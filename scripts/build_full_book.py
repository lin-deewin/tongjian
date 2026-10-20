"""Build all remaining Tongjian volumes from the supplied EPUBs. No generated translations."""
import argparse, pathlib, zipfile, re, json, collections, difflib, time
from lxml import html as H
from clean_translation_markup import clean_translation_text
A=argparse.ArgumentParser();A.add_argument('--original',type=pathlib.Path,required=True);A.add_argument('--translation',type=pathlib.Path,required=True);A.add_argument('--output',type=pathlib.Path,default=pathlib.Path('dist'));A.add_argument('--extract-only',action='store_true');args=A.parse_args();out=args.output;out.mkdir(parents=True,exist_ok=True)
NUM=dict(zip('〇○零一二三四五六七八九',[0,0,0,1,2,3,4,5,6,7,8,9]))
def digit(t):
 if t.isdigit():return int(t)
 if '十' in t:
  a,b=t.split('十');return (NUM[a] if a else 1)*10+(NUM[b] if b else 0)
 return int(''.join(str(NUM[c]) for c in t))
def cn(t):
 total=n=0
 for c in t:
  if c in NUM:n=NUM[c]
  elif c in '十百':total+=(n or 1)*{'十':10,'百':100}[c];n=0
 return total+n
# Identified typos in the uploaded Hu text: source characters are never rewritten.
FIX={(1,130):371,(21,28):107,(50,50):-120,(79,101):-271,(81,71):-284,(82,76):-294,(88,51):-313,(90,1):-317,(91,1):-319,(116,66):-413,(117,1):-415,(118,1):-417,(123,96):-440,(135,2):-479,(135,57):-480,(209,61):-710,(213,49):-728,(226,22):-780,(279,101):-935,(293,69):-957}
HEAD=re.compile(r'^([^〔]{1,12}?[年载])[，,。]?〔[（(]?([^〕）]{1,35})')
def heading(v,i,t):
 m=HEAD.match(t)
 if not m:return None
 d=re.search(r'[、，,﹑](前?)([〇○零一二三四五六七八九十\d膶]+)',m[2])
 if not d:return None
 try:raw=digit(d[2])*(1 if d[1] else -1)
 except (KeyError,ValueError):raw=None
 year=FIX.get((v,i),raw)
 assert year is not None,(v,i,t)
 return year,m[1],raw

def runs(t):
 result=[];buf='';depth=0;kind='text';bad=False
 # Extra chapter-note opening marks exist in this upload. Only ignore when opens exceed closes.
 excess=max(0,t.count('〔')-t.count('〕'))
 for pos,c in enumerate(t):
  if c=='〔' and depth and excess and (t[pos:].startswith('〔【章：') or t[pos:].startswith('〔宜翻，')):
   buf+=c;excess-=1;bad=True;continue
  if c=='〔':
   if not depth:
    if buf:result.append(dict(kind='text',text=buf))
    buf='';kind='note'
   buf+=c;depth+=1
  elif c=='〕' and depth:
   buf+=c;depth-=1
   if not depth:result.append(dict(kind='note',text=buf));buf='';kind='text'
  else:
   if c=='〕':bad=True
   buf+=c
 if buf:result.append(dict(kind=kind,text=buf))
 if depth:
  # Uncertain markup stays visible rather than swallowing historical text as a hidden note.
  result=[dict(kind='text',text=t)];bad=True
 assert ''.join(r['text'] for r in result)==t
 return result,bad

def plain(rs):return ''.join(r['text'] for r in rs if r['kind']=='text')
def norm(t):return re.sub(r'[^\u4e00-\u9fff]','',re.sub(r'^\[\d+\]','',t)).replace('崐','')
def sequence(start,end):return [y for y in range(start,end-1,-1) if y]
def yearname(y):return ('前' if y>0 else '')+str(abs(y))+'年'
def clean_king(t):return re.sub(r'(上之[上中下]|中之[上中下]|下之[上中下]|上之上|上之下|[上中下甲乙丙丁戊己庚辛壬癸一二三四五六七八九十]+)$','',t)
def marker(t):
 return bool(re.fullmatch(r'[^，。；：、！？\s]{1,45}(?:皇帝|皇后|帝|王)(?:[上中下甲乙丙丁戊己庚辛壬癸一二三四五六七八九十之]*)',t))
