#!/usr/bin/env python3
"""Real pg_dump/pg_restore drill in two disposable PostgreSQL databases, never the live database."""
import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import psycopg
from psycopg import sql
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

ROOT = Path(__file__).resolve().parents[1]

def main():
    run = uuid.uuid4().hex[:10]
    work = ROOT / 'commerce-backups/restore-drill' / run
    work.mkdir(parents=True)
    source_name, target_name = 'tongjian_backup_' + run + '_test', 'tongjian_restore_' + run + '_test'
    base = os.getenv('BROWSER_DATABASE_URL', 'postgresql://tongjian:local-development-only@127.0.0.1:55432/tongjian_commerce_test')
    parsed = urlsplit(base)
    if not parsed.path.endswith('_test'):
        raise ValueError('Use a dedicated *_test connection')
    source_url = urlunsplit(parsed._replace(path='/' + source_name))
    target_url = urlunsplit(parsed._replace(path='/' + target_name))
    python = str(ROOT / '.venv-commerce/bin/python')
    manage = [python, str(ROOT / 'backend/manage.py')]
    env = {**os.environ, 'DATABASE_URL': source_url, 'PAYMENT_PROVIDER': 'fake', 'SALES_ENABLED': 'true',
           'DJANGO_SETTINGS_MODULE': 'config.settings.development',
           'PG_TOOL_PREFIX': os.getenv('PG_TOOL_PREFIX', '["docker","exec","-i","tongjian-commerce-dev"]')}
    report = {'mode': 'isolated PostgreSQL encrypted restore drill', 'passed': False}
    created = []
    try:
        with psycopg.connect(base, autocommit=True) as db:
            for name in [source_name, target_name]:
                db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
                created.append(name)
        subprocess.run(manage + ['migrate', '--noinput'], env=env, check=True, capture_output=True)
        subprocess.run(manage + ['import_product'], env=env, check=True, capture_output=True)
        seed = '''from accounts.models import User
from commerce.models import Product, AccessGrant
from commerce.services import create_order,ensure_payment,reconcile_order,request_refund,reconcile_refund
from payments.models import FakeTransaction,FakeRefund
from django.contrib.sessions.models import Session
from django.utils import timezone
import uuid
user=User.objects.create_user('restore-reader@example.com')
staff=User.objects.create_superuser('restore-admin@example.com','restore-strong-password')
product=Product.objects.get(slug='truth')
order=ensure_payment(create_order(user,'truth',product.revision,'native',uuid.uuid4().hex,'127.0.0.1'))
FakeTransaction.objects.filter(merchant_number=order.merchant_number).update(state='SUCCESS')
order=reconcile_order(order,force=True)
refund=request_refund(order,staff,'恢复演练')
FakeRefund.objects.filter(merchant_number=refund.merchant_number).update(state='succeeded')
reconcile_refund(refund)
AccessGrant.objects.create(user=user,product=product,reason='另有人工权益')
Session.objects.create(session_key='restore-session-fixture',session_data='test',expire_date=timezone.now())
'''
        subprocess.run(manage + ['shell', '-c', seed], env=env, check=True, capture_output=True)
        key = work / 'backup.key'
        key.write_bytes(os.urandom(32)); key.chmod(0o600)
        file = work / 'drill.tjcb'
        backup = [python, str(ROOT / 'ops/commerce/backup.py')]
        subprocess.run(backup + ['backup', '--file', str(file), '--key-file', str(key), '--content-root', str(ROOT / 'private-content')], env=env, check=True)
        raw = file.read_bytes()
        assert b'database.dump' not in raw and b'restore-reader@example.com' not in raw
        for payload, secret in [(raw[17:-1] + bytes([raw[-1] ^ 1]), key.read_bytes()), (raw[17:], os.urandom(32))]:
            try:
                AESGCM(secret).decrypt(raw[5:17], payload, b'tongjian-commerce-backup-v1')
                raise AssertionError('Invalid backup unexpectedly decrypted')
            except InvalidTag:
                pass
        restored = work / 'restored-content'
        subprocess.run(backup + ['restore', '--file', str(file), '--key-file', str(key), '--content-root', str(restored),
                                  '--confirm-database', target_name], env={**env, 'RESTORE_DATABASE_URL': target_url}, check=True)
        with psycopg.connect(source_url) as source, psycopg.connect(target_url) as target:
            tables = [row[0] for row in source.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")]
            for table in tables:
                source_count = source.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
                target_count = target.execute(sql.SQL('SELECT count(*) FROM {}').format(sql.Identifier(table))).fetchone()[0]
                assert target_count == (0 if table == 'django_session' else source_count), table
            assert target.execute('SELECT count(*) FROM commerce_accessgrant WHERE active').fetchone()[0] == 1
            assert target.execute("SELECT count(*) FROM commerce_refund WHERE status='succeeded'").fetchone()[0] == 1
        files = 0
        for original in (ROOT / 'private-content').rglob('*'):
            if original.is_file():
                relative = original.relative_to(ROOT / 'private-content')
                assert hashlib.sha256(original.read_bytes()).digest() == hashlib.sha256((restored / relative).read_bytes()).digest()
                files += 1
        report.update(passed=True, database_tables=len(tables), content_files=files, encrypted=True,
                      tamper_and_wrong_key_rejected=True, sessions_invalidated=True, refund_and_manual_grant_preserved=True)
    finally:
        with psycopg.connect(base, autocommit=True) as db:
            for name in created:
                db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        destination = ROOT / 'artifacts/commerce/restore-drill'
        destination.mkdir(parents=True, exist_ok=True)
        (destination / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('Encrypted PostgreSQL/content restore drill passed')

if __name__ == '__main__':
    main()
