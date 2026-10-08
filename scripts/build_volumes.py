"""Extract volumes 2–10 from the user's two EPUBs; retain source text and audit matches."""
import argparse, pathlib, zipfile, re, json, difflib
from lxml import html as H
A=argparse.ArgumentParser();A.add_argument('--original',type=pathlib.Path,required=True);A.add_argument('--translation',type=pathlib.Path,required=True);A.add_argument('--output',type=pathlib.Path,default=pathlib.Path('dist'));args=A.parse_args()
# Reign boundaries derive from the volume headers; all years are BCE.
regimes=[(403,402,'周','威烈王',426),(401,376,'周','安王',402),(375,369,'周','烈王',376),(368,321,'周','显王',369),(320,315,'周','慎靓王',321),(314,256,'周','赧王',315),(255,251,'秦','昭襄王',307),(250,250,'秦','孝文王',251),(249,247,'秦','庄襄王',250),(246,210,'秦','始皇帝',247),(209,207,'秦','二世皇帝',210),(206,203,'汉','高帝',207)]
ranges={2:(368,321),3:(320,298),4:(297,273),5:(272,256),6:(255,228),7:(227,209),8:(208,207),9:(206,205),10:(204,203)}
num=dict(zip('〇○零一二三四五六七八九',[0,0,0,1,2,3,4,5,6,7,8,9]))
def number(t):
 if t=='元':return 1
 if '十' in t:
  a,b=t.split('十');return (num[a] if a else 1)*10+(num[b] if b else 0)
 return num[t]
def digit(t):return int(''.join(str(num[c]) for c in t))
def split(t):
 runs=[];buf='';depth=0;kind='text';anomaly=False
 for pos,c in enumerate(t):
  if c=='〔' and depth and (t[pos:].startswith('〔【章：') or t[pos:].startswith('〔宜翻，')):
   buf+=c;anomaly=True;continue
  if c=='〔':
   if depth==0:
    if buf:runs.append({'kind':kind,'text':buf})
    buf='';kind='note'
   depth+=1;buf+=c
  elif c=='〕' and depth:
   buf+=c;depth-=1
   if depth==0:runs.append({'kind':'note','text':buf});buf='';kind='text'
  else:
   if c=='〕':anomaly=True
   buf+=c
 if buf:runs.append({'kind':kind,'text':buf})
 if depth:anomaly=True
 assert ''.join(r['text'] for r in runs)==t
 return runs,anomaly

