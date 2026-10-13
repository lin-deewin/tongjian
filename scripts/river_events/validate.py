"""Read-only evidence checks for in-progress agent reviews."""
import json
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[2]

def validate():
 books={};errors=[];rows=[]
 for p in sorted(Path(__file__).parent.glob('review-*.json')):
  d=json.loads(p.read_text());ids=set(d['coverage'].get('reviewedCandidateIds',[]));full=d['coverage'].get('fullTextReviewedCandidateIds',[])
  seen=set()
  for e in d['events']:
   if e['id'] in seen:errors.append(dict(batch=p.name,event=e['id'],issue='duplicate event id'))
   seen.add(e['id'])
   if not isinstance(e['year'],int):errors.append(dict(batch=p.name,event=e['id'],issue='year is not integer'))
   for s in e['sources']:
    v=s['volume'];y=s['year'];a=s['anchor']
    if v not in books:books[v]=json.loads((ROOT/f'dist/volume{v}.json').read_text())
    sy=next((z for z in books[v]['years'] if z['year']==y),None)
    if sy is None or not isinstance(a,int) or not 0<=a<len(sy['paragraphs']):
     errors.append(dict(batch=p.name,event=e['id'],issue='invalid source',source=s));continue
    if not s['quote'] or s['quote'] not in sy['paragraphs'][a]['plain']:errors.append(dict(batch=p.name,event=e['id'],issue='quote mismatch',source=s))
    if e['status']=='reviewed' and f'v{v}-y{y}-p{a}' not in ids:errors.append(dict(batch=p.name,event=e['id'],issue='source not audited',source=s))
    if e['status']=='reviewed' and y!=e['year'] and not e.get('dateBasis'):errors.append(dict(batch=p.name,event=e['id'],issue='missing dateBasis',source=s))
  rows.append(dict(batch=p.name,candidates=d['coverage']['candidateParagraphs'],read=len(ids),fullTextRead=len(full) if full else None,events=dict(Counter(e['status'] for e in d['events']))))
 report=dict(batches=rows,errors=errors)
 target=ROOT/'artifacts/river-audit/validation.json';target.write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps(report,ensure_ascii=False,indent=2))
 return report
if __name__=='__main__':
 report=validate()
 raise SystemExit(bool(report['errors']))