zh=zipfile.ZipFile(args.original);zt=zipfile.ZipFile(args.translation);books={};source_checks=[];king='';era='';previous=None
for v in range(1,295):
 physical={200:201,201:200}.get(v,v);src=f'OEBPS/text{physical+2:05d}.html';root=H.fromstring(zh.read(src).decode());fulltitle=root.xpath('//h3')[0].text_content();short=fulltitle.split('】')[0]+'】';dyn=re.search(r'【(.*?)[纪记]',short)[1];ps=[p.text_content() for p in root.xpath('//p')];heads={i:heading(v,i,t) for i,t in enumerate(ps)};heads={i:h for i,h in heads.items() if h};dates=[h[0] for h in heads.values()];assert dates and all(a>b for a,b in zip(dates,dates[1:])),(v,dates)
 if v<=10:
  b=json.loads((out/f'volume{v}.json').read_text());books[v]=b
  for i,t in enumerate(ps):
   rs,_=runs(t);base=plain(rs)
   if marker(base):king=clean_king(base)
  continue
 years=[];by={};intro=[];current=None;structural=[]
 for i,t in enumerate(ps):
  rs,bad=runs(t);base=plain(rs);p=dict(runs=rs,plain=base,sourceId=f'v{v}-p{i}')
  if i in heads:
   year,label,raw=heads[i];num=re.search(r'([元一二三四五六七八九十]+)[年载]$',label);rn=1 if num[1]=='元' else cn(num[1]);prefix=label[:num.start()]
   if prefix:era=prefix
   current=dict(year=year,calendarYear=-year,king=king or dyn,eraName=era,reign=rn,reignLabel=dyn+(king or '')+era+num[1]+label[-1],dynasty=dyn,heading=t,headingRuns=rs,after=[],paragraphs=[],titles=[],anchors=[])
   if raw!=year:current['warning']=f'上传原文件年头的数字有误；按本卷年号与相邻年份定位为{yearname(year)}，原字保留。'
   if (v,i) in [(81,71),(82,76)]:current['warning']='上传年头与下一年重复；按上下年序和译本定位，原字保留。'
   years.append(current);by[year]=current
  elif marker(base):
   king=clean_king(base)
   if current:current['after'].append(t)
   else:intro.append(p)
  elif current:
   if current['after'] and not base.strip():current['after'].append(t)
   else:
    if current['after']:
     for rawtext in current['after']:
      rr,_=runs(rawtext);current['paragraphs'].append(dict(runs=rr,plain=plain(rr),structural=True))
     current['after']=[]
    current['paragraphs'].append(p)
  else:intro.append(p)
  if bad and current:current['noteWarning']='上传原文的注释括号有异常，字符原样保留；无法可靠划分的段落默认全文显示。'
 for year in sequence(dates[0],dates[-1]):
  if year in by:continue
  older=next(y for y in reversed(years) if y['year']>year)
  delta=older['year']-year-(1 if older['year']>0>year else 0)
  empty=dict(year=year,calendarYear=-year,king=older['king'],eraName=older['eraName'],reign=older['reign']+delta,reignLabel=f'{yearname(year)} · 本卷无单列记事',dynasty=dyn,heading='',after=[],paragraphs=[],titles=[],anchors=[]);by[year]=empty
 years=[by[y] for y in sequence(dates[0],dates[-1])]
 b=dict(volume=v,title=short,fullTitle=fulltitle,source=f'上传胡三省注版 EPUB · {src}',sourceFile=src,intro=intro,years=years,translationSource='上传白话 EPUB（文件署名，未另作版本鉴定）',indexKind='translationExcerpt',schemaVersion=2);books[v]=b
 reconstructed=[''.join(r['text'] for r in p['runs']) for p in intro]
 for y in years:
  if y['heading']:reconstructed.append(y['heading'])
  reconstructed.extend(''.join(r['text'] for r in p['runs']) for p in y['paragraphs']);reconstructed.extend(y['after'])
 assert reconstructed==ps,('source reconstruction',v)
 source_checks.append(dict(volume=v,sourceParagraphs=len(ps),start=dates[0],end=dates[-1]))