def norm(t):return re.sub(r'[^\u4e00-\u9fff]','',re.sub(r'^\[\d+\]','',t)).replace('崐','')
zh=zipfile.ZipFile(args.original);zt=zipfile.ZipFile(args.translation);report=[]
for v,(start,end) in ranges.items():
 source=f'OEBPS/text{v+2:05d}.html';root=H.fromstring(zh.read(source).decode('utf-8'));title=root.xpath('//h3')[0].text_content();short=title.split('】')[0]+'】';intro=[];years=[]
 for year in range(start,end-1,-1):
  _,_,dyn,king,epoch=next(r for r in regimes if r[0]>=year>=r[1])
  years.append(dict(year=year,dynasty=dyn,king=king,reign=epoch-year,heading='',after=[],paragraphs=[],titles=[],anchors=[]))
 by={y['year']:y for y in years};current=None;sourceps=[p.text_content() for p in root.xpath('//p')];bracketWarnings=[]
 for ix,t in enumerate(sourceps):
  runs,anomaly=split(t);plain=''.join(r['text'] for r in runs if r['kind']=='text');p={'runs':runs,'plain':plain}
  m=re.fullmatch(r'([元一二三四五六七八九十]+)年',plain)
  if m:
   date=re.search(r'前([〇○零一二三四五六七八九]+)',t);assert date,(v,t)
   year=digit(date[1]);assert year in by,(v,t,year);current=by[year];assert not current['heading'],(v,year)
   current['heading']=t;current['headingRuns']=runs
   if number(m[1])!=current['reign']:current['warning']=f'上传胡注本年头写作“{m[1]}年”，同一处公元前年份为前{year}年。本页按该年份与在位年序显示为第{current["reign"]}年；保留原文件年头。'
  elif re.fullmatch(r'(显王|慎靓王|赧王[上中下]?|昭襄王|孝文王|庄襄王|始皇帝[上下]?|二世皇帝[上下]?|太祖高皇帝上之[上下])',plain):
   if current:current['after'].append(t)
   else:intro.append(p)
  elif current:
   if not plain.strip():
    # Source has occasional stand-alone PUA numbering; preserve it in the body.
    pass
   current['paragraphs'].append(p)
  else:intro.append(p)
  if anomaly and current:current['noteWarning']='原文件本年含注释括号异常；字符按原样保留，可展开胡注核对。'
  if anomaly:bracketWarnings.append({'sourceParagraph':ix,'year':current['year'] if current else None})
 assert sum(len(y['paragraphs'])+bool(y['heading'])+len(y['after']) for y in years)+len(intro)==len(sourceps)
 chapter=next(n for n in zt.namelist() if n.endswith(f'chapter{v}.htm'));rt=H.fromstring(zt.read(chapter).decode('utf-8'));tokens=[]
 for p in rt.xpath('//h3')[0].itersiblings():
  if p.tag!='p':continue
  t=p.text_content().strip()
  if t.startswith(('该书籍由','--epub','---')):break
  tokens.extend(s.strip() for s in t.split('*') if s.strip())
 trans={};year=None
 for t in tokens:
  m=re.search(r'前(\d{3})',t)
  if m and len(t)<85 and re.search(r'[元一二三四五六七八九十]+年\s*[（(]',t):
   year=int(m[1]);assert year in by,(v,t);trans.setdefault(year,{'headers':[],'tokens':[]})['headers'].append(t)
  else:
   assert year,(v,t);trans[year]['tokens'].append(t)
 warnings=[]
 for y in years:
  d=trans.get(y['year']);ps=y['paragraphs'];pairs=[];used=set()
  if d:
   if v==5 and y['year']==266:
    assert d['tokens'][2].startswith('秦国的将');d['tokens'][1]+=d['tokens'].pop(2)
   if v==5 and y['year']==270:
    assert d['tokens'][-1].startswith('王说：'); d['tokens'][-2]=d['tokens'][-2]+d['tokens'][-1];d['tokens'].pop()
   assert len(d['tokens'])%2==0,(v,y['year'],len(d['tokens']),[t[:90] for t in d['tokens']])
   for i in range(0,len(d['tokens']),2):
    original,modern=d['tokens'][i:i+2];best=(0,[])
    for idx in range(len(ps)):
     for size in range(1,7):
      indices=list(range(idx,min(idx+size,len(ps))))
      if any(j in used for j in indices):continue
      score=difflib.SequenceMatcher(None,norm(original),norm(''.join(ps[j]['plain'] for j in indices)),autojunk=False).ratio()
      if score>best[0]:best=score,indices
    indices=best[1] if best[0]>=.65 else [];used.update(indices)
    pairs.append(dict(huIndices=indices,sourceOriginal=original,modern=modern,score=round(best[0],3),kind='commentary' if re.match(r'^(臣光曰|太史公曰|贾谊论曰|扬子|荀子论之曰)',re.sub(r'^\[\d+\]','',original)) else 'record',difference=not indices))
  # Some editions split a single Hu paragraph into several bilingual pairs.
  for pair in list(pairs):
   if not pair['difference']:continue
   a=norm(pair['sourceOriginal'])
   target=next((p for p in pairs if p['huIndices'] and a and any(a in norm(ps[j]['plain']) for j in p['huIndices'])),None)
   if target:
    ordered=sorted([target,pair],key=lambda p:pairs.index(p))
    target['sourceOriginal']='\n'.join(p['sourceOriginal'] for p in ordered)
    target['modern']='\n'.join(re.sub(r'^\[\d+\]','',p['modern']) for p in ordered)
    target['score']=round(difflib.SequenceMatcher(None,norm(target['sourceOriginal']),norm(''.join(ps[j]['plain'] for j in target['huIndices'])),autojunk=False).ratio())
    pairs.remove(pair)
  y.update(bilingual=pairs,translationHeaders=d['headers'] if d else [],translationMissing=[i for i in range(len(ps)) if i not in used],recorded=bool(ps),search=' '.join(p['plain'] for p in ps),noteCount=sum(r['kind']=='note' for p in ps for r in p['runs']))
  # Translated incipits are explicitly labelled; no invented historical summaries.
  for pair in sorted((p for p in pairs if p['huIndices']),key=lambda p:p['huIndices'][0]):
   t=re.sub(r'^\[\d+\]','',pair['modern']);t=re.sub(r'[\ue000-\uf8ff]','',t)
   first=re.split(r'[。！？]',t)[0];y['titles'].append(first[:42]+('…' if len(first)>42 else ''));y['anchors'].append(pair['huIndices'][0])
  for i in y['translationMissing']:
   t=re.sub(r'[\ue000-\uf8ff]','',ps[i]['plain']).strip()
   if t:y['titles'].append(t[:42]+('…' if len(t)>42 else ''));y['anchors'].append(i)
  order=sorted(range(len(y['anchors'])),key=lambda i:y['anchors'][i]);y['titles']=[y['titles'][i] for i in order];y['anchors']=[y['anchors'][i] for i in order]
  if y['translationMissing'] or any(p['difference'] or p['score']<.9 for p in pairs):warnings.append({'year':y['year'],'missing':y['translationMissing'],'pairs':[{'score':p['score'],'indices':p['huIndices'],'original':p['sourceOriginal'][:100],'modern':p['modern'][:100]} for p in pairs if p['difference'] or p['score']<.9]})
 book=dict(volume=v,title=short,fullTitle=title,source=f'上传的《资治通鉴 胡三省注版》EPUB · {source}',intro=intro,years=years,translationSource=f'上传的《资治通鉴全译本柏杨版》EPUB · {chapter}（文件署名，未另作版本鉴定）',indexKind='translationExcerpt',sourceBracketWarnings=bracketWarnings)
 args.output.mkdir(parents=True,exist_ok=True);(args.output/f'volume{v}.json').write_text(json.dumps(book,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
 report.append(dict(volume=v,years=len(years),sourceParagraphs=len(sourceps),bodyParagraphs=sum(len(y['paragraphs']) for y in years),pairs=sum(len(y['bilingual']) for y in years),bracketWarnings=bracketWarnings,warnings=warnings))
pathlib.Path('alignment-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))

# Reapply reviewed and automatic browsing headings after rebuilding source data.
from summarize_event_titles import update
update(args.output)
