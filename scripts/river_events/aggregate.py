"""Validate and aggregate ten Luna review files without upgrading provisional records."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIRECTORY = Path(__file__).parent
KINDS = {'disaster', 'famine', 'war'}


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')



def chinese_year_number(text):
    values={'元':1,'一':1,'二':2,'两':2,'兩':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9,'十':10}
    if text in values:return values[text]
    if '十' in text:
        left,right=text.split('十',1);return (values.get(left,1)*10 if left else 10)+values.get(right,0)
    return None

def build():
    books = {}
    corpus_hash = hashlib.sha256()
    for volume in range(1, 295):
        raw = (ROOT / f'dist/volume{volume}.json').read_bytes()
        corpus_hash.update(raw)
        books[volume] = json.loads(raw)
    source_years = {(v, y['year']): y for v, b in books.items() for y in b['years']}
    rows = {}
    for (v, year), source in source_years.items():
        row = rows.setdefault(year, dict(year=year, dynasty=source.get('dynasty', books[v].get('dynasty', '周')), volumes=[], events=[], pending=0))
        row['volumes'].append(v)
    signatures = {}
    pending_signatures = set()
    agents = []
    excluded = 0
    exclusion_reason_gaps = 0
    for batch in range(1, 11):
        path = DIRECTORY / f'review-{batch:02}.json'
        review = json.loads(path.read_text())
        expected = [(batch - 1) * 30 + 1, min(batch * 30, 294)]
        assert review['range'] == expected, (path, 'range')
        candidates = json.loads((ROOT / f'artifacts/river-audit/candidates-{batch:02}.json').read_text())
        candidate_ids = {c['id'] for c in candidates}
        coverage = review['coverage']
        reviewed_ids = set(coverage.get('reviewedCandidateIds', []))
        assert coverage['candidateParagraphs'] == len(candidates), (path, 'candidate count')
        assert coverage['modelReviewedParagraphs'] == len(reviewed_ids), (path, 'audit count must be backed by IDs')
        counts = Counter()
        ids = set()
        decided_candidate_ids = set()
        for event in review['events']:
            assert event['id'] not in ids, (path, 'duplicate event ID', event['id'])
            ids.add(event['id'])
            assert event['status'] in {'reviewed', 'provisional'}, (path, event['id'])
            assert event['year'] in rows and event['year'] != 0
            assert isinstance(event['title'], str) and event['title'].strip()
            assert event['categories'] and set(event['categories']) <= KINDS
            assert event['sources'], (path, 'missing source', event['id'])
            normalized_sources = []
            for source in event['sources']:
                v, y, a, quote = (source[k] for k in ('volume', 'year', 'anchor', 'quote'))
                assert expected[0] <= v <= expected[1]
                if y != event['year']:
                    if event['status'] == 'provisional':
                        continue
                    assert event.get('dateBasis'), (path, 'missing explicit historical date basis', event['id'])
                    previous = 1 if y == -1 else y + 1
                    relative = any(word in quote for word in ('去岁', '去歲', '去年', '去冬'))
                    source_reign = source_years[v, y].get('reign')
                    regnal = None
                    import re
                    marker = re.search(r'(元|[一二两兩三四五六七八九十]+)年', quote)
                    if marker:
                        regnal = chinese_year_number(marker.group(1))
                    if relative:
                        assert event['year'] == previous, (path, 'relative year mismatch', event['id'])
                    else:
                        assert event.get('dateEvidence') == 'regnalYear' and isinstance(source_reign, int) and regnal, (path, 'unsupported historical date shift', event['id'])
                        offset = source_reign-regnal
                        computed = y + offset if y < 0 else y-offset
                        assert event['year'] == computed, (path, 'regnal year arithmetic mismatch', event['id'])
                assert isinstance(a, int) and 0 <= a < len(source_years[v, y]['paragraphs']), (path, 'bad source anchor', event['id'])
                paragraph = source_years[v, y]['paragraphs'][a]
                assert isinstance(quote, str) and quote.strip() and quote in paragraph['plain'], (path, 'quote mismatch', event['id'])
                assert not paragraph.get('structural'), (path, 'structural source', event['id'])
                if event['status'] == 'reviewed':
                    assert f'v{v}-y{y}-p{a}' in reviewed_ids, (path, 'reviewed event source was not audited', event['id'])
                candidate_id = source.get('candidateId', f'v{v}-y{y}-p{a}')
                if candidate_id in candidate_ids:
                    decided_candidate_ids.add(candidate_id)
                normalized_sources.append(dict(volume=v, year=y, anchor=a, quote=quote, candidateId=candidate_id))
            counts[event['status']] += 1
            # Same exact textual action is one event even when an agent repeats it.
            signature = (event['year'], tuple(sorted(set(s['quote'] for s in normalized_sources))))
            if event['status'] == 'provisional':
                pending_signatures.add(signature)
                continue
            if signature in signatures:
                existing = signatures[signature]
                existing['categories'] = sorted(set(existing['categories']) | set(event['categories']))
                for source in normalized_sources:
                    if source not in existing['sources']:
                        existing['sources'].append(source)
                continue
            first = normalized_sources[0]
            stable = 'event-' + hashlib.sha256(repr(signature).encode()).hexdigest()[:16]
            item = dict(id=stable, year=event['year'], categories=sorted(set(event['categories'])), title=event['title'], sources=normalized_sources, volume=first['volume'], anchor=first['anchor'], status='modelReviewed')
            if event.get('dateBasis'):
                item['dateBasis'] = event['dateBasis']
            if event.get('dateEvidence'):
                item['dateEvidence'] = event['dateEvidence']
            signatures[signature] = item
            rows[event['year']]['events'].append(item)
        excluded_rows = review.get('excluded', [])
        excluded += len(excluded_rows)
        exclusion_reason_gaps += sum(
            '原因记录' in item.get('reason', '') and '丢失' in item.get('reason', '')
            for item in excluded_rows
        )
        for item in excluded_rows:
            if item.get('candidateId') in candidate_ids:
                decided_candidate_ids.add(item['candidateId'])
        unresolved = len(candidate_ids-decided_candidate_ids)
        agents.append(dict(batch=batch, volumes=expected, candidates=len(candidates), decidedCandidates=len(decided_candidate_ids), undecidedCandidates=unresolved, modelReviewedParagraphs=len(reviewed_ids), supplementalReviewedParagraphs=len(reviewed_ids-candidate_ids), eventCounts=dict(counts), method=coverage.get('method', ''), fullTextReviewedParagraphs=len(coverage.get('fullTextReviewedCandidateIds', [])), excerptReviewedParagraphs=max(0,len(reviewed_ids)-len(coverage.get('fullTextReviewedCandidateIds', []))), limitations=coverage.get('limitations', [])))
    pending_signatures -= signatures.keys()
    for signature in pending_signatures:
        rows[signature[0]]['pending'] += 1
    ordered = sorted(rows.values(), key=lambda r: -r['year'])
    for row in ordered:
        row['events'].sort(key=lambda e: (e['volume'], e['anchor'], e['id']))
    events = [e for r in ordered for e in r['events']]
    reviewed = sum(a['modelReviewedParagraphs'] for a in agents)
    supplemental = sum(a['supplementalReviewedParagraphs'] for a in agents)
    candidates = sum(a['candidates'] for a in agents)
    limitations = ['模型复核不是人工史学终审，分类与拆并仍可能有误。', '同一年度不同战斗行动分别记；同事件多类别合并为一个点。', '未逐条核实的候选不绘为事件点；空白不代表当年没有事件。', '事件点在远景可能重叠，没有按年截断。']
    if exclusion_reason_gaps:
        limitations.append(f'批次07的{exclusion_reason_gaps}条排除理由记录在一次误操作中丢失；候选归属已按事件来源差集恢复，但这些段落的具体排除理由无法恢复。')
    summary = dict(schemaVersion=3, unit='按年具体事件；跨年战事按年分别记录', reviewers=dict(model='gpt-6-luna', reasoningEffort='low', agents=10), corpusSHA256=corpus_hash.hexdigest(), candidateParagraphs=candidates, modelReviewedParagraphs=reviewed, supplementalReviewedParagraphs=supplemental, candidatesWithEventOrExclusion=sum(a['decidedCandidates'] for a in agents), unclassifiedCandidates=sum(a['undecidedCandidates'] for a in agents), candidateParagraphsSemanticallyReviewed=sum(a['modelReviewedParagraphs']-a['supplementalReviewedParagraphs'] for a in agents), unreviewedCandidateParagraphs=candidates-sum(a['modelReviewedParagraphs']-a['supplementalReviewedParagraphs'] for a in agents), modelReviewedEvents=len(events), pendingCandidates=len(pending_signatures), categoryCounts=dict(Counter(k for e in events for k in e['categories'])), excludedCandidates=excluded, scope='关键词宽召回候选；未命中的原文尚未全量语义复核', completeness='completeCandidateReview' if reviewed == candidates else 'partialCandidateReview', limitations=limitations, agents=agents)
    dump(ROOT / 'dist/river-data.json', dict(schemaVersion=3, summary={k:v for k,v in summary.items() if k != 'agents'}, years=ordered))
    dump(ROOT / 'dist/river-audit-report.json', summary)
    dump(ROOT / 'dist/river-events.json', dict(schemaVersion=1, events=events))
    print(json.dumps({k:v for k,v in summary.items() if k not in {'agents','limitations'}}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    build()
