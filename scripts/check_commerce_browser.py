#!/usr/bin/env python3
"""Isolated PostgreSQL + real browser QA. Fake payments, never a real merchant transaction."""
import email
import json
import os
import re
import shutil
import socket
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx
import psycopg
from psycopg import sql
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def registration_code(address):
    for path in sorted((ROOT / 'backend/test-mail').glob('*'), key=lambda path: path.stat().st_mtime, reverse=True):
        message = email.message_from_bytes(path.read_bytes())
        if address in message.get('To', ''):
            plain = message.get_payload(decode=True).decode(message.get_content_charset() or 'utf-8')
            match = re.search(r'注册验证码是 (\d{6})', plain)
            if match:
                return match.group(1)
    raise AssertionError('Registration mail not generated')

def main():
    run_id = time.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    artifacts = ROOT / 'artifacts/commerce' / run_id
    artifacts.mkdir(parents=True)
    database_name = 'tongjian_browser_' + uuid.uuid4().hex[:8] + '_test'
    base_db = os.getenv('BROWSER_DATABASE_URL', 'postgresql://tongjian:local-development-only@127.0.0.1:55432/tongjian_commerce_test')
    parsed = urlsplit(base_db)
    if not parsed.path.endswith('_test'):
        raise ValueError('BROWSER_DATABASE_URL must be a dedicated *_test connection')
    with psycopg.connect(base_db, autocommit=True) as db:
        db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(database_name)))
    url = urlunsplit(parsed._replace(path='/' + database_name))
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        backend_port = sock.getsockname()[1]
    origin = f'http://127.0.0.1:{port}'
    env = {**os.environ, 'EMAIL_HOST': '', 'DATABASE_URL': url, 'DJANGO_SETTINGS_MODULE': 'config.settings.development',
           'PAYMENT_PROVIDER': 'fake', 'SALES_ENABLED': 'true', 'SITE_URL': origin,
           'TRUSTED_PROXY_NETWORKS': '127.0.0.1/32',
           'XDG_CONFIG_HOME': str(artifacts / 'caddy-config'), 'XDG_DATA_HOME': str(artifacts / 'caddy-data')}
    python = str(ROOT / '.venv-commerce/bin/python')
    manage = [python, str(ROOT / 'backend/manage.py')]
    def solve_graphic(page):
        # Fixture only in the disposable QA database; production has no bypass.
        identifier = page.locator('[name=captcha_id]').input_value()
        command = ("from accounts.models import GraphicChallenge; from accounts.captcha import answer_digest; "
                   f"GraphicChallenge.objects.filter(pk='{uuid.UUID(identifier)}').update("
                   f"answer_digest=answer_digest('{uuid.UUID(identifier)}', 'ABCD'))")
        subprocess.run(manage + ['shell', '-c', command], env=env, check=True, stdout=log)
        page.locator('[name=captcha]').fill('abcd')

    process = proxy = None
    evidence = {'mode': 'local fake payments; real Chromium + Caddy + Gunicorn; isolated PostgreSQL', 'checks': [], 'page_errors': [], 'viewports': []}
    log = (artifacts / 'server.log').open('w')
    try:
        subprocess.run(manage + ['migrate', '--noinput'], env=env, check=True, stdout=log)
        subprocess.run(manage + ['import_product'], env=env, check=True, stdout=log)
        subprocess.run(manage + ['collectstatic', '--noinput'], env=env, check=True, stdout=log)
        caddy = os.getenv('CADDY_BIN') or shutil.which('caddy') or str(ROOT / 'tmp/commerce-tools/caddy')
        if not Path(caddy).is_file():
            raise RuntimeError('Install Caddy or set CADDY_BIN for real reverse-proxy QA')
        fragment = (ROOT / 'ops/commerce/Caddyfile.fragment').read_text().replace('127.0.0.1:8010', f'127.0.0.1:{backend_port}')
        fragment = fragment.replace('/srv/tongjian-commerce/static', str(ROOT / 'tmp/commerce-static'))
        config = ('{\n admin off\n auto_https off\n}\n' + f'http://127.0.0.1:{port} {{\n bind 127.0.0.1\n' + fragment +
                  f'\n redir /tongjian /tongjian/ 308\n handle_path /tongjian/* {{\n root * {ROOT / "dist"}\n file_server\n }}\n handle {{\n respond 404\n }}\n}}\n')
        caddyfile = artifacts / 'Caddyfile.local'
        caddyfile.write_text(config)
        subprocess.run([caddy, 'validate', '--config', str(caddyfile), '--adapter', 'caddyfile'], check=True, stdout=log, stderr=log)
        process = subprocess.Popen([str(ROOT / '.venv-commerce/bin/gunicorn'), 'config.wsgi:application', '--bind', f'127.0.0.1:{backend_port}',
                                   '--workers', '2', '--timeout', '30'], cwd=ROOT / 'backend', env=env, stdout=log, stderr=log)
        proxy = subprocess.Popen([caddy, 'run', '--config', str(caddyfile), '--adapter', 'caddyfile'], env=env, stdout=log, stderr=log)
        for _ in range(100):
            try:
                if httpx.get(origin + '/tongjian/api/v1/healthz/', timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(.1)
        else:
            raise RuntimeError('QA server did not start')
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=shutil.which('google-chrome-stable') or shutil.which('chromium'),
                                                args=['--no-sandbox'])
            buyer = browser.new_context(viewport={'width': 1440, 'height': 1000})
            stranger = browser.new_context(viewport={'width': 390, 'height': 844})
            page = buyer.new_page()
            page.on('pageerror', lambda error: evidence['page_errors'].append(str(error)))
            page.goto(origin + '/tongjian/truth.html#wugu')
            assert stranger.request.get(origin + '/tongjian/admin-static/admin/css/base.css').status == 200
            assert stranger.request.get(origin + '/tongjian/api/v1/session/').headers.get('cache-control') == 'private, no-store'
            assert stranger.request.get(origin + '/tongjian').status == 200
            page.locator('[data-buy]').filter(has_text='登录后购买').wait_for()
            assert page.locator('#chenzhen').count() == 1 and page.locator('#wugu').count() == 0
            assert (stranger.request.get(origin + '/tongjian/api/v1/products/truth/download/')).status == 401
            evidence['checks'].append('anonymous preview whitelist; PDF API 401')
            page.locator('[data-buy]').click()
            page.wait_for_url('**/account/login/**')
            address = f'browser-{uuid.uuid4().hex}@example.com'
            page.get_by_role('link', name='注册账号', exact=True).click()
            password = 'Browser-' + uuid.uuid4().hex + '!'
            page.locator('[name=email]').fill(address)
            old_image = page.locator('[name=captcha_id]').input_value()
            page.get_by_role('button', name='换一张', exact=True).click()
            page.wait_for_function("old => document.querySelector('[name=captcha_id]').value !== old", arg=old_image)
            assert page.locator('[name=email]').input_value() == address
            solve_graphic(page)
            page.get_by_role('button', name='发送验证码', exact=True).click()
            page.locator('.registration-sent').wait_for()
            evidence['checks'].append('graphical captcha refresh preserves email; captcha-protected email registration')
            page.locator('[name=code]').fill(registration_code(address))
            page.locator('[name=password1]').fill(password)
            page.locator('[name=password2]').fill(password)
            page.get_by_role('button', name='验证邮箱并注册', exact=True).click()
            page.wait_for_url('**/truth.html#wugu')
            page.locator('[data-buy]').filter(has_text='购买完整专题').wait_for()
            assert buyer.request.get(origin + '/tongjian/api/v1/products/truth/download/').status == 403
            page.locator('[data-accept-terms]').check()
            page.locator('[data-buy]').click()
            page.wait_for_url('**/checkout/**')
            order_id = page.url.rstrip('/').rsplit('/', 1)[-1]
            assert stranger.request.get(origin + f'/tongjian/api/v1/orders/{order_id}/').status == 401
            page.get_by_role('button', name='模拟付款成功').click()
            page.locator('[data-read]').wait_for()
            page.locator('[data-read]').click()
            page.wait_for_url('**/article/truth/#wugu')
            assert page.locator('#wugu').count() == 1
            assert page.locator('figure.article-diagram').count() == 6
            assert page.locator('table').count() == 3
            pdf = buyer.request.get(origin + '/tongjian/api/v1/products/truth/download/')
            assert pdf.status == 200 and pdf.body().startswith(b'%PDF-')
            assert pdf.headers.get('cache-control') == 'private, no-store'
            assert stranger.request.get(origin + '/tongjian/api/v1/products/truth/download/').status == 401
            unowned = stranger.request.get(origin + '/tongjian/article/truth/', max_redirects=0)
            assert unowned.status == 302 and '#wugu' not in unowned.text()
            evidence['checks'].append('email-code verification plus password registration; unpurchased PDF 403; fake purchase; six diagrams and three tables; cross-context PDF blocked')
            page.locator('#question').scroll_into_view_if_needed()
            page.screenshot(path=str(artifacts / 'desktop-article.png'))
            for width in [1440, 390, 320]:
                page.set_viewport_size({'width': width, 'height': 900})
                page.goto(origin + '/tongjian/article/truth/')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                for section in ['chenzhen', 'ganmao', 'chenping', 'wugu', 'deer', 'zhaodi', 'comparison', 'practice']:
                    page.locator('.method a[href="#' + section + '"]').click()
                    assert urlsplit(page.url).fragment == section
                evidence['viewports'].append({'width': width, 'no_overflow': True, 'toc_anchors': 8})
                page.goto(origin + '/tongjian/account/purchases/')
                assert page.get_by_role('link', name='阅读全文').count() >= 1
                page.screenshot(path=str(artifacts / f'purchases-{width}.png'))
                page.goto(origin + '/tongjian/truth.html')
                page.locator('[data-buy]').filter(has_text='继续阅读全文').wait_for()
                page.screenshot(path=str(artifacts / f'preview-{width}.png'))
            page.goto(origin + '/tongjian/article/truth/#question')
            page.locator('a[href="/tongjian/reader.html#volume-10-year-204-para-20"]').first.click()
            page.wait_for_url('**/reader.html#volume-10-year-204-para-20')
            page.wait_for_function('document.body.innerText.includes("项羽")', timeout=20000)
            page.go_back()
            page.wait_for_url('**/article/truth/#question')
            assert page.locator('#wugu').count() == 1
            page.goto(origin + '/tongjian/account/purchases/')
            page.get_by_role('button', name='退出登录').click()
            page.wait_for_url('**/research.html')
            assert buyer.request.get(origin + '/tongjian/api/v1/products/truth/download/').status == 401
            assert stranger.request.get(origin + '/tongjian/private-content/truth/20261014-v1/reader.pdf').status == 404
            assert stranger.request.get(origin + '/tongjian/../private-content/truth/20261014-v1/reader.pdf').status == 404
            evidence['checks'].append('1440/390/320 layouts; eight anchors; original reader deep link and back; logout revokes session')
            # Native HTML forms: registration, validation, password login, recovery.
            for width in [1440, 390, 320]:
                page.set_viewport_size({'width': width, 'height': 900})
                for route, heading in [('login', '登录'), ('register', '注册账号'), ('password-reset', '找回密码')]:
                    page.goto(origin + '/tongjian/account/' + route + '/')
                    assert page.get_by_role('heading', name=heading, exact=True).is_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.screenshot(path=str(artifacts / f'{route}-{width}.png'), full_page=True)
            page.goto(origin + '/tongjian/account/login/')
            page.locator('[name=username]').fill(address)
            page.locator('[name=password]').fill('deliberately-wrong')
            page.get_by_role('button', name='登录', exact=True).click()
            assert page.get_by_text('邮箱或密码不正确，请重新输入。', exact=True).is_visible()
            page.locator('[name=password]').fill(password)
            page.get_by_role('button', name='登录', exact=True).click()
            page.wait_for_url('**/account/')
            assert buyer.request.get(origin + '/tongjian/api/v1/products/truth/download/').status == 200
            page.get_by_role('button', name='退出登录').click()
            page.wait_for_url('**/research.html')
            page.goto(origin + '/tongjian/account/password-reset/')
            page.locator('[name=email]').fill(address)
            page.get_by_role('button', name='发送重设链接').click()
            page.wait_for_url('**/password-reset/sent/')
            reset_url = None
            for path in sorted((ROOT / 'backend/test-mail').glob('*'), key=lambda path: path.stat().st_mtime, reverse=True):
                parsed_mail = email.message_from_bytes(path.read_bytes())
                if address in parsed_mail.get('To', ''):
                    plain = parsed_mail.get_payload(decode=True).decode(parsed_mail.get_content_charset() or 'utf-8')
                    match = re.search(r'https?://[^\s]+/tongjian/account/reset/[^\s]+', plain)
                    if match:
                        reset_url = match.group()
                        break
            assert reset_url
            page.goto(reset_url)
            new_password = 'Reset-' + uuid.uuid4().hex + '!'
            page.locator('[name=new_password1]').fill(new_password)
            page.locator('[name=new_password2]').fill(new_password)
            page.get_by_role('button', name='保存新密码').click()
            page.wait_for_url('**/password-reset/complete/')
            page.get_by_role('link', name='前往登录').click()
            page.locator('[name=username]').fill(address)
            page.locator('[name=password]').fill(new_password)
            page.get_by_role('button', name='登录', exact=True).click()
            page.wait_for_url('**/account/')
            assert buyer.request.get(origin + '/tongjian/api/v1/products/truth/download/').status == 200
            # Account security remains separate from purchases and works natively.
            for width in [1440, 390, 320]:
                page.set_viewport_size({'width': width, 'height': 900})
                for route, heading in [('', '我的账号'), ('password-change/', '修改密码')]:
                    page.goto(origin + '/tongjian/account/' + route)
                    assert page.get_by_role('heading', name=heading, exact=True).is_visible()
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                    page.screenshot(path=str(artifacts / f'account-{route.replace("/", "") or "overview"}-{width}.png'), full_page=True)
            page.locator('[name=old_password]').fill(new_password)
            changed_password = 'Changed-' + uuid.uuid4().hex + '!'
            page.locator('[name=new_password1]').fill(changed_password)
            page.locator('[name=new_password2]').fill(changed_password)
            page.get_by_role('button', name='保存新密码', exact=True).click()
            page.wait_for_url('**/password-change/done/')
            assert buyer.request.get(origin + '/tongjian/api/v1/session/').json()['authenticated']
            assert buyer.request.get(origin + '/tongjian/api/v1/products/truth/download/').status == 200
            # Logging in from a reader event returns to that event, including its hash.
            reader_path = '/tongjian/reader.html#volume-1-year-403'
            returning = stranger.new_page()
            returning.goto(origin + reader_path)
            returning.locator('[data-account-link][href*="account/login/"]').wait_for()
            returning.locator('[data-account-link]').click()
            returning.wait_for_url('**/account/login/**')
            assert returning.locator('[name=next]').input_value() == reader_path
            returning.locator('[name=username]').fill(address)
            returning.locator('[name=password]').fill(changed_password)
            returning.get_by_role('button', name='登录', exact=True).click()
            returning.wait_for_url('**/reader.html#volume-1-year-403')
            returning.get_by_role('link', name='我的账号', exact=True).wait_for()
            returning.close()
            evidence['checks'].append('account overview and password change at 1440/390/320; change keeps current login and purchases; reader login preserves event hash')
            native = browser.new_context(java_script_enabled=False)
            nojs = native.new_page()
            nojs.goto(origin + '/tongjian/account/register/')
            native_address = 'nojs-' + uuid.uuid4().hex + '@example.com'
            nojs.locator('[name=email]').fill(native_address)
            solve_graphic(nojs)
            nojs.get_by_role('button', name='发送验证码', exact=True).click()
            assert nojs.locator('.registration-sent').is_visible()
            nojs.locator('[name=code]').fill(registration_code(native_address))
            nojs.locator('[name=password1]').fill(password)
            nojs.locator('[name=password2]').fill(password)
            nojs.get_by_role('button', name='验证邮箱并注册', exact=True).click()
            nojs.wait_for_url('**/account/')
            nojs.get_by_role('link', name='修改密码', exact=True).click()
            nojs.locator('[name=old_password]').fill(password)
            native_password = 'Native-' + uuid.uuid4().hex + '!'
            nojs.locator('[name=new_password1]').fill(native_password)
            nojs.locator('[name=new_password2]').fill(native_password)
            nojs.get_by_role('button', name='保存新密码', exact=True).click()
            nojs.wait_for_url('**/password-change/done/')
            nojs.get_by_role('link', name='返回我的账号', exact=True).click()
            nojs.get_by_role('button', name='退出登录', exact=True).click()
            nojs.wait_for_url('**/research.html')
            assert not native.request.get(origin + '/tongjian/api/v1/session/').json()['authenticated']
            nojs.goto(origin + '/tongjian/account/login/')
            nojs.locator('[name=username]').fill(native_address)
            nojs.locator('[name=password]').fill(native_password)
            nojs.get_by_role('button', name='登录', exact=True).click()
            nojs.wait_for_url('**/account/')
            native.close()
            evidence['checks'].append('native registration/login/reset forms at 1440/390/320; wrong password feedback; logout and password login preserve purchases; recovery link resets password and preserves PDF access; verified registration, password change, logout and login work with JavaScript disabled')
            assert not evidence['page_errors']
            browser.close()
        evidence['passed'] = True
    finally:
        if proxy:
            proxy.terminate()
            proxy.wait(timeout=10)
        if process:
            process.terminate()
            process.wait(timeout=10)
        log.close()
        with psycopg.connect(base_db, autocommit=True) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(database_name)))
        (artifacts / 'qa-report.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    print(f'Real-browser QA passed: {artifacts.relative_to(ROOT)}')

if __name__ == '__main__':
    main()