# Include empty years that fall exactly between volume boundaries, e.g. 288 CE.
for v in range(1,294):
 a=books[v];b=books[v+1];last=a['years'][-1]['year'];first=b['years'][0]['year']
 assert last>=first,('reverse volume',v,last,first)
 for key in sequence(last-1,first+1):
  if key==first or key==last:continue
  template=a['years'][-1];a['years'].append(dict(year=key,calendarYear=-key,king=template['king'],dynasty=template.get('dynasty','周'),reign=template['reign']+1,reignLabel=yearname(key)+' · 本卷无单列记事',heading='',after=[],paragraphs=[],titles=[],anchors=[],bilingual=[],translationMissing=[]))
# First ten volumes remain unchanged; use their data only as matching references.
hu_by_year=collections.defaultdict(list)
for v,b in books.items():
 for y in b['years']:
  for i,p in enumerate(y['paragraphs']):hu_by_year[y['year']].append((v,y,i,norm(re.sub(r'〔[^〕]*〕','',p['plain']) if len(p['runs'])==1 and p['runs'][0]['kind']=='text' and '〔' in p['plain'] else p['plain'])))
TRANS_HEAD=re.compile(r'^([^（）\n]{0,100}?[年载])\s*[（(]([^）)]{0,55}?)[）)]')
def trans_head(t):
 m=TRANS_HEAD.match(t)
 if not m:return None
 d=re.search(r'[、，,﹑]\s*(?:公元|公年)?(前)?\s*([〇○零一二三四五六七八九\d]{1,4})\s*年?',m[2])
 if not d:return None
 return digit(d[2])*(1 if d[1] else -1),m.end(),m[0]
trans=collections.defaultdict(list);headers=collections.defaultdict(list);translation_sources=collections.defaultdict(set);token_count=0;year=None;orphan=[];headsequence=[]
for name in sorted((n for n in zt.namelist() if re.search(r'chapter\d+\.htm$',n)),key=lambda s:int(re.search(r'chapter(\d+)',s)[1])):
 root=H.fromstring(zt.read(name).decode());filetitle=root.xpath('//h3')[0].text_content();baseVolumeMatch=re.search(r'第+([一二三四五六七八九十百零]+)卷',filetitle);filevolume=cn(baseVolumeMatch[1]) if baseVolumeMatch else None
 for p in root.xpath('//p'):
  full=clean_translation_text(p.text_content().strip(),name)
  if full.startswith(('该书籍由','--epub','---')):continue
  if re.fullmatch(r'(?:资[治冶]通鉴|通鉴)[\s第卷]*[一二三四五六七八九十百零]+卷?',full):continue
  # Asterisks are layout delimiters in the uploaded file.
  for t in (t.strip() for t in full.split('*') if t.strip()):
   while True:
    h=trans_head(t)
    if not h:break
    year,end,head=h;headers[year].append(head);translation_sources[year].add(name);headsequence.append((name,year,head));t=t[end:].strip()
    if t in ('B>','</B>'):t=''
    if not t:break
   if not t:continue
   if year is None:orphan.append((name,t));continue
   trans[year].append(dict(text=t,file=name,fileVolume=filevolume));token_count+=1
pathlib.Path('full-source-audit.json').write_text(json.dumps(dict(sourceChecks=source_checks,translationHeadSequence=headsequence,orphan=orphan),ensure_ascii=False,indent=2))
pathlib.Path('/tmp/tongjian-translation-tokens.json').write_text(json.dumps(trans,ensure_ascii=False))
if args.extract_only:
 for v,b in books.items():
  if v>10:(out/f'volume{v}.json').write_text(json.dumps(b,ensure_ascii=False,separators=(',',':')))
 print('EXTRACT',len(books),'body',sum(len(y['paragraphs']) for b in books.values() for y in b['years']),'tokens',token_count,'orphans',orphan[:4],flush=True)
 print('TR REVERSE',[(a,b) for a,b in zip(headsequence,headsequence[1:]) if a[1]<b[1]][:60]);raise SystemExit
