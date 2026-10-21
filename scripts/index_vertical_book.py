"""Map reader paragraph anchors to uploaded traditional source blocks."""
import json,re,html
from pathlib import Path
from lxml import etree
from opencc import OpenCC
cc=OpenCC('t2s')
root=Path(__file__).resolve().parents[1]/'dist'
def norm(s):return re.sub(r'[^\w]','',cc.convert(s))
matched=total=0
for volume in range(1,295):
 path=root/'vertical-book'/f'chapter-{volume+2:03}.json'
 chapter=json.loads(path.read_text());blocks=re.split(r'<br/>\s*<br/>',chapter['html'])
 # Balance source markup independently after splitting the EPUB's long paragraphs.
 blocks=[re.sub(r'</?(?:div|p|h1)[^>]*>','',block) for block in blocks]
 plain=[]
 for block in blocks:
  dom=etree.HTML('<div>'+block+'</div>');plain.append(norm(''.join(dom.itertext())))
 offsets=[];text=''
 for s in plain:offsets.append(len(text));text+=s
 anchors={};book=json.loads((root/f'volume{volume}.json').read_text())
 import bisect
 for year in book['years']:
  for i,p in enumerate(year['paragraphs']):
   total+=1;value=norm(p['plain']);pos=-1
   for width in dict.fromkeys((32,20,12,min(len(value),8))):
    if width>=4 and len(value)>=width:
     pos=text.find(value[:width])
     if pos>=0 and text.count(value[:width])==1:break
     pos=-1
   if pos>=0:
    anchors[f"{year['year']}:{i}"]=max(0,bisect.bisect_right(offsets,pos)-1);matched+=1
 chapter['blocks']=blocks;chapter['anchors']=anchors
 path.write_text(json.dumps(chapter,ensure_ascii=False))
print(f'Mapped {matched}/{total} original paragraph anchors; unmatched anchors remain explicitly unavailable.')
