import json,re,pathlib,zipfile,lxml.html as H
src=next(pathlib.Path('/workspace/scratch/cafe6334cb34/upload').glob('*.epub'))
z=zipfile.ZipFile(src); root=H.fromstring(z.read('OEBPS/text00003.html'))
ps=[p.text_content() for p in root.xpath('//p')]
def split(t):
 out=[];buf='';depth=0;kind='text'
 for pos,c in enumerate(t):
  if c=='〔' and depth and (t[pos:].startswith('〔【章：') or t[pos:].startswith('〔今此书年')):
   buf+=c;continue
  if c=='〔':
   if depth==0:
    if buf:out.append({'kind':'text','text':buf})
    buf='';kind='note'
   depth+=1;buf+=c
  elif c=='〕':
   buf+=c;depth-=1
   if depth==0:out.append({'kind':'note','text':buf});buf='';kind='text'
  else:buf+=c
 if buf:out.append({'kind':kind,'text':buf})
 assert depth==0
 assert ''.join(x['text'] for x in out)==t
 return out
def plain(t):return ''.join(r['text'] for r in split(t) if r['kind']=='text')
titles={403:['三晋获封诸侯','司马光论礼、分与名','追叙：智氏覆亡与晋阳之战','追叙：豫让报仇','追叙：赵、魏、韩世系','魏文侯用人与吴起事迹','燕愍公去世'],402:['周威烈王去世，安王继位','楚声王被杀，悼王继位'],401:['秦伐魏，至阳孤'],400:['三晋伐楚；郑围韩阳翟','韩、赵、秦君主更替'],399:['王子定奔晋','虢山崩，壅河'],398:['楚围郑；郑人杀驷子阳'],397:['日食','聂政刺杀韩相侠累'],396:['郑繻公被弑','宋悼公去世'],394:['齐伐鲁；郑负黍归韩'],393:['魏伐郑','晋烈公去世'],391:['秦伐韩，取六邑','田和迁齐康公于海上'],390:['秦晋战于武城','齐伐魏；鲁败齐师'],389:['秦侵晋','田和求为诸侯'],387:['秦伐蜀，取南郑','魏文侯去世，武侯继位','吴起在魏、入楚与变法','秦、赵、韩君主更替'],386:['田和获封诸侯','赵公子朝作乱'],385:['秦献公被拥立','韩伐郑、宋','齐太公去世'],383:['魏败赵师于兔台'],382:['日全食'],381:['吴起遇害；楚肃王即位'],380:['齐伐燕；三晋伐齐'],379:['赵袭卫不克','齐康公去世，田氏并齐'],378:['狄败魏师','三晋伐齐；晋靖公继位'],377:['蜀伐楚，取兹方','子思论用人与君臣谏诤','鲁、韩君主更替'],376:['周安王去世','三晋废晋靖公，分其地'],375:['日食','韩灭郑，迁都新郑','赵成侯继位'],373:['燕、鲁、魏伐齐','燕、宋、卫君主更替'],372:['赵伐卫','魏败赵师于北蔺'],371:['魏伐楚，取鲁阳','韩哀侯遇害','魏武侯去世，国内争立'],370:['齐威王朝周','赵伐齐；魏败赵','齐威王整顿吏治','楚、宋君主更替'],369:['日食；周烈王去世','韩赵攻魏，意见相左而退','太史公论魏国未被瓜分']}
years=[]
for year in range(403,368,-1):
 king='威烈王' if year>=402 else '安王' if year>=376 else '烈王'
 rn=426-year if king=='威烈王' else 402-year if king=='安王' else 376-year
 years.append({'year':year,'king':king,'reign':rn,'heading':'','paragraphs':[],'titles':titles.get(year,[])})
by={y['year']:y for y in years}; current=None;king='威烈王';intro=[]
nums={'〇':0,'○':0,'零':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
def cn(t):
 if t=='元':return 1
 if '十' in t:
  a,b=t.split('十');return (nums[a] if a else 1)*10+(nums[b] if b else 0)
 return nums[t]
for t in ps:
 base=plain(t)
 if base in ['威烈王','安王','烈王']:
  king=base
  if current:current['after'].append(t)
  else:intro.append(t)
  continue
 m=re.fullmatch(r'([元一二三四五六七八九十]+)年',base)
 if m:
  rn=cn(m[1]);y=(426-rn if king=='威烈王' else 402-rn if king=='安王' else 376-rn)
  current=by[y];current['heading']=t;current['headingRuns']=split(t);current['after']=[]
 elif current:current['paragraphs'].append({'runs':split(t),'plain':base})
 else:intro.append(t)
for y in years:
 y.setdefault('after',[]);y['recorded']=bool(y['paragraphs']);y['search']=' '.join(p['plain'] for p in y['paragraphs']);y['noteCount']=sum(r['kind']=='note' for p in y['paragraphs'] for r in p['runs'])
 if y['year']==371:y['warning']='上传版本的“五年”年头误写为“己酉、前三七二”。年表按周烈王五年定位为前371年；原文保留上传版本字样。'
 y['anchors']=[]
 if y['year']==403:y['anchors']=[0,1,8,17,19,21,30]
 elif y['year']==387:y['anchors']=[0,1,2,6]
 else:
  for i,p in enumerate(y['paragraphs']):
   if not p['plain'].startswith(('臣光曰','太史公曰')):y['anchors'].append(i)
  y['anchors']=y['anchors'][:len(y['titles'])]
  y['anchors']={400:[0,2],390:[0,1],378:[0,1],377:[0,1,4],373:[0,3],370:[0,1,3,4],369:[0,2,3]}.get(y['year'],y['anchors'])
out={'volume':1,'title':root.xpath('//h3')[0].text_content(),'source':'上传的《资治通鉴 胡三省注版》EPUB · OEBPS/text00003.html','intro':[{'runs':split(t),'plain':plain(t)} for t in intro],'years':years}
# Every source paragraph is retained exactly, including year/king headings.
assert sum(len(y['paragraphs'])+bool(y['heading'])+len(y['after']) for y in years)+len(intro)==len(ps)
assert len(years)==35 and years[0]['year']==403 and years[-1]['year']==369
pathlib.Path('dist/volume1.json').write_text(json.dumps(out,ensure_ascii=False,separators=(',',':')))
print(json.dumps({'years':35,'recorded':sum(y['recorded'] for y in years),'paragraphs':len(ps),'unrecorded':[y['year'] for y in years if not y['recorded']],'source_preserved':True},ensure_ascii=False))
