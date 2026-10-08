"""Do not mislabel the three ancient-only chapters of the supplied translation EPUB."""
import json,pathlib,zipfile,re
from lxml import html as H
ANCIENT_ONLY={'OPS/chapter29.htm':28,'OPS/chapter110.htm':113,'OPS/chapter196.htm':200}
def finalize(out,epub):
 out=pathlib.Path(out);z=zipfile.ZipFile(epub)
 for f in ANCIENT_ONLY:
  root=H.fromstring(z.read(f).decode());assert root.xpath('//p')[0].text_content().startswith('【'),f
 books=[]
 for v in range(1,295):
  path=out/f'volume{v}.json';b=json.loads(path.read_text());books.append(b)
  for y in b['years']:
   keep=[]
   for pair in y.get('bilingual',[]):
    if set(pair.get('translationFiles',[]))&set(ANCIENT_ONLY):
     y.setdefault('translationBlocks',[]).extend([pair['sourceOriginal'],pair['modern']]);continue
    keep.append(pair)
   y['bilingual']=keep;covered={i for p in keep for i in p['huIndices']};y['translationMissing']=sorted(set(range(len(y['paragraphs'])))-covered)
   if v in ANCIENT_ONLY.values():y['translationWarning']='上传译本本卷实际仅载古文，未附白话；不将这些古文标为白话译文。'
   if v>10:
    entries=[]
    for pair in keep:
     if not pair['huIndices']:continue
     t=re.sub(r'^\[\d+\]','',pair['modern']);t=re.split(r'[。！？\n]',t)[0].strip();entries.append((pair['huIndices'][0],t[:42]+('…' if len(t)>42 else '')))
    for i in y['translationMissing']:
     p=y['paragraphs'][i]
     if p.get('structural'):continue
     t=re.sub(r'[\ue000-\uf8ff]','',p['plain']).strip()
     if t:entries.append((i,'原文：'+t[:38]+('…' if len(t)>38 else '')))
    entries.sort();y['anchors']=[a for a,t in entries];y['titles']=[t for a,t in entries]
   # Correct the two duplicated Hu reign numbers in metadata, retaining uploaded headings.
   if v==81 and y['year']==-284:y['reign']=5;y['reignLabel']=y['reignLabel'].replace('六年','五年')
   if v==82 and y['year']==-294:y['reign']=4;y['reignLabel']=y['reignLabel'].replace('五年','四年')
  if v>10:path.write_text(json.dumps(b,ensure_ascii=False,separators=(',',':')))
  rows=[]
  for y in b['years']:
   rows.append(dict(year=y['year'],king=y['king'],reign=y['reign'],dynasty=y.get('dynasty','周'),reignLabel=y.get('reignLabel'),recorded=y['recorded'],titles=y['titles'],anchors=y['anchors'],paragraphCount=len(y['paragraphs']),pairCount=sum(not p['difference'] for p in y['bilingual']),text=' '.join([''.join(r['text'] for r in p['runs']) for p in y['paragraphs']]+[p['modern'] for p in y['bilingual']]+y.get('translationBlocks',[]))))
  (out/f'search{v}.json').write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':')))
 cat=json.loads((out/'catalog.json').read_text())
 health=[]
 for b,meta in zip(books,cat['volumes']):
  missing=sum(len(y['translationMissing']) for y in b['years']);meta['translationMissing']=missing;meta['indexKind']=b.get('indexKind','editorial')
  if missing:health.append(dict(volume=b['volume'],title=meta['title'],missing=missing,body=meta['bodyParagraphs'],reason='上传译本本卷仅古文，无白话' if b['volume'] in ANCIENT_ONLY.values() else '上传译本漏卷、文字差异或排版待核对'))
 (out/'catalog.json').write_text(json.dumps(cat,ensure_ascii=False,separators=(',',':')))
 summary=dict(volumes=294,uniqueYears=len(cat['yearVolumes']),sourceBody=sum(v['bodyParagraphs'] for v in cat['volumes']),matchedOriginal=sum(v['bodyParagraphs']-v['translationMissing'] for v in cat['volumes']),unmatchedOriginal=sum(v['translationMissing'] for v in cat['volumes']),ancientOnlyVolumes=list(ANCIENT_ONLY.values()),volumesWithMissing=health)
 (out/'coverage.json').write_text(json.dumps(summary,ensure_ascii=False,separators=(',',':')))
 path=pathlib.Path('full-alignment-report.json');report=json.loads(path.read_text());report['finalCoverage']=summary;path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
 from summarize_event_titles import update
 update(out)
 print('FINAL COVERAGE',json.dumps({k:v for k,v in summary.items() if k!='volumesWithMissing'},ensure_ascii=False))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--data',type=pathlib.Path,default=pathlib.Path('dist'));p.add_argument('--translation',type=pathlib.Path,required=True);a=p.parse_args();finalize(a.data,a.translation)
