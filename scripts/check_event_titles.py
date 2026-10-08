"""Check source-bound reviewed headings and synchronization of browsing/search indexes."""
import json
from pathlib import Path
from summarize_event_titles import clean, digest, summarize

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'
overrides = json.loads((ROOT / 'scripts/event-title-overrides.json').read_text())
assert clean('>[12]>十一月，丁卯朔（初一），武氏受册') == '武氏受册'
assert summarize('[1]冬季，十月。齐悼惠王来朝。', '齐悼惠王来朝。') == '齐悼惠王来朝'
assert summarize('>[3]>春季，正月，秦国攻打魏国。', '秦伐魏。') == '秦攻魏'
assert summarize('>', '王朴上书论礼乐。') == '王朴上书论礼乐'
assert '司马光论' in summarize('臣光曰：君主治国，应以信誉为重。', '')

count = reviewed_count = 0
for volume in range(1, 295):
    b = json.loads((DIST / f'volume{volume}.json').read_text())
    rows = json.loads((DIST / f'search{volume}.json').read_text())
    for y, row in zip(b['years'], rows, strict=True):
        assert y['year'] == row['year']
        assert y['anchors'] == row['anchors']
        assert y['titles'] == row['titles']
        assert len(y['titles']) == len(y['anchors'])
        for anchor, title in zip(y['anchors'], y['titles'], strict=True):
            if volume == 1:
                continue
            count += 1
            assert 2 <= len(title) <= 36, (volume, y['year'], anchor, title)
            assert not any(c in title for c in '>…\n'), (volume, title)
            entry = overrides.get(str(volume), {}).get(f"{y['year']}:{anchor}")
            if entry:
                reviewed_count += 1
                assert entry['title'] == title
                assert entry['sourceHash'] == digest(y['paragraphs'][anchor])
                if entry.get('reviewStatus') == 'rewritten':
                    group = next((p['huIndices'] for p in y.get('bilingual', [])
                                  if not p.get('difference') and p.get('huIndices')
                                  and p['huIndices'][0] == anchor), [anchor])
                    assert entry['reviewedIndices'] == group
                    assert entry['groupHash'] == digest([y['paragraphs'][i] for i in group])
assert count == 30402
assert reviewed_count == sum(len(rows) for rows in overrides.values())
report = json.loads((DIST / 'event-title-report.json').read_text())
verified = sum(1 for rows in overrides.values() for row in rows.values() if row.get('reviewStatus') == 'rewritten')
assert report['rewritten'] == verified and not report['longTitles']
print(f'PASS: {count} titles synchronized with search; {verified} manually rewritten titles bound to source passages; dates, blank markers, title lengths and stable anchors.')
