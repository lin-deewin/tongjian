"""Place captioned figures near matching records; broad maps stay at year opening."""
import json,re,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def clean(text):return re.sub(r'[^\u4e00-\u9fff]','',text)
def main():
 counts={'record':0,'year':0}
 for v in range(1,295):
  path=ROOT/f'dist/volume{v}.json';book=json.loads(path.read_text())
  picture_path=ROOT/f'dist/illustrations/volume{v}.json'
  if picture_path.exists():
   pictures={e['year']:e['images'] for e in json.loads(picture_path.read_text())['years']}
   for y in book['years']:y['yearIllustrations']=pictures.get(y['year'],[])
  for y in book['years']:
   for pic in y.get('yearIllustrations',[]):
    caption=re.sub(r'^.*?年\s*','',pic.get('caption',''))
    terms=clean(caption)
    scores=[]
    for pair in y['bilingual']:
     if pair.get('difference') or not pair['huIndices'] or pair.get('kind')=='commentary':continue
     text=clean(pair['modern']+' '+pair.get('sourceOriginal',''))
     best=max((size for size in range(4,min(12,len(terms))+1) if any(terms[i:i+size] in text for i in range(len(terms)-size+1))),default=0)
     scores.append((best,max(pair['huIndices'])))
    scores.sort(reverse=True)
    anchor=None
    if scores and scores[0][0]>=4 and (len(scores)==1 or scores[0][0]>scores[1][0]):anchor=scores[0][1]
    if re.search(r'国际形势|全图|疆域|行政区|版图',caption):anchor=None
    if v==1 and y['year']==403 and '三家分晋' in caption and '之前' not in caption:anchor=0
    pic['afterParagraph']=anchor
    pic['placementNote']='本年形势与背景参考图' if anchor is None else ''
    counts['year' if anchor is None else 'record']+=1
  entries=[{'year':y['year'],'images':y['yearIllustrations']} for y in book['years'] if y.get('yearIllustrations')]
  if entries:picture_path.write_text(json.dumps({'volume':v,'years':entries},ensure_ascii=False,separators=(',',':')))
 print(json.dumps(counts,ensure_ascii=False))
if __name__=='__main__':main()
