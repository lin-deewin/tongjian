"""Check every existing illustration in generated annual articles and its paragraph position."""
import json,collections,sys
from pathlib import Path
from lxml import html
root=Path(__file__).resolve().parents[1]; dist=root/'dist'
cache={};count=0; null=0; expected=collections.defaultdict(list)
for p in (dist/'illustrations').glob('volume*.json'):
 d=json.loads(p.read_text());v=d['volume']
 for y in d['years']:
  yr=y['year'];path=dist/f'year/{"bce" if yr>0 else "ce"}-{abs(yr)}/index.html'
  if path not in cache:
   raw=path.read_text().split('<!-- annual-source -->')[1].split('<!-- /annual-source -->')[0]
   cache[path]=html.fromstring(raw)
  tree=cache[path];section=tree.get_element_by_id(f'volume-{v}-year-{yr}')
  actual=section.xpath('.//figure//img/@src')
  assert len(actual)==len(y['images']),(v,yr,len(actual),len(y['images']))
  for pic in y['images']:
   assert (dist/pic['src']).is_file(),pic['src']
   images=section.xpath('.//figure[.//img[contains(@src,$src)]]',src=pic['src'])
   assert len(images)==1,(v,yr,pic['src'])
   previous=images[0].xpath('preceding-sibling::div[contains(@class,"comparison-row")][1]')
   anchor=pic['afterParagraph']
   if anchor is None:
    assert not previous,(v,yr,pic['src']);null+=1
   else:
    assert previous,(v,yr,pic['src'])
    indices=[int(x) for x in previous[0].xpath('.//p[@data-index]/@data-index')]
    assert anchor==max(indices),(v,yr,pic['src'],anchor,indices)
   expected[(v,yr)].append(pic['src']);count+=1
assert count>0, "No illustrations audited"
summary={'figures':count,'narrative':count-null,'background':null,'annualArticles':len(cache),'staticOrder':'passed'}
(root/'artifacts/illustration-placement/static-render-audit.json').write_text(json.dumps(summary,indent=2)+'\n')
print(summary)
