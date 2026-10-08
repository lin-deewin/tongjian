#!/usr/bin/env python3
"""Align the uploaded bilingual edition against the extracted second volume."""
import argparse
import difflib
import json
import re
import zipfile
from pathlib import Path

from lxml import html


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--epub', type=Path, required=True)
parser.add_argument('--data', type=Path, required=True)
parser.add_argument('--index', type=Path,
                    default=Path(__file__).with_name('volume2-index.json'))
args = parser.parse_args()
event_index = json.loads(args.index.read_text(encoding='utf-8'))


def normalize(text):
    text = re.sub(r'^\[\d+\]', '', text.strip())
    return re.sub(r'[^\u4e00-\u9fff]', '', text).replace('崐', '')


with zipfile.ZipFile(args.epub) as epub:
    chapter = html.fromstring(epub.read('OPS/chapter2.htm'))
    source_paragraphs = chapter.xpath('//h3')[0].itersiblings('p')
    texts = []
    for paragraph in source_paragraphs:
        text = ' '.join(paragraph.text_content().split())
        if text.startswith('---'):
            break
        texts.extend(part.strip() for part in text.split('*') if part.strip())

translated = {}
year = None
year_heading = re.compile(r'^(?:周纪二\s*)?(?:周)?(?:显王)?[元一二三四五六七八九十]+年')
for text in texts:
    match = re.search(r'前(\d{3})', text)
    if match and len(text) < 100 and year_heading.match(text):
        year = int(match.group(1))
        translated.setdefault(year, {'headers': [], 'tokens': []})['headers'].append(text)
        continue
    if year is None:
        continue
    # A few source paragraphs contain more than one indexed passage.
    parts = re.split(r'(?=\[\d+\])', text)
    translated[year]['tokens'].extend(part.strip() for part in parts if part.strip())

book = json.loads(args.data.read_text(encoding='utf-8'))
report = []
for item in book['years']:
    edition = translated.get(item['year'], {'headers': [], 'tokens': []})
    tokens = edition['tokens']
    if len(tokens) % 2:
        raise ValueError(f"year {item['year']} has {len(tokens)} unpaired translation passages")
    pairs, used, cursor = [], set(), 0
    paragraphs = item['paragraphs']
    for index in range(0, len(tokens), 2):
        original, modern = tokens[index:index + 2]
        best_score, best_indices = 0, []
        for start in range(cursor, len(paragraphs)):
            for size in range(1, 5):
                indices = list(range(start, min(start + size, len(paragraphs))))
                if not indices:
                    continue
                joined = ''.join(paragraphs[i]['plain'] for i in indices)
                score = difflib.SequenceMatcher(
                    None, normalize(original), normalize(joined), autojunk=False
                ).ratio()
                if score > best_score:
                    best_score, best_indices = score, indices
        matched = best_score >= 0.65
        if matched:
            used.update(best_indices)
            cursor = best_indices[-1] + 1
        pairs.append({
            'huIndices': best_indices if matched else [],
            'sourceOriginal': original,
            'modern': re.sub(r'^\[\d+\]', '', modern).strip(),
            'score': round(best_score, 3),
            'kind': 'commentary' if re.sub(r'^\[\d+\]', '', original).lstrip().startswith(
                ('臣光曰', '太史公曰')) else 'record',
            'difference': not matched,
        })

    item['bilingual'] = pairs
    item['translationHeaders'] = edition['headers']
    item['translationMissing'] = [i for i in range(len(paragraphs)) if i not in used]
    translation_warnings = {
        357: '上传译本的古文与白话在会盟地名处缺字；胡注本作“鄗”。两栏分别保留来源字样。',
        336: '上传译本写“孟轲拜孔为师”，胡注本作“孟子师子思”；两栏分别保留来源字样。',
    }
    if item['year'] in translation_warnings:
        item['translationWarning'] = translation_warnings[item['year']]
    context_notes = {
        359: '本年叙述包含新法施行十年等后续成效；按原书次序保留，不将全部叙事视为当年发生。',
        321: '孟尝君袭封、养士与出使楚国等附叙包含后续经历；按原书编排留在本年，不将全部叙事视为前321年发生。',
    }
    if item['year'] in context_notes:
        item['contextNote'] = context_notes[item['year']]
    indexed = [pair for pair in pairs if not pair['difference']]
    events = event_index.get(str(item['year']), [])
    if bool(events) != item['recorded']:
        raise ValueError(f"missing or unexpected event index in {item['year']}")
    if any(not 0 <= e['anchor'] < len(paragraphs) for e in events):
        raise ValueError(f"event anchor outside source paragraphs in {item['year']}")
    item['titles'] = [e['title'] for e in events]
    item['anchors'] = [e['anchor'] for e in events]
    report.append({
        'year': item['year'],
        'translation_pairs': len(pairs),
        'aligned': len(indexed),
        'differences': [p['sourceOriginal'] for p in pairs if p['difference']],
        'missing_paragraphs': item['translationMissing'],
        'lowest_score': min((p['score'] for p in indexed), default=None),
    })

book['translationSource'] = (
    '上传的《资治通鉴全译本柏杨版》EPUB · OPS/chapter2.htm（文件署名，未另作版本鉴定）'
)
args.data.write_text(json.dumps(book, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
