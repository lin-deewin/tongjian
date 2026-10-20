"""Clean verified escaped HTML separator artifacts in uploaded translation EPUB text."""
import json
import re
from pathlib import Path

CHAPTER_RE = re.compile(r'(?:^|/)chapter\d+\.htm$')


def clean_translation_text(text, source):
    """Remove stray visible delimiters from translation EPUB chapter text only."""
    if not CHAPTER_RE.search(source or ''):
        return text
    # Exported bold tags survive in a few isolated paragraphs as text markers.
    text = text.replace('B>', '').replace('>/B', '').replace('</B>', '')
    return text.replace('>', '')


def search_text(year):
    return ' '.join(
        [''.join(run['text'] for run in p['runs']) for p in year['paragraphs']]
        + [p['modern'] for p in year.get('bilingual', [])]
        + year.get('translationBlocks', [])
    )


def main():
    root = Path(__file__).resolve().parents[1] / 'dist'
    changed = {}
    newly_missing = __import__('collections').Counter()
    for volume_path in sorted(root.glob('volume[0-9]*.json'), key=lambda p: int(re.search(r'\d+', p.stem)[0])):
        book = json.loads(volume_path.read_text())
        dirty_years = set()
        removed = 0
        for year in book.get('years', []):
            clean_pairs = []
            for pair in year.get('bilingual', []):
                before = pair['modern']
                for source in pair.get('translationFiles', []):
                    pair['modern'] = clean_translation_text(pair['modern'], source)
                if before != pair['modern']:
                    removed += len(before) - len(pair['modern'])
                    dirty_years.add(year['year'])
                visible_text = re.sub(r'^\[\d+\]', '', pair['modern']).strip()
                if not visible_text and before != pair['modern']:
                    indices = pair.get('huIndices', [])
                    if indices:
                        year.setdefault('translationMissing', []).extend(indices)
                        newly_missing[book['volume']] += len(indices)
                    dirty_years.add(year['year'])
                    continue
                clean_pairs.append(pair)
            if len(clean_pairs) != len(year.get('bilingual', [])):
                year['bilingual'] = clean_pairs
            sources = year.get('translationFiles', [])
            if not sources and book.get('volume') == 2:
                sources = ['OPS/chapter2.htm']
            for field in ('translationHeaders', 'translationBlocks'):
                before = year.get(field, [])
                after = [value for value in before]
                for i, value in enumerate(after):
                    for source in sources:
                        after[i] = clean_translation_text(after[i], source)
                if before != after:
                    removed += sum(len(a)-len(b) for a, b in zip(before, after))
                    year[field] = after
                    dirty_years.add(year['year'])
        if not removed and not any(year.get('year') in dirty_years for year in book.get('years', [])):
            continue
        for year in book.get('years', []):
            if year.get('year') in dirty_years and 'translationMissing' in year:
                year['translationMissing'] = sorted(set(year['translationMissing']))
        volume_path.write_text(json.dumps(book, ensure_ascii=False, separators=(',', ':')))
        search_path = root / f"search{book['volume']}.json"
        rows = json.loads(search_path.read_text())
        years_by_key = {y['year']: y for y in book['years']}
        for row in rows:
            if row['year'] in years_by_key:
                row['text'] = search_text(years_by_key[row['year']])
        search_path.write_text(json.dumps(rows, ensure_ascii=False, separators=(',', ':')))
        changed[book['volume']] = {'removed': removed, 'years': sorted(dirty_years)}
    if newly_missing:
        catalog_path = root / 'catalog.json'
        catalog = json.loads(catalog_path.read_text())
        for item in catalog['volumes']:
            if item['volume'] in newly_missing:
                book = json.loads((root / f"volume{item['volume']}.json").read_text())
                item['translationMissing'] = sum(len(y['translationMissing']) for y in book['years'])
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, separators=(',', ':')))
        coverage_path = root / 'coverage.json'
        coverage = json.loads(coverage_path.read_text())
        added = sum(newly_missing.values())
        coverage['matchedOriginal'] -= added
        coverage['uploadedMatchedOriginal'] -= added
        coverage['unmatchedOriginal'] += added
        for item in coverage['volumesWithMissing']:
            if item['volume'] in newly_missing:
                item['missing'] = next(v['translationMissing'] for v in catalog['volumes'] if v['volume'] == item['volume'])
        coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, separators=(',', ':')))
    print(json.dumps(changed, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
