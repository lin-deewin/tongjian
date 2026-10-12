#!/usr/bin/env python3
"""Summarize Caddy JSON access logs by Asia/Shanghai calendar day."""
import argparse
from collections import Counter
from datetime import datetime, timedelta
import gzip
import json
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--date', default='yesterday', help='today, yesterday or YYYY-MM-DD')
    parser.add_argument('--log-dir', default='/var/log/caddy')
    parser.add_argument('--output-dir', default='/root/projs/tongjian/reports/traffic')
    args = parser.parse_args()
    tz = ZoneInfo('Asia/Shanghai')
    today = datetime.now(tz).date()
    day = today if args.date == 'today' else today - timedelta(days=1) if args.date == 'yesterday' else datetime.strptime(args.date, '%Y-%m-%d').date()
    start = datetime.combine(day, datetime.min.time(), tz).timestamp()
    end = start + 86400
    seconds, visitors, statuses, paths = Counter(), {}, Counter(), Counter()
    malformed = pages = total = 0
    for path in sorted(Path(args.log_dir).glob('tongjian*.log*')):
        opener = gzip.open if path.suffix == '.gz' else open
        with opener(path, 'rt', encoding='utf-8') as source:
            for line in source:
                try:
                    row = json.loads(line)
                    ts = float(row['ts'])
                    req = row['request']
                    uri = urlsplit(req['uri']).path
                except (ValueError, KeyError, TypeError):
                    malformed += 1
                    continue
                if not start <= ts < end or not (uri == '/tongjian' or uri.startswith('/tongjian/')):
                    continue
                total += 1
                seconds[int(ts)] += 1
                statuses[str(row.get('status', 0))] += 1
                paths[uri] += 1
                ip = req.get('client_ip') or req.get('remote_ip') or 'unknown'
                stamp = datetime.fromtimestamp(ts, tz).isoformat()
                visitor = visitors.setdefault(ip, {'ip': ip, 'requests': 0, 'page_views': 0, 'first_seen': stamp, 'last_seen': stamp, 'user_agents': set()})
                visitor['requests'] += 1
                visitor['first_seen'] = min(visitor['first_seen'], stamp)
                visitor['last_seen'] = max(visitor['last_seen'], stamp)
                headers = req.get('headers', {})
                visitor['user_agents'].update(headers.get('User-Agent', []))
                if req.get('method') == 'GET' and uri in ('/tongjian/', '/tongjian/index.html') and row.get('status') in (200, 304):
                    pages += 1
                    visitor['page_views'] += 1
    elapsed = max(1, min(86400, datetime.now(tz).timestamp() - start))
    peak_second, peak = max(seconds.items(), key=lambda item: item[1], default=(None, 0))
    for visitor in visitors.values():
        visitor['user_agents'] = sorted(visitor['user_agents'])
    report = {
        'date': str(day), 'timezone': 'Asia/Shanghai',
        'scope': 'Requests reaching Caddy; includes bots; hash navigation and Cloudflare cache hits are not logged.',
        'requests': total, 'page_views': pages, 'unique_request_ips': len(visitors),
        'unique_page_view_ips': sum(v['page_views'] > 0 for v in visitors.values()),
        'average_qps_full_day': round(total / 86400, 6),
        'average_qps_elapsed': round(total / elapsed, 6),
        'peak_qps_1s': peak,
        'peak_second': datetime.fromtimestamp(peak_second, tz).isoformat() if peak_second else None,
        'status_counts': dict(statuses), 'top_paths': paths.most_common(20),
        'malformed_lines': malformed,
        'visitors': sorted(visitors.values(), key=lambda v: v['requests'], reverse=True),
    }
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    destination = output / (str(day) + '.json')
    temp = destination.with_suffix('.tmp')
    temp.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    temp.chmod(0o600)
    temp.replace(destination)
    print(json.dumps({k: v for k, v in report.items() if k not in ('visitors', 'top_paths')}, ensure_ascii=False, indent=2))
    print('Report:', destination)


if __name__ == '__main__':
    main()
