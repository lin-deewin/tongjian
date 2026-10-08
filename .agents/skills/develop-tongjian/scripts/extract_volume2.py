#!/usr/bin/env python3
"""Extract volume two from the two supplied editions' source structure."""
import argparse
import json
import re
import zipfile
from pathlib import Path

from lxml import html


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--epub', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
malformed_notes = set()


def split_runs(text):
    runs, buffer, depth, kind = [], '', 0, 'text'
    for pos, char in enumerate(text):
        if char == '〔' and depth and text[pos:].startswith(('〔【章：', '〔今此书年')):
            buffer += char
            continue
        if char == '〔':
            if depth == 0:
                if buffer:
                    runs.append({'kind': 'text', 'text': buffer})
                buffer, kind = '', 'note'
            depth += 1
            buffer += char
        elif char == '〕':
            buffer += char
            depth -= 1
            if depth == 0:
                runs.append({'kind': 'note', 'text': buffer})
                buffer, kind = '', 'text'
        else:
            buffer += char
    if depth:
        malformed_notes.add(text)
        # This EPUB has one paragraph whose final note lacks its closing glyph.
        # Keep its bytes visible to the note toggle without inventing a glyph.
        if depth == 1 and buffer.startswith('〔'):
            runs.append({'kind': 'note', 'text': buffer})
            buffer = ''
        else:
            return [{'kind': 'text', 'text': text}]
    if buffer:
        runs.append({'kind': kind, 'text': buffer})
    if ''.join(run['text'] for run in runs) != text:
        raise AssertionError('source paragraph was not reconstructed exactly')
    return runs


def plain_text(text):
    return ''.join(run['text'] for run in split_runs(text) if run['kind'] == 'text')


digits = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6,
          '七': 7, '八': 8, '九': 9, '十': 10}


def number(text):
    if text == '元':
        return 1
    if '十' not in text:
        return digits[text]
    left, right = text.split('十')
    return (digits[left] if left else 1) * 10 + (digits[right] if right else 0)


with zipfile.ZipFile(args.epub) as epub:
    root = html.fromstring(epub.read('OEBPS/text00004.html'))
    source_paragraphs = [p.text_content() for p in root.xpath('//p')]

years = [
    {'year': year, 'king': '显王', 'reign': 369 - year, 'heading': '',
     'headingRuns': [], 'paragraphs': [], 'after': [], 'titles': [],
     'anchors': [], 'bilingual': [], 'translationHeaders': [],
     'translationMissing': []}
    for year in range(368, 320, -1)
]
by_year = {year['year']: year for year in years}
intro, current = [], None
for text in source_paragraphs:
    plain = plain_text(text)
    heading = re.fullmatch(r'([元一二三四五六七八九十]+)年', plain)
    if heading:
        current = by_year[369 - number(heading.group(1))]
        current['heading'] = text
        current['headingRuns'] = split_runs(text)
    elif current:
        current['paragraphs'].append({'runs': split_runs(text), 'plain': plain})
        if text in malformed_notes:
            current['sourceWarning'] = (
                '本年孟子见魏惠王一段的末尾胡注缺少右括号；'
                '原文字符完整保留，未补写括号。'
            )
    else:
        intro.append({'runs': split_runs(text), 'plain': plain})

for year in years:
    year['recorded'] = bool(year['paragraphs'])
    year['search'] = ' '.join(p['plain'] for p in year['paragraphs'])
    year['noteCount'] = sum(r['kind'] == 'note' for p in year['paragraphs'] for r in p['runs'])

preserved = sum(bool(y['heading']) + len(y['paragraphs']) for y in years) + len(intro)
if preserved != len(source_paragraphs):
    raise AssertionError(f'preserved {preserved} of {len(source_paragraphs)} source paragraphs')
if [y['year'] for y in years if y['heading']] != [
        368, 366, 365, 364, 362, 361, 359, 358, 357, 356, 355, 354, 353,
        352, 351, 350, 348, 347, 346, 344, 343, 341, 340, 338, 337, 336,
        335, 334, 333, 332, 330, 329, 328, 327, 326, 325, 324, 323, 322, 321]:
    raise AssertionError('volume two year headings do not match the 48-year sequence')

book = {
    'volume': 2,
    'title': root.xpath('//h3')[0].text_content(),
    'subtitle': '周显王元年—四十八年 · 商鞅变法与战国诸侯争衡',
    'source': '上传的《资治通鉴 胡三省注版》EPUB · OEBPS/text00004.html',
    'intro': intro,
    'years': years,
    'sourceWarnings': [
        f'胡注本有 {len(malformed_notes)} 段注释括号不完整；原文字符完整保留，未自动修补。'
    ] if malformed_notes else [],
}
args.output.write_text(json.dumps(book, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(json.dumps({'volume': 2, 'years': 48, 'recorded': sum(y['recorded'] for y in years),
                  'paragraphs': len(source_paragraphs), 'intro': len(intro),
                  'empty_years': [y['year'] for y in years if not y['recorded']],
                  'malformed_note_paragraphs': len(malformed_notes),
                  'source_preserved': True}, ensure_ascii=False))
