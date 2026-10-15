#!/usr/bin/env python3
"""Verify the public mail DNS records without DNS administration credentials."""
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def lookup(name, kind):
    query = urlencode({'name': name, 'type': kind})
    request = Request('https://cloudflare-dns.com/dns-query?' + query,
                      headers={'Accept': 'application/dns-json'})
    with urlopen(request, timeout=15) as response:
        payload = json.load(response)
    if payload.get('Status') not in (0, 3):
        raise RuntimeError(f'DNS lookup failed for {name} ({kind})')
    return [answer['data'] for answer in payload.get('Answer', [])
            if answer['type'] == {'A': 1, 'MX': 15, 'TXT': 16, 'PTR': 12}[kind]]


def normalized_txt(value):
    # Cloudflare uses DNS presentation strings, including decimal escapes and
    # multiple quoted chunks for long TXT records. Preserve spaces between words.
    if value.startswith('"'):
        chunks = re.findall(r'"((?:[^"\\]|\\.)*)"', value)
        value = ''.join(re.sub(r'\\([0-9]{3}|.)',
                              lambda m: chr(int(m[1])) if m[1].isdigit() and len(m[1]) == 3 else m[1],
                              chunk) for chunk in chunks)
    # DKIM allows folded whitespace in its base64 public key.
    if value.startswith(('v=DKIM1;', 'v=DMARC1;')):
        tags = {}
        for field in value.split(';'):
            if '=' not in field:
                continue
            key, content = field.split('=', 1)
            tags[key.strip()] = ''.join(content.split()) if key.strip() == 'p' else content.strip()
        return tags
    return ' '.join(value.split())


def main():
    config = json.loads(Path(__file__).with_name('dns-records.json').read_text())
    checks = []
    for record in config['records']:
        name = config['zone'] if record['name'] == '@' else record['name'] + '.' + config['zone']
        values = lookup(name, record['type'])
        expected = record['content']
        if record['type'] == 'TXT':
            values = [normalized_txt(value) for value in values]
            expected = normalized_txt(expected)
        if record['type'] == 'MX':
            expected = str(record['priority']) + ' ' + expected
            values = [value.rstrip('.') for value in values]
        checks.append({'name': name, 'type': record['type'],
                       'matches': expected in values,
                       'answer_count': len(values)})
    reverse = ipaddress.ip_address('104.129.181.27').reverse_pointer
    ptr = lookup(reverse, 'PTR')
    ready = all(check['matches'] for check in checks)
    print(json.dumps({'dns_records_ready': ready, 'records': checks,
                      'ptr': ptr, 'ptr_matches': 'mail.deewins.top.' in ptr}, indent=2))
    return 0 if ready else 2


if __name__ == '__main__':
    sys.exit(main())
