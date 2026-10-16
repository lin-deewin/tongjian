#!/usr/bin/env python3
"""Normalize actual GSC/Baidu CSV exports; never infer search metrics from server logs."""
import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path

ALIASES = {
    'clicks': ['clicks', '点击次数', '点击量', '点击'],
    'impressions': ['impressions', '展示次数', '展现量', '展现', '曝光量'],
    'date': ['date', '日期'],
    'page': ['page', 'pages', 'top pages', '热门网页', '网页', '页面', 'url', '链接'],
    'query': ['query', 'queries', 'top queries', '热门查询', '查询', '关键词', '搜索词'],
    'position': ['position', 'average position', '平均排名', '排名'],
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', required=True, choices=['gsc', 'baidu'])
    parser.add_argument('--input', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    raw = args.input.read_bytes()
    text = None
    for encoding in (['utf-16'] if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else ['utf-8-sig', 'gb18030']):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            pass
    if text is None:
        raise ValueError('Could not decode CSV; export as UTF-8 CSV')
    reader = csv.DictReader(io.StringIO(text))
    columns = {k: next((name for name in (reader.fieldnames or []) if name.strip().lower() in aliases), None)
               for k, aliases in ALIASES.items()}
    if not columns['clicks'] or not columns['impressions']:
        raise ValueError('CSV must include recognized clicks and impressions columns; do not substitute visits')
    records = []
    for number, row in enumerate(reader, 2):
        if not any(row.values()):
            continue
        item = {}
        for key, column in columns.items():
            if not column:
                continue
            value = row[column].strip()
            if key in ('clicks', 'impressions', 'position'):
                try:
                    numeric = Decimal(value.replace(',', ''))
                except InvalidOperation:
                    raise ValueError(f'Invalid {key} on CSV line {number}') from None
                if not numeric.is_finite() or numeric < 0 or key != 'position' and numeric != int(numeric):
                    raise ValueError(f'Invalid {key} on CSV line {number}')
                item[key] = float(numeric) if key == 'position' else int(numeric)
            else:
                item[key] = value
        records.append(item)
    clicks = sum(r['clicks'] for r in records)
    impressions = sum(r['impressions'] for r in records)
    output = dict(platform=args.platform, importedAt=datetime.now(timezone.utc).isoformat(),
                  sourceFile=args.input.name, sourceSHA256=hashlib.sha256(raw).hexdigest(),
                  scope='Exported rows only; may omit hidden/anonymized or truncated rows. Not full-site totals unless the export establishes that scope.',
                  dimensions=[k for k in ('date', 'page', 'query') if columns[k]], records=records,
                  exportedRowsSummary=dict(rows=len(records), clicks=clicks, impressions=impressions,
                                           ctr=clicks/impressions if impressions else None))
    args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    args.output.chmod(0o600)
    print(json.dumps(output['exportedRowsSummary'], ensure_ascii=False))


if __name__ == '__main__':
    main()
