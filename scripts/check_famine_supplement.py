"""Regression checks for famine evidence, chronology, exclusions and rebuilds."""
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from river_events.famine_supplement import apply
from river_events.aggregate import build
ROOT=Path(__file__).resolve().parents[1]

def main():
    data=json.loads((ROOT/'dist/river-data.json').read_text())
    report=json.loads((ROOT/'dist/famine-audit-report.json').read_text())
    events=json.loads((ROOT/'dist/river-events.json').read_text())['events']
    assert events == [e for y in data['years'] for e in y['events']]
    assert len({e['id'] for e in events}) == len(events)
    books={v:json.loads((ROOT/f'dist/volume{v}.json').read_text()) for v in range(1,295)}
    years={(v,y['year']):y for v,b in books.items() for y in b['years']}
    for e in events:
        assert e['year'] and e['sources'] and e['categories']
        for s in e['sources']:
            p=years[s['volume'],s['year']]['paragraphs'][s['anchor']]
            assert not p.get('structural') and s['quote'] in p['plain']
            assert s['candidateId']==f'v{s["volume"]}-y{s["year"]}-p{s["anchor"]}'
            if e['id'].startswith('famine-supplement-') and s['year'] != e['year']:
                assert e['year']==(1 if s['year']==-1 else s['year']+1)
                assert '去岁' in s['quote']
    assert Counter(k for e in events for k in e['categories']) == Counter(data['summary']['categoryCounts'])
    famine=[e for e in events if 'famine' in e['categories']]
    assert len(famine)==report['famineCount']==247
    assert len({e['year'] for e in famine})==report['famineYearCount']==202
    assert 190+report['addedEvents']-report['mergedFamineEntries']-report['removedFamineClassifications']==247
    def at(cid):return [e for e in famine if any(s['candidateId']==cid for s in e['sources'])]
    assert len(at('v220-y-757-p14'))==1 and len(at('v219-y-757-p43'))==1
    assert at('v220-y-757-p14')[0]['id']==at('v219-y-757-p43')[0]['id']
    assert len(at('v19-y120-p4'))==1 and len(at('v240-y-817-p9'))==1
    assert not at('v8-y207-p8')  # Field army supply failure.
    assert not at('v249-y-857-p10')  # Explicitly appended retrospective story.
    assert not at('v1-y403-p14')  # Pre-403 introduction must not be dated 403.
    assert not at('v289-y-950-p3')  # Burial of earlier famine victims.
    assert at('v89-y-314-p5')[0]['year']==-313  # Relative year, reader stays in source year.
    byid={e['id']:e for e in events}
    for c in report['changes']:
        if c['action'] in {'mergeCategory','removeCategory'}:
            old_other=set(c['before']['categories'])-{'famine'}
            if old_other:assert old_other <= set(byid[c['eventId']]['categories'])
    # Bad evidence must fail before replacing generated outputs.
    review=json.loads((ROOT/'scripts/river_events/famine-review.json').read_text())
    for kind in ('corpus','quote','zeroYear'):
        bad=copy.deepcopy(review)
        if kind=='corpus':bad['corpusSHA256']='changed'
        elif kind=='quote':bad['additions'][0]['sources'][0]['quote']='This quote is not in the book.'
        else:bad['additions'][0]['year']=0
        try:
            apply({}, report['corpusSHA256'], bad) if kind=='corpus' else apply(baseline_rows(data,report),report['corpusSHA256'],bad)
        except AssertionError:pass
        else:raise AssertionError(f'Failed to reject {kind}')
    paths=[ROOT/'dist'/name for name in ('river-data.json','river-events.json','river-audit-report.json','famine-audit-report.json')]
    before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    build()
    assert before=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}, 'Non-deterministic rebuild'
    result=dict(sourceLinkedEvents=len(events),famineEvents=len(famine),famineYears=202,
                regressionScenarios=['siege civilian hunger','field army exclusion','undated retrospection','relative year','same-year consolidation','other-category preservation','bad evidence rejection','deterministic rebuild'],errors=[])
    (ROOT/'artifacts/famine-supplement/validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))

def baseline_rows(data,report):
    # Restore the unamended baseline in memory for rejection scenarios.
    rows={y['year']:copy.deepcopy(y) for y in data['years']}
    byid={e['id']:e for y in rows.values() for e in y['events']}
    for y in rows.values():y['events']=[e for e in y['events'] if not e['id'].startswith('famine-supplement-')]
    snapshots={}
    for c in report['changes']:
        if 'before' in c:snapshots.setdefault(c['eventId'],c['before'])
    for eid,snapshot in snapshots.items():
        y=rows[snapshot['year']]
        y['events']=[e for e in y['events'] if e['id']!=eid]+[copy.deepcopy(snapshot)]
    # A merge target can inherit sources, but the category counts are unchanged;
    # source corruption is tested on the first new addition.
    return rows

if __name__=='__main__':main()
