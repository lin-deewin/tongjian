#!/usr/bin/env python3
"""Encrypted pg_dump + immutable content. Restore ONLY into an explicitly named empty database."""
import argparse
import hashlib
import io
import json
import os
import subprocess
import tarfile
import tempfile
import datetime
import uuid
from pathlib import Path
from urllib.parse import urlsplit, unquote

import psycopg
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ROOT = Path(__file__).resolve().parents[2]
HEADER = b'TJCB1'
AAD = b'tongjian-commerce-backup-v1'

def tool(name, url, args, input_data=None):
    parsed = urlsplit(url)
    prefix = json.loads(os.getenv('PG_TOOL_PREFIX', '[]'))
    if not isinstance(prefix, list) or any(not isinstance(value, str) for value in prefix):
        raise ValueError('PG_TOOL_PREFIX must be a JSON argument array')
    command = prefix + [name, '--username', unquote(parsed.username or ''), '--dbname', parsed.path.lstrip('/')]
    if not prefix:
        command += ['--host', parsed.hostname or '127.0.0.1', '--port', str(parsed.port or 5432)]
    env = {**os.environ, 'PGPASSWORD': unquote(parsed.password or '')}
    return subprocess.run(command + args, input=input_data, capture_output=True, env=env, check=True, timeout=300).stdout

def key_bytes(path):
    if path.stat().st_mode & 0o077:
        raise ValueError('Backup key permissions must be 0600 or stricter')
    key = path.read_bytes()
    if len(key) != 32:
        raise ValueError('Backup key must contain exactly 32 random bytes')
    return key

def pack(database_dump, content):
    files = {'database.dump': database_dump}
    for path in sorted(content.rglob('*')):
        if path.is_symlink():
            raise ValueError('Content symlinks are not allowed')
        if path.is_file():
            files['content/' + path.relative_to(content).as_posix()] = path.read_bytes()
    files['checksums.json'] = json.dumps({name: hashlib.sha256(value).hexdigest() for name, value in files.items()}).encode()
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as archive:
        for name, value in files.items():
            entry = tarfile.TarInfo(name)
            entry.size, entry.mode = len(value), 0o600
            archive.addfile(entry, io.BytesIO(value))
    return output.getvalue()

def unpack(data):
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:gz') as archive:
        for member in archive:
            path = Path(member.name)
            if not member.isfile() or path.is_absolute() or '..' in path.parts or member.name in files:
                raise ValueError('Unsafe backup member')
            if member.name not in {'database.dump', 'checksums.json'} and not member.name.startswith('content/'):
                raise ValueError('Unexpected backup member')
            files[member.name] = archive.extractfile(member).read()
    checksums = json.loads(files.pop('checksums.json'))
    if set(files) != set(checksums) or any(hashlib.sha256(value).hexdigest() != checksums[name] for name, value in files.items()):
        raise ValueError('Backup checksum mismatch')
    return files

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['backup', 'restore'])
    location = parser.add_mutually_exclusive_group(required=True)
    location.add_argument('--file', type=Path)
    location.add_argument('--directory', type=Path)
    parser.add_argument('--key-file', type=Path, required=True)
    parser.add_argument('--content-root', type=Path, required=True)
    parser.add_argument('--confirm-database')
    args = parser.parse_args()
    if args.action == 'restore' and not args.file:
        raise ValueError('Restore requires a specific --file')
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%d-%H%M%S')
    file = (args.file or args.directory / f'backup-{timestamp}-{uuid.uuid4().hex[:8]}.tjcb').resolve()
    content = args.content_root.resolve()
    if file.is_relative_to(ROOT / 'dist') or content.is_relative_to(ROOT / 'dist'):
        raise ValueError('Backup and private content must not be stored under dist')
    url = os.environ.get('DATABASE_URL') if args.action == 'backup' else os.environ.get('RESTORE_DATABASE_URL')
    if not url:
        raise ValueError('Set the appropriate database URL in the private environment')
    key = key_bytes(args.key_file)
    if args.action == 'backup':
        if file.exists() or not content.is_dir():
            raise ValueError('Use a new backup filename and existing content root')
        dump = tool('pg_dump', url, ['--format=custom', '--no-owner', '--no-acl'])
        nonce = os.urandom(12)
        encrypted = HEADER + nonce + AESGCM(key).encrypt(nonce, pack(dump, content), AAD)
        file.parent.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(encrypted)
            stream.flush(); os.fsync(stream.fileno())
        print('Encrypted database/content backup created')
    else:
        database_name = urlsplit(url).path.lstrip('/')
        if args.confirm_database != database_name:
            raise ValueError('Explicit target database confirmation is required')
        if content.exists() and any(content.iterdir()):
            raise ValueError('Restore content into a new empty directory')
        with psycopg.connect(url) as connection:
            if connection.execute("SELECT count(*) FROM pg_tables WHERE schemaname='public'").fetchone()[0]:
                raise ValueError('Restore target database must be empty; never replace live transactions')
        raw = file.read_bytes()
        if not raw.startswith(HEADER):
            raise ValueError('Invalid encrypted backup header')
        files = unpack(AESGCM(key).decrypt(raw[5:17], raw[17:], AAD))
        tool('pg_restore', url, ['--no-owner', '--no-acl', '--single-transaction'], files.pop('database.dump'))
        for name, data in files.items():
            target = content / name.removeprefix('content/')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            target.chmod(0o600)
        with psycopg.connect(url) as connection:
            connection.execute('DELETE FROM django_session')
        print('Restored into empty target; sessions invalidated. Keep sales off and reconcile channel history before switching traffic.')

if __name__ == '__main__':
    main()
