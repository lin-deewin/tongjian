"""Validate all 294 volumes, reconstruction, no year zero, unique alignment and provenance."""
import argparse,json,pathlib,zipfile,collections,re
from lxml import html as H
from validate_volume import check
from translations.overlay import apply as apply_supplement
from translations.replacement import apply as apply_replacement, load_replacement, replacement_path
A=argparse.ArgumentParser();A.add_argument('--original',type=pathlib.Path,required=True);A.add_argument('--base-only',action='store_true',help='Validate canonical files before translation overlays');A.add_argument('--data',type=pathlib.Path,default=pathlib.Path('dist'));a=A.parse_args();z=zipfile.ZipFile(a.original);years=set();bodies=missing=matched=diff=0
for v in range(1,295):
 b=json.loads((a.data/f'volume{v}.json').read_text());assert b['volume']==v
 replacement=replacement_path(a.data,v)
 overlay=a.data/f'translation-supplements/volume{v}.json'
 if replacement.exists() and not a.base_only:
  canonical,extra,raw_sha=load_replacement(a.data/f'volume{v}.json',replacement)
  b=apply_replacement(canonical,extra,canonical_sha=raw_sha)
 elif overlay.exists() and not a.base_only:
  import hashlib
  extra=json.loads(overlay.read_text());assert extra['baseSHA256']==hashlib.sha256((a.data/f'volume{v}.json').read_bytes()).hexdigest();b=apply_supplement(b,extra)
 check(b)
 r=[''.join(run['text'] for run in p['runs']) for p in b['intro']]
 for y in b['years']:
  years.add(y['year']);assert y['year']!=0
  if y['heading']:r.append(y['heading'])
  r+=[''.join(run['text'] for run in p['runs']) for p in y['paragraphs']];r+=y['after'];bodies+=len(y['paragraphs']);missing+=len(y['translationMissing']);matched+=sum(len(p['huIndices']) for p in y['bilingual']);diff+=sum(p['difference'] for p in y['bilingual'])
  if 'calendarYear' in y:assert y['calendarYear']==-y['year']
 physical={200:201,201:200}.get(v,v);ps=[p.text_content() for p in H.fromstring(z.read(f'OEBPS/text{physical+2:05d}.html').decode()).xpath('//p')]
 assert r==ps,('Original source mismatch',v)
 search=json.loads((a.data/f'search{v}.json').read_text());assert [y['year'] for y in search]==[y['year'] for y in b['years']]
assert years==set(range(1,404))|set(range(-959,0)),('global years',len(years))
cat=json.loads((a.data/'catalog.json').read_text());assert len(cat['volumes'])==294;assert set(map(int,cat['yearVolumes']))==years
assert matched+missing==bodies
print(json.dumps(dict(volumes=294,uniqueYears=len(years),originalBody=bodies,matchedOriginal=matched,unmatchedOriginal=missing,translationDifferences=diff,sourceReconstruction='exact'),ensure_ascii=False))
