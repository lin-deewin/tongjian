#!/usr/bin/env python3
"""Record public SEO reachability. This does not measure indexing or search traffic."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, build_opener, HTTPRedirectHandler
import xml.etree.ElementTree as ET

BASE = 'https://deewins.top/'
REPRESENTATIVES = ['', 'reading.html', 'volume/', 'people/', 'volume/1/', 'volume/113/',
                   'volume/200/', 'volume/294/', 'people/p-73bb90f91552/', 'people/yue-yi/',
                   'history/xiao-he-guanzhong/', 'history/yue-yi-qi-campaign/', 'research.html']


class Head(HTMLParser):
    def __init__(self):
        super().__init__()
        self.canonical, self.robots, self.h1, self.title = [], [], 0, ''
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'link' and 'canonical' in a.get('rel', '').split():
            self.canonical.append(a.get('href', ''))
        if tag == 'meta' and a.get('name', '').lower() == 'robots':
            self.robots.append(a.get('content', ''))
        self.h1 += tag == 'h1'
        if tag == 'title':
            self.in_title = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(url, redirect=True):
    req = Request(url, headers={'User-Agent': 'TongjianSEOCheck/1.0 (+https://deewins.top/)'})
    try:
        with build_opener(*([] if redirect else [NoRedirect])).open(req, timeout=25) as response:
            return response.status, dict(response.headers), response.read(), response.url
    except HTTPError as exc:
        return exc.code, dict(exc.headers), exc.read(), exc.url


def page(url):
    try:
        status, headers, raw, final = fetch(url)
        head = Head()
        head.feed(raw.decode('utf-8'))
        headers = {k.lower(): v for k, v in headers.items()}
        return dict(url=url, status=status, finalURL=final, title=head.title,
                    canonical=head.canonical, h1=head.h1, metaRobots=head.robots,
                    xRobotsTag=headers.get('x-robots-tag'), bytes=len(raw))
    except (OSError, URLError, UnicodeError, ValueError) as exc:
        return dict(url=url, error=str(exc))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--full', action='store_true', help='Fetch every sitemap URL instead of representative pages')
    parser.add_argument('--output-dir', default='reports/seo-observation')
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    report = dict(checkedAt=now.isoformat(), origin=BASE, platformData='not-connected',
                  indexingStatus='unknown', searchClicks=None, searchImpressions=None,
                  scope='Public HTTP responses only; not search-engine indexing, rankings or visitors.', errors=[])
    try:
        status, headers, raw, _ = fetch(BASE + 'robots.txt')
        text = raw.decode('utf-8')
        headers = {k.lower(): v for k, v in headers.items()}
        correct = status == 200 and 'User-agent:' in text and 'Sitemap: ' + BASE + 'sitemap.xml' in text
        report['robots'] = dict(status=status, correct=correct, body=text,
                                cache=headers.get('cf-cache-status'), edge=headers.get('cf-ray'), age=headers.get('age'))
        if not correct:
            report['errors'].append('Domain-root robots is missing/incorrect or still cached')
        status, _, raw, _ = fetch(BASE + 'sitemap.xml')
        tree = ET.fromstring(raw)
        urls = [n.text for n in tree.findall('{*}url/{*}loc')]
        valid = status == 200 and tree.tag.endswith('}urlset') and bool(urls) and len(urls) == len(set(urls))
        valid = valid and all(u.startswith(BASE) and not u.startswith(BASE+'tongjian/') and '#' not in u for u in urls)
        report['sitemap'] = dict(status=status, valid=valid, urls=len(urls))
        if not valid:
            report['errors'].append('Invalid sitemap or noncanonical URL')
        selected = urls if args.full else [BASE + p for p in REPRESENTATIVES]
        with ThreadPoolExecutor(max_workers=6) as pool:
            report['pages'] = list(pool.map(page, selected))
        for row in report['pages']:
            noindex = 'noindex' in ','.join(row.get('metaRobots', []) + [row.get('xRobotsTag') or '']).lower()
            if row.get('status') != 200 or row.get('canonical') != [row['url']] or row.get('h1') != 1 or noindex:
                report['errors'].append('Page failed: ' + row['url'])
        status, headers, _, _ = fetch(BASE + 'tongjian/reader.html?seo=check', redirect=False)
        location = next((v for k, v in headers.items() if k.lower() == 'location'), '')
        report['legacyRedirect'] = dict(status=status, location=location)
        if status not in (301, 308) or location != BASE + 'reader.html?seo=check':
            report['errors'].append('Old reader URL does not permanently map to root URL with its query')
    except (OSError, URLError, UnicodeError, ValueError, ET.ParseError) as exc:
        report['errors'].append(str(exc))
    report['status'] = 'passed' if not report['errors'] else 'needs-attention'
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = output / (now.strftime('%Y%m%dT%H%M%SZ') + '.json')
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    destination.chmod(0o600)
    latest = output / 'latest.json'
    temp = output / 'latest.tmp'
    temp.write_text(destination.read_text())
    temp.chmod(0o600)
    temp.replace(latest)
    print(json.dumps(dict(status=report['status'], errors=report['errors'], report=str(destination)), ensure_ascii=False))
    return 0 if not report['errors'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
