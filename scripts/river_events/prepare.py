"""Prepare broad recall candidates; these are never certified events."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'artifacts/river-audit'
PATTERNS={
'disaster':r'地震|旱|大水|水灾|水災|蝗|疫|大风|大風|雨雹|大雹|霖雨|霜杀|霜殺|山崩|河决|河決|江溢|海溢|水溢|水潦|洪水|大雨|水漂|风拔|風拔',
'famine':r'饥|飢|饑|饿|餓|人相食|民相食|谷贵|穀貴|米贵|米貴|乏食|绝粮|絕糧',
'war':r'战|戰|攻|伐|讨|討|击|擊|围|圍|破|败|敗|寇|侵|军|軍|兵|叛'}

def main():
 OUT.mkdir(parents=True,exist_ok=True)
 chunks=[[] for _ in range(10)]
 for v in range(1,295):
  b=json.loads((ROOT/f'dist/volume{v}.json').read_text())
  for y in b['years']:
   for a,p in enumerate(y['paragraphs']):
    text=p.get('plain','')
    if p.get('structural') or not text.strip():continue
    kinds=[k for k,rx in PATTERNS.items() if re.search(rx,text)]
    if not kinds:continue
    titles=[t for t,n in zip(y['titles'],y['anchors']) if n==a]
    chunks[min((v-1)//30,9)].append(dict(id=f'v{v}-y{y["year"]}-p{a}',volume=v,year=y['year'],anchor=a,categories=kinds,titles=titles,text=text))
 for i,rows in enumerate(chunks,1):
  (OUT/f'candidates-{i:02}.json').write_text(json.dumps(rows,ensure_ascii=False,indent=1))
  print(i,len(rows),sum(len(x['text']) for x in rows))
if __name__=='__main__': main()
