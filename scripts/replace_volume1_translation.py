"""Import the inspected zztj2 EPUB's BC 403–369 text; retain Hu text and anchors."""
import argparse,json,re,zipfile,hashlib,io
from PIL import Image
from pathlib import Path
from lxml import html
p=argparse.ArgumentParser();p.add_argument('--epub',type=Path,required=True);p.add_argument('--data',type=Path,default=Path('dist'));a=p.parse_args()
b=json.loads((a.data/'volume1.json').read_text());by={};headers={};year=None;group=None
with zipfile.ZipFile(a.epub) as z:
 for f in ['OEBPS/text00008.html','OEBPS/text00009.html']:
  for i,e in enumerate(html.fromstring(z.read(f).decode('utf-8')).xpath('//body/*')):
   for im in (e.xpath('.//img[@class="s-pic"]') if year and 369<=year<=403 and e.tag!='h4' else []):
    glyph={'Image00005.jpg':'絺','Image00006.jpg':'絺','Image00007.jpg':'騑','Image00010.jpg':'罃','Image00012.jpg':'罃'}[im.get('src')]
    im.tail=glyph+(im.tail or '')
   t=re.sub(r'\s+','',e.text_content())
   if e.tag=='h4':
    m=re.search(r'公元前([〇一二三四五六七八九]+)年',t)
    year=int(''.join(str('〇一二三四五六七八九'.index(c)) for c in m[1])) if m else None;group=None
    if year and 369<=year<=403:headers[year]=[t]
   if not year or not 369<=year<=403 or not t:continue
   if e.get('class')=='content_106':group=t;continue
   if e.tag=='p' and e.get('class')=='content':
    if t=='1本年无记载。':continue
    by.setdefault(year,[]).append(dict(text=t,kind='record',file=f,index=i));group=None
   elif e.tag=='p' and e.get('class','').startswith('quotation') and group:
    if not by.setdefault(year,[]) or by[year][-1]['kind']!=group:by[year].append(dict(text='',kind=group,file=f,index=i))
    by[year][-1]['text']+=t+'\n'
# Explicit exceptions reviewed against Hu paragraphs. Other years follow verified event order.
special={403:[[0],list(range(1,8)),[],[8],[9],[],[10],[11],[12],[13],[14],None,[15],[16],[],[17,18],[19],[20],[21],[22],[23],[24],[25],[26],[27],[28],[29],[30]],397:[[0],[1],[]],388:[[]],387:[[0],[1],[2],[3],[],[4],[5],[6],[7],[8]],385:[[0],[],[1],[2]],381:[[0],[]],380:[[0],None],379:[[0],[1],[]],378:[[0],[1],[2],[]],377:[[0],[1],[2],[3],[4],[5]],370:[[0],[],[1],[2],[3],[4],[5]],369:[[0],[1],[2],[3],[]]}
report=[]
for y in b['years']:
 rows=by.get(y['year'],[]);mapping=special.get(y['year'],[[i] for i in range(len(rows))]);assert len(rows)==len(mapping),(y['year'],len(rows),len(mapping))
 pairs=[]
 for row,indices in zip(rows,mapping):
  text=row['text'].strip()
  if row['kind']!='record':text=row['kind']+'\n'+text
  if indices is None:
   pairs[-1]['modern']+='\n'+text;pairs[-1]['sourceLocations'].append(dict(file=row['file'],element=row['index']));continue
  pairs.append(dict(huIndices=indices,sourceOriginal='',modern=text,score=1.0,kind='record' if row['kind']=='record' else 'commentary',difference=not indices,alignmentMethod='manual-content-review',sourceLabel='柏杨评论' if row['kind']=='柏杨曰：' else '新译本独有记事',sourceLocations=[dict(file=row['file'],element=row['index'])],translationFiles=[row['file']]))
 covered=[i for pair in pairs for i in pair['huIndices']];assert sorted(covered)==list(range(len(y['paragraphs']))),(y['year'],covered)
 y['bilingual']=pairs;y['translationHeaders']=headers.get(y['year'],[]);y['translationMissing']=[]
 y['translationWarning']='白话已替换为新上传的《柏杨白话版资治通鉴》。新书未附逐段古文，按记事内容人工核对；柏杨评论及新增、改系年份记事另列在版本差异中。'
 report.append(dict(year=y['year'],pairs=len(pairs),differences=sum(p['difference'] for p in pairs),covered=len(covered)))
# Map captions carry the historical date; EPUB layout occasionally places them later.
map_specs=[('Image00003.jpg',403,0,403,29),('Image00004.jpg',403,0,403,32),('Image00008.jpg',376,1,375,582),('Image00009.jpg',375,1,373,623),('Image00011.jpg',370,3,370,702)]
asset_dir=a.data/'images/baiyang-volume1';asset_dir.mkdir(parents=True,exist_ok=True)
with zipfile.ZipFile(a.epub) as z:
 for name,year,anchor,source_year,element in map_specs:
  f='OEBPS/text00008.html' if year==403 else 'OEBPS/text00009.html'
  e=html.fromstring(z.read(f).decode('utf-8')).xpath('//body/*')[element]
  caption=re.sub(r'\s+','',e.text_content());raw=z.read('OEBPS/'+name)
  width,height=Image.open(io.BytesIO(raw)).size
  (asset_dir/name).write_bytes(raw)
  y=next(y for y in b['years'] if y['year']==year)
  pair=next(pair for pair in y['bilingual'] if anchor in pair['huIndices'])
  pair.setdefault('illustrations',[]).append(dict(src='images/baiyang-volume1/'+name,caption=caption,width=width,height=height,sourceFile=f,sourceElement=element,sourceYear=source_year,year=year,placementNote='按图题年份放置；EPUB排版位置在前'+str(source_year)+'年。' if source_year!=year else ''))
b['translationSource']='上传的《柏杨白话版资治通鉴（全72册）》EPUB · zztj2.epub · 東方出版社（文件元数据署名柏杨；未另作版本鉴定）'
b['translationProvenance']=dict(fileName=a.epub.name,sha256=hashlib.sha256(a.epub.read_bytes()).hexdigest(),chapters=['OEBPS/text00008.html','OEBPS/text00009.html'],alignment='人工按年份与记事内容核对；sourceOriginal为空，因为该译本未附古文')
(a.data/'volume1.json').write_text(json.dumps(b,ensure_ascii=False,separators=(',',':')))
rows=json.loads((a.data/'search1.json').read_text())
for r,y in zip(rows,b['years']):
 assert r['year']==y['year'];r['pairCount']=sum(not p['difference'] for p in y['bilingual']);r['text']=' '.join([''.join(t['text'] for t in p['runs']) for p in y['paragraphs']]+[p['modern'] for p in y['bilingual']])
(a.data/'search1.json').write_text(json.dumps(rows,ensure_ascii=False,separators=(',',':')))
Path('artifacts/translation-volume1/import-report.json').write_text(json.dumps(dict(source=b['translationProvenance'],years=report),ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False))
