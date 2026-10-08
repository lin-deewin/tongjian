#!/usr/bin/env python3
"""Validate volume coverage, text runs, anchors, and translation alignment."""
import argparse
import json
from pathlib import Path


def check(book):
    years = book['years']
    assert years, 'no years'
    nums = [y['year'] for y in years]
    assert len(set(nums)) == len(nums), 'duplicate years'
    assert nums == [n for n in range(nums[0], nums[-1] - 1, -1) if n], 'year gap'
    if book.get('volume') == 1:
        assert nums == list(range(403, 368, -1)), 'wrong first-volume range'
    pairs = differences = 0
    for y in years:
        ps = y['paragraphs']
        assert y['recorded'] == bool(ps), 'recorded flag mismatch'
        assert len(y['anchors']) == len(y['titles']), 'index length mismatch'
        assert all(0 <= a < len(ps) for a in y['anchors']), 'anchor out of range'
        for p in ps:
            assert all(r['kind'] in ('text', 'note') for r in p['runs'])
            plain = ''.join(r['text'] for r in p['runs'] if r['kind'] == 'text')
            assert plain == p['plain'], 'plain text mismatch'
        if 'bilingual' not in y:
            continue
        seen = set()
        for pair in y['bilingual']:
            pairs += 1
            assert pair['modern'] and pair['sourceOriginal'], 'empty pair'
            if pair['difference']:
                differences += 1
                assert not pair['huIndices'], 'difference matches a paragraph'
                continue
            assert pair['huIndices'], 'unmarked unmatched pair'
            assert pair['score'] >= 0.65, 'low-confidence match'
            for i in pair['huIndices']:
                assert 0 <= i < len(ps), 'paragraph out of range'
                assert i not in seen, 'duplicate paragraph mapping'
                seen.add(i)
        missing = sorted(set(range(len(ps))) - seen)
        assert missing == sorted(y['translationMissing']), 'missing mismatch'
        if book.get('volume', 1) <= 10:
            assert not missing, f"untranslated verified baseline {y['year']}"
    return {'years': len(years), 'recorded': sum(y['recorded'] for y in years),
            'translation_pairs': pairs, 'source_differences': differences,
            'unmatched_original': sum(len(y.get('translationMissing', [])) for y in years)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = check(json.loads(args.data.read_text(encoding='utf-8')))
    except (AssertionError, KeyError, ValueError) as exc:
        parser.exit(1, f'Validation failed: {exc}\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
