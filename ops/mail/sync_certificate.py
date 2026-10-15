#!/usr/bin/env python3
"""Install Caddy's verified mail certificate and reload the mail services.

Run as root on deewins. No credentials or private keys are logged.
"""
import hashlib
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile


HOST = 'mail.deewins.top'
SOURCE = Path('/var/lib/caddy/.local/share/caddy/certificates')
DEST = Path('/etc/mail/certificates')
ACTIVE = Path('/etc/mail/tls')


def checked(*args):
    result = subprocess.run(args, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError('Certificate validation failed: ' + args[1])


def main():
    if os.geteuid() != 0:
        raise SystemExit('Run as root')
    candidates = sorted(SOURCE.glob(f'*/{HOST}/{HOST}.crt'),
                        key=lambda p: p.stat().st_mtime, reverse=True)
    source = None
    for cert in candidates:
        key = cert.with_suffix('.key')
        try:
            checked('openssl', 'x509', '-in', str(cert), '-noout', '-checkhost', HOST)
            checked('openssl', 'x509', '-in', str(cert), '-noout', '-checkend', '86400')
            checked('openssl', 'verify', '-verify_hostname', HOST,
                    '-untrusted', str(cert), str(cert))
            ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER).load_cert_chain(cert, key)
        except (RuntimeError, OSError, ssl.SSLError):
            continue
        source = cert
        break
    if source is None:
        raise SystemExit('No valid public mail.deewins.top certificate available yet')

    fingerprint = hashlib.sha256(source.read_bytes()).hexdigest()
    DEST.mkdir(mode=0o700, parents=True, exist_ok=True)
    version = DEST / fingerprint
    if not version.exists():
        with tempfile.TemporaryDirectory(prefix='.install-', dir=DEST) as tmp:
            stage = Path(tmp)
            shutil.copyfile(source, stage / 'fullchain.pem')
            shutil.copyfile(source.with_suffix('.key'), stage / 'privkey.pem')
            (stage / 'fullchain.pem').chmod(0o644)
            (stage / 'privkey.pem').chmod(0o600)
            stage.rename(version)
    if ACTIVE.is_symlink() and ACTIVE.resolve() == version:
        print('Mail certificate already current')
        return
    if ACTIVE.exists() and not ACTIVE.is_symlink():
        # Preserve the local staging certificate, never delete its private key.
        bootstrap = DEST / 'bootstrap'
        if bootstrap.exists():
            raise SystemExit('Unexpected existing certificate directory; inspect manually')
        ACTIVE.rename(bootstrap)
    link = ACTIVE.with_name('.tls-next')
    link.unlink(missing_ok=True)
    link.symlink_to(version, target_is_directory=True)
    link.replace(ACTIVE)
    for service in ('dovecot', 'postfix'):
        subprocess.run(['systemctl', 'try-reload-or-restart', service], check=True)
    print('Verified mail certificate installed and mail services reloaded')


if __name__ == '__main__':
    main()
