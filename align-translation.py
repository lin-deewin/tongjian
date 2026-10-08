import pathlib,lxml.html as H,re,json,difflib
root=H.fromstring(pathlib.Path('/tmp/baiyang-volume1.html').read_text())
h=root.xpath('//h3')[0];texts=[]
for p in h.itersiblings():
 if p.tag!='p':continue
 t=p.text_content().strip()
 if t.startswith('---'):break
 texts.extend(s for s in t.split('*') if s)
by={};year=None
for t in texts:
 m=re.search(r'前(\d{3})',t)
 if m and len(t)<65 and re.match(r'^(周纪一\s*)?(周)?(威烈王|安王|烈王)?[元一二三四五六七八九十]+年',t):
  year=int(m[1]);by.setdefault(year,{'headers':[],'tokens':[]})['headers'].append(t)
 else:
  assert year;by[year]['tokens'].append(t)
book=json.load(open('dist/volume1.json'))
def norm(t):return re.sub(r'[^\u4e00-\u9fff]','',re.sub(r'^\[\d+\]','',t)).replace('崐','')
report=[]
for y in book['years']:
 d=by.get(y['year']);pairs=[];used=set(); ps=y['paragraphs']
 if d:
  assert len(d['tokens'])%2==0,(y['year'],len(d['tokens']))
  for i in range(0,len(d['tokens']),2):
   original,modern=d['tokens'][i:i+2];best=(0,[])
   for start in range(len(ps)):
    for size in [1,2,3]:
     indices=list(range(start,min(start+size,len(ps))))
     if any(a in used for a in indices):continue
     score=difflib.SequenceMatcher(None,norm(original),norm(''.join(ps[a]['plain'] for a in indices)),autojunk=False).ratio()
     if score>best[0]:best=(score,indices)
   if best[0]>=.65:
    indices=best[1];used.update(indices)
   else:indices=[]
   pairs.append({'huIndices':indices,'sourceOriginal':original,'modern':modern,'score':round(best[0],3),'kind':'commentary' if original.startswith(('臣光曰','太史公曰')) else 'record','difference':not indices})
 y['bilingual']=pairs;y['translationHeaders']=d['headers'] if d else []
 y['translationMissing']=[i for i in range(len(ps)) if i not in used]
 report.append({'year':y['year'],'pairs':len(pairs),'differences':[p['sourceOriginal'] for p in pairs if p['difference']],'missing':y['translationMissing'],'minScore':min((p['score'] for p in pairs if not p['difference']),default=1)})
book['translationSource']='上传的《资治通鉴全译本柏杨版》EPUB · chapter1.htm（文件署名，未另作版本鉴定）'
pathlib.Path('dist/volume1.json').write_text(json.dumps(book,ensure_ascii=False,separators=(',',':')))
print(json.dumps(report,ensure_ascii=False,indent=2))
