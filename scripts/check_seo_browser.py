#!/usr/bin/env python3
"""Real Chromium + isolated Caddy checks; never contacts production or restarts services."""
import json
import os
import re
import shutil
import socket
import subprocess
import time
from urllib.request import urlopen
import xml.etree.ElementTree as ET

from playwright.sync_api import sync_playwright
from build_seo import NS, ROOT, Sources, read

ARTIFACTS = ROOT / 'artifacts/seo/browser'


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    caddy = os.environ.get('CADDY_BIN') or shutil.which('caddy') or str(ROOT / 'tmp/commerce-tools/caddy')
    port, fragment_port = free_port(), free_port()
    local = (ROOT / 'ops/local/Caddyfile').read_text()
    local = local.replace('http://:3003', f'http://127.0.0.1:{port}').replace('tcp4/0.0.0.0', 'tcp4/127.0.0.1')
    fragment = (ROOT / 'ops/seo/Caddyfile.fragment').read_text().replace('/root/projs/tongjian/dist', str(ROOT / 'dist'))
    config = local + f'''\nhttp://127.0.0.1:{fragment_port} {{
{fragment}
handle {{
 root * dist
 file_server
}}
}}\n'''
    caddyfile = ARTIFACTS / 'Caddyfile.test'
    caddyfile.write_text(config)
    subprocess.run([caddy, 'validate', '--config', str(caddyfile), '--adapter', 'caddyfile'], cwd=ROOT, check=True, capture_output=True)
    report = dict(status='running', productionContacted=False, existingServicesRestarted=False,
                  viewports=[], noJavaScriptPages=[], readerParity=[], rootRoutes=[], pageErrors=[])
    with (ARTIFACTS / 'caddy.log').open('w') as log:
        process = subprocess.Popen([caddy, 'run', '--config', str(caddyfile), '--adapter', 'caddyfile'],
                                   cwd=ROOT, stdout=log, stderr=log)
        try:
            origin = f'http://127.0.0.1:{port}'
            base = origin + '/'
            for attempt in range(60):
                try:
                    with urlopen(base, timeout=1) as response:
                        assert response.status == 200
                    break
                except OSError:
                    if process.poll() is not None:
                        raise RuntimeError('Test Caddy exited; see caddy.log')
                    time.sleep(.1)
            else:
                raise RuntimeError('Test Caddy did not start')
            manifest = read(ROOT / 'dist/seo-manifest.json')
            config = manifest
            sources = Sources(ROOT / 'dist')
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport={'width': 1440, 'height': 1000})
                page = context.new_page()
                page.on('pageerror', lambda error: report['pageErrors'].append(str(error)))
                # Both actual local config and candidate production fragment must serve root files.
                for test_port in (port, fragment_port):
                    host = f'http://127.0.0.1:{test_port}'
                    robots = page.request.get(host + '/robots.txt', max_redirects=0)
                    assert robots.status == 200 and robots.headers['content-type'].startswith('text/plain')
                    assert 'Sitemap: https://deewins.top/sitemap.xml' in robots.text()
                    assert 'Hello from Caddy' not in robots.text()
                    root = page.request.get(host + '/sitemap.xml', max_redirects=0)
                    assert root.status == 200
                    assert ET.fromstring(root.body()).tag == f'{{{NS}}}urlset'
                    sitemap = page.request.get(host + '/sitemap.xml')
                    assert sitemap.status == 200 and ET.fromstring(sitemap.body()).tag == f'{{{NS}}}urlset'
                    assert page.request.get(host + '/not-a-real-seo-page.html').status == 404
                    if test_port == port:
                        for old, new in [('/tongjian', '/'), ('/tongjian/', '/'),
                                         ('/tongjian/reader.html?from=legacy', '/reader.html?from=legacy')]:
                            moved = page.request.get(host + old, max_redirects=0)
                            assert moved.status == 308 and moved.headers['location'] == host + new
                    report['rootRoutes'].append('local-config' if test_port == port else 'candidate-production-fragment')
                # Content is readable without JS, including on mobile; no redirect-to-reader shells.
                nojs = browser.new_context(java_script_enabled=False, viewport={'width': 390, 'height': 844})
                static = nojs.new_page()
                for relative in manifest['pages']:
                    response = static.goto(base + relative.removesuffix('index.html'), wait_until='domcontentloaded')
                    assert response.status == 200
                    assert static.locator('h1').is_visible()
                    assert static.locator('main').inner_text().strip()
                    if re.fullmatch(r'volume/\d+/index.html', relative):
                        assert static.locator('.source-original').first.is_visible()
                        if static.locator('.modern-text').count():
                            assert static.locator('.modern-text').first.is_visible()
                        else:
                            assert static.locator('.missing').first.is_visible()
                        assert not static.locator('.reading-controls').is_visible()
                    if relative.startswith('people/') and relative != 'people/index.html':
                        assert static.locator('.person-event blockquote').first.is_visible()
                    assert static.evaluate('document.documentElement.scrollWidth <= innerWidth'), relative
                    if relative in ('volume/1/index.html', 'people/zhao-xiang-zi/index.html'):
                        static.screenshot(path=str(ARTIFACTS / ('nojs-' + relative.replace('/', '-') + '.png')))
                    report['noJavaScriptPages'].append(relative)
                    if len(report['noJavaScriptPages']) % 50 == 0:
                        print(f'No-JavaScript browser checks: {len(report["noJavaScriptPages"])}/{len(manifest["pages"])}', flush=True)
                nojs.close()
                # Shared templates: exercise every data shape at desktop and both mobile sizes.
                samples = ['reading.html', 'volume/index.html', 'people/index.html'] + [
                    f'volume/{v}/index.html' for v in (1, 3, 9, 14, 28, 72, 113, 192, 200, 201, 294)] + [
                    f'people/{pid}/index.html' for pid in ('zhao-xiang-zi', 'zhang-yi', 'shang-yang')] + [
                    p or 'index.html' for p in manifest['publicPages']]
                for width in (1440, 390, 320):
                    page.set_viewport_size({'width': width, 'height': 1000 if width == 1440 else 844})
                    for relative in samples:
                        response = page.goto(base + relative.removesuffix('index.html'))
                        assert response.status == 200
                        assert page.locator('h1').is_visible()
                        if relative == 'ruler-deaths.html':
                            page.locator('#rulerRows tr').first.wait_for()
                        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), (width, relative, 'overflow')
                        if re.fullmatch(r'volume/\d+/index.html', relative):
                            page.locator('.reading-controls').wait_for()
                            page.locator('.comparison-row').first.scroll_into_view_if_needed()
                            original = page.locator('.original-cell').first.bounding_box()
                            modern = page.locator('.modern-cell').first.bounding_box()
                            if width > 650:
                                assert modern['x'] > original['x'] + original['width'] - 2
                            else:
                                assert modern['y'] >= original['y'] + original['height'] - 2
                            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                        if relative in ('reading.html', 'volume/1/index.html', 'people/zhao-xiang-zi/index.html', 'power-rules.html', 'ruler-deaths.html'):
                            page.screenshot(path=str(ARTIFACTS / (str(width) + '-' + relative.replace('/', '-') + '.png')))
                    report['viewports'].append(width)
                # The personnel directory filter is optional enhancement, never a content fetch.
                page.goto(base + 'people/')
                page.locator('#peopleFilter').fill('张仪')
                assert page.locator('#staticPeopleList li:visible').count() == 1
                page.locator('#peopleFilter').fill('not-a-person')
                assert page.locator('#staticPeopleList li:visible').count() == 0
                page.locator('#peopleFilter').fill('')
                assert page.locator('#staticPeopleList li:visible').count() == len(manifest['people'])
                # Progressive controls change display, not the URL or document text.
                page.goto(base + 'volume/1/#year-403-para-13')
                page.locator('.reading-controls').wait_for()
                start_url = page.url
                page.locator('#staticMode').select_option('modern')
                assert not page.locator('.original-cell').first.is_visible()
                assert page.locator('.modern-cell').first.is_visible()
                page.locator('#staticMode').select_option('original')
                assert not page.locator('.modern-cell').first.is_visible()
                page.locator('#staticMode').select_option('compare')
                page.locator('#staticNotes').uncheck()
                assert not page.locator('.source-original .source-note').first.is_visible()
                page.locator('#staticNotes').check()
                assert page.locator('.source-original .source-note').first.is_visible()
                page.locator('#staticLarger').click()
                assert page.locator('.source-original').first.evaluate('e => getComputedStyle(e).fontSize') == '20px'
                page.locator('#staticSmaller').click()
                assert page.url == start_url
                # Ordinary navigation, exact source anchors and browser back remain usable.
                page.goto(base + 'people/')
                page.get_by_role('link', name='赵襄子', exact=True).click()
                page.locator('.person-event').first.get_by_role('link', name='阅读这一段的原文与白话').first.click()
                assert '/volume/1/#year-403-para-' in page.url
                target_id = page.url.split('#')[1]
                assert page.locator('[id="' + target_id + '"]').is_visible()
                page.go_back()
                assert '/people/zhao-xiang-zi/' in page.url
                page.locator('.person-event').first.get_by_role('link', name='在阅读器中核对上下文').click()
                page.wait_for_function('typeof book !== "undefined" && book?.volume === 1 && readerOpen')
                assert page.locator('.compare-row.active').is_visible()
                # Compare actual browser-loaded data with Python generator inputs, including
                # v28's uploaded-only recovery, date warnings and unresolved originals.
                for volume in config['volumes']:
                    actual = page.evaluate('(v) => loadVolume(v).then(b => JSON.parse(JSON.stringify(b)))', volume)
                    expected = sources.effective(volume)
                    assert actual['intro'] == expected['intro']
                    for a, b in zip(actual['years'], expected['years']):
                        for key in ('year', 'paragraphs', 'bilingual', 'translationMissing', 'translationWarning', 'translationHeaders', 'yearIllustrations'):
                            assert a.get(key) == b.get(key), (volume, a['year'], key)
                    report['readerParity'].append(volume)
                    if len(report['readerParity']) % 50 == 0:
                        print(f'Full reader/generator parity: {len(report["readerParity"])}/294', flush=True)
                # Existing reader: previous/next, same-year continuation, return to yearbook.
                page.goto(base + 'reader.html#volume-200-year--662')
                page.wait_for_function('typeof book !== "undefined" && book?.volume === 200 && readerOpen')
                assert page.locator('#nextYear').inner_text() == '本年续篇 →'
                page.locator('#nextYear').click()
                page.wait_for_url('**#volume-201-year--662')
                page.locator('#closeReader').click()
                assert page.locator('#annualPage').is_visible()
                assert not report['pageErrors'], report['pageErrors']
                browser.close()
            report['status'] = 'passed'
        except Exception as error:
            report['status'] = 'failed'
            report['failure'] = str(error)
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            (ARTIFACTS / 'validation.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({**report, 'noJavaScriptPages': len(report['noJavaScriptPages']),
                      'readerParity': len(report['readerParity'])}, ensure_ascii=False))


if __name__ == '__main__':
    main()
