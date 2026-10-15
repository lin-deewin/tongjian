#!/usr/bin/env python3
"""Fail closed on leaked private artifacts or protected paragraph copies in public assets."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from lxml import html

ROOT = Path(__file__).resolve().parents[1]

def normalize(value):
    return re.sub(r'\s+', '', value)

def scan(directory):
    delivery = json.loads((ROOT / 'private-content/truth/current.json').read_text())
    protected = json.loads((ROOT / 'private-content' / delivery['relative_directory'] / 'protected-paragraphs.json').read_text())
    sentinels = [normalize(p) for p in protected]
    failures = []
    private_hashes = {delivery['pdf_sha256'], delivery['article_sha256']}
    for path in directory.rglob('*'):
        if not path.is_file():
            continue
        raw = path.read_bytes()
        relative = str(path.relative_to(directory))
        if path.is_symlink() or hashlib.sha256(raw).hexdigest() in private_hashes or path.suffix.lower() in {'.pdf', '.pem', '.key', '.bak', '.map'}:
            failures.append(relative + ': private/disallowed artifact')
            continue
        if path.suffix.lower() not in {'.html', '.json', '.js', '.svg', '.txt', '.md', '.css'}:
            continue
        text = raw.decode('utf-8', errors='replace')
        if path.suffix.lower() == '.html':
            text = html.fromstring(text).text_content()
        elif path.suffix.lower() == '.json':
            try:
                text = json.dumps(json.loads(text), ensure_ascii=False)
            except ValueError:
                failures.append(relative + ': invalid JSON')
        value = normalize(text)
        if any(p in value for p in sentinels):
            failures.append(relative + ': protected paragraph exposed')
    tree = html.parse(str(directory / 'truth.html'))
    ids = set(tree.xpath('//section/@id'))
    if ids != set(delivery['preview_sections']):
        failures.append('truth.html: preview whitelist mismatch')
    if failures:
        raise SystemExit('\n'.join(failures))
    print(f'Public scan passed: {len(sentinels)} protected paragraphs, no private artifacts')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--directory', type=Path, default=ROOT / 'dist')
    scan(parser.parse_args().directory)