# Correct an unambiguous duplicated year digit in both translated headers.
if -992 in trans:
 trans[-922].extend(trans.pop(-992));headers[-922].extend(headers.pop(-992));translation_sources[-922].update(translation_sources.pop(-992))
report=[];unassigned=[];started=time.monotonic()
def grams(t):return set(t[i:i+3] for i in range(max(1,len(t)-2))) if len(t)>=3 else {t}
for count,(year,tokens) in enumerate(sorted(trans.items(),reverse=True)):
 if year>=203:continue  # Already verified first ten volumes are preserved.
 refs=hu_by_year.get(year,[]);texts=[p['text'] for p in tokens];normalized=[norm(t) for t in texts];refgrams=[grams(r[3]) for r in refs];cache={}
 def best(text):
  a=norm(text)
  if a in cache:return cache[a]
  if not a or not refs:cache[a]=(0,[]);return cache[a]
  gs=grams(a);rank=sorted(range(len(refs)),key=lambda i:len(gs&refgrams[i])/max(1,min(len(gs),len(refgrams[i]))),reverse=True)[:8];choices=set()
  for index in rank:
   for start in range(max(0,index-2),index+1):
    for length in range(1,7):
     stop=min(len(refs),start+length)
     if refs[start][0]!=refs[stop-1][0]:continue
     choices.add((start,stop))
  score=0;indices=[]
  for start,stop in choices:
   b=''.join(r[3] for r in refs[start:stop]);length_ratio=min(len(a),len(b))/max(1,max(len(a),len(b)))
   if 2*length_ratio/(1+length_ratio)<max(.68,score):continue
   if a==b:s=1.
   elif a in b:s=2*len(a)/(len(a)+len(b))
   else:
    bg=grams(b)
    if len(gs&bg)/max(1,min(len(gs),len(bg)))<.32:continue
    s=difflib.SequenceMatcher(None,a,b,autojunk=False).ratio()
   if s>score:score=s;indices=list(range(start,stop))
  cache[a]=(score,indices);return cache[a]
 scores=[best(t)[0] for t in texts]
 # Standard alternating pairs are retained where their ancient text matches.
 standard=len(texts)%2==0 and sum(s<.68 for s in scores[::2])<=max(1,len(texts)//20)
 chunks=[]
 if standard:chunks=[(i,i+1,i+2) for i in range(0,len(texts),2)]
 else:
  # DP resolves wrapped or merged paragraphs; marker mismatches prohibit false boundaries.
  n=len(texts);dp=[float('-inf')]*(n+1);dp[n]=0;choices={}
  for i in range(n-1,-1,-1):
   dp[i]=dp[i+1]-1.8;choices[i]=(i+1,i+1)
   for orig_count in range(1,min(3,n-i-1)+1):
    middle=i+orig_count;original=''.join(texts[i:middle]);s,_=best(original)
    if orig_count>1 and any(re.match(r'^\[\d+\]',t) for t in texts[i+1:middle]):continue
    for modern_count in range(1,min(4,n-middle)+1):
     end=middle+modern_count
     if dp[end]==float('-inf'):continue
     if modern_count>1 and any(re.match(r'^\[\d+\]',t) for t in texts[middle+1:end]):continue
     orig_marker=re.match(r'^\[(\d+)\]',texts[i]);modern_marker=re.match(r'^\[(\d+)\]',texts[middle]);mismatch=bool(orig_marker and modern_marker and orig_marker[1]!=modern_marker[1])

     reward=2*s-.9-(.35 if mismatch else 0)-(.7 if s<.65 else 0)-.12*(orig_count-1)-.07*(modern_count-1)
     if scores[middle]>.8 and len(normalized[middle])>35:reward-=.8
     value=reward+dp[end]
     if value>dp[i]:dp[i]=value;choices[i]=(middle,end)
  if 0 in choices:
   i=0
   while i<n:
    middle,end=choices[i];chunks.append((i,middle,end));i=end
  else:
   # Explicitly preserve unresolved mixed blocks instead of calling ancient text a translation.
   candidates=[b for b in books.values() if any(y['year']==year for y in b['years'])]
   if candidates:
    target=candidates[0];yy=next(y for y in target['years'] if y['year']==year);yy['translationBlocks']=texts;yy['translationWarning']='译本本年的段落边界异常，保留未分段内容供核对。'
   else:unassigned.append(dict(year=year,blocks=texts))
   continue
 allocated=[]
 for start,middle,end in chunks:
  if middle==end:
   score,ix=best(texts[start]);possible=[v for v,b in books.items() if b['years'][0]['year']>=year>=b['years'][-1]['year']];v=refs[ix[0]][0] if ix and score>=.72 else (possible[0] if possible else None)
   if v:next(y for y in books[v]['years'] if y['year']==year).setdefault('translationBlocks',[]).append(texts[start])
   continue
  original='\n'.join(texts[start:middle]);modern='\n'.join(texts[middle:end]);s,indices=best(original);matched=indices if s>=.72 else []
  if matched:
   volume=refs[matched[0]][0];hu_indices=[refs[i][2] for i in matched]
  else:
   possible=[v for v,b in books.items() if b['years'][0]['year']>=year>=b['years'][-1]['year']]
   if not possible:unassigned.append(dict(year=year,original=original,modern=modern));continue
   filevol=tokens[start]['fileVolume'];volume=filevol if filevol in possible else possible[0];hu_indices=[]
  yy=next(y for y in books[volume]['years'] if y['year']==year)
  pair=dict(huIndices=hu_indices,sourceOriginal=original,modern=modern,score=round(s,3),kind='commentary' if re.match(r'^(臣光曰|太史公曰|贾谊|荀子|扬子|论曰)',re.sub(r'^\[\d+\]','',original)) else 'record',difference=not hu_indices,translationFiles=sorted(set(t['file'] for t in tokens[start:end])),reviewStatus='matched' if s>=.9 else 'check-source')
  yy.setdefault('bilingual',[])
  # Duplicate EPUB chapters have identical records. Keep all provenance without duplicating events.
  duplicate=next((p for p in yy['bilingual'] if norm(p['sourceOriginal'])==norm(original) and norm(p['modern'])==norm(modern) and set(p.get('translationFiles',[])).isdisjoint(pair['translationFiles'])),None)
  if duplicate:duplicate['translationFiles']=sorted(set(duplicate.get('translationFiles',[])+pair['translationFiles']));continue
  yy['bilingual'].append(pair);allocated.append(pair)
 if count%35==0:print('ALIGN',year,'tokens',len(tokens),'elapsed',round(time.monotonic()-started),flush=True)
# Merge groups that overlap the same Hu paragraph; retain each translated source fragment once.
for v,b in books.items():
 if v<=10:continue
 for y in b['years']:
  pairs=y.setdefault('bilingual',[]);ps=y['paragraphs']
  for pair in pairs:
   if pair['difference']:
    a=norm(pair['sourceOriginal']);target=next((p for p in pairs if not p['difference'] and a and any(a in norm(ps[j]['plain']) for j in p['huIndices'])),None)
    if target:pair['huIndices']=target['huIndices'].copy();pair['difference']=False
  merged=[]
  for pair in pairs:
   overlapping=[p for p in merged if not p['difference'] and not pair['difference'] and set(p['huIndices'])&set(pair['huIndices'])]
   if not overlapping:merged.append(pair);continue
   target=overlapping[0];target['huIndices']=sorted(set(target['huIndices']+pair['huIndices']));target['sourceOriginal']+='\n'+pair['sourceOriginal'];target['modern']+='\n'+pair['modern'];target['translationFiles']=sorted(set(target.get('translationFiles',[])+pair['translationFiles']))
   for other in overlapping[1:]:
    target['huIndices']=sorted(set(target['huIndices']+other['huIndices']));target['sourceOriginal']+='\n'+other['sourceOriginal'];target['modern']+='\n'+other['modern'];merged.remove(other)
  pairs=merged;y['bilingual']=pairs;covered={i for p in pairs for i in p['huIndices']};missing=sorted(set(range(len(ps)))-covered)
  y.update(translationMissing=missing,translationHeaders=headers.get(y['year'],[]),translationFiles=sorted(translation_sources.get(y['year'],[])),recorded=bool(ps),search=' '.join(p['plain'] for p in ps),noteCount=sum(r['kind']=='note' for p in ps for r in p['runs']))
  for pair in sorted((p for p in pairs if p['huIndices']),key=lambda p:p['huIndices'][0]):
   t=re.sub(r'^\[\d+\]','',pair['modern']);first=re.split(r'[。！？\n]',t)[0].strip();y['titles'].append(first[:42]+('…' if len(first)>42 else ''));y['anchors'].append(pair['huIndices'][0])
  for i in missing:
   if ps[i].get('structural'):continue
   t=re.sub(r'[\ue000-\uf8ff]','',ps[i]['plain']).strip()
   if t:y['titles'].append('原文：'+t[:38]+('…' if len(t)>38 else ''));y['anchors'].append(i)
  order=sorted(range(len(y['anchors'])),key=lambda i:y['anchors'][i]);y['titles']=[y['titles'][i] for i in order];y['anchors']=[y['anchors'][i] for i in order]
  if missing or any(p['difference'] or p['score']<.9 for p in pairs):report.append(dict(volume=v,year=y['year'],body=len(ps),missing=missing,differences=sum(p['difference'] for p in pairs),lowMatches=[dict(indices=p['huIndices'],score=p['score']) for p in pairs if not p['difference'] and p['score']<.9]))
 (out/f'volume{v}.json').write_text(json.dumps(b,ensure_ascii=False,separators=(',',':')))
cat=[];yearindex=collections.defaultdict(list)
for v,b in books.items():
 ys=b['years'];cat.append(dict(volume=v,title=b['title'].split('】')[0]+'】',dynasty=ys[0].get('dynasty','周'),start=ys[0]['year'],end=ys[-1]['year'],years=len(ys),bodyParagraphs=sum(len(y['paragraphs']) for y in ys),translationMissing=sum(len(y.get('translationMissing',[])) for y in ys)))
 for y in ys:yearindex[y['year']].append(v)
(out/'catalog.json').write_text(json.dumps(dict(schemaVersion=2,volumes=cat,yearVolumes=yearindex),ensure_ascii=False,separators=(',',':')))
# Lightweight per-volume search data, never the complete original+notes at initial page load.
for v,b in books.items():
 (out/f'search{v}.json').write_text(json.dumps([dict(year=y['year'],king=y['king'],reign=y['reign'],dynasty=y.get('dynasty','周'),reignLabel=y.get('reignLabel'),recorded=y['recorded'],titles=y['titles'],anchors=y['anchors'],paragraphCount=len(y['paragraphs']),pairCount=sum(not p['difference'] for p in y.get('bilingual',[])),text=' '.join([*[''.join(r['text'] for r in p['runs']) for p in y['paragraphs']],*[p['modern'] for p in y.get('bilingual',[])]])) for y in b['years']],ensure_ascii=False,separators=(',',':')))
summary=dict(volumes=len(books),uniqueYears=len(yearindex),first=max(yearindex),last=min(yearindex),sourceBody=sum(len(y['paragraphs']) for b in books.values() for y in b['years']),missing=sum(len(y.get('translationMissing',[])) for b in books.values() for y in b['years']),unassigned=unassigned,review=report)
pathlib.Path('full-alignment-report.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print('COMPLETE',json.dumps({k:v for k,v in summary.items() if k not in ('review','unassigned')},ensure_ascii=False),flush=True)

from finalize_full_book import finalize
finalize(out,args.translation)
