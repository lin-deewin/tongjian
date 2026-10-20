"""Place existing EPUB figures within the matching annual narrative.

Caption words, lunar month and adjacent source text are independent alignment
cues. --report-only writes candidates without modifying the published data.
"""
import argparse
import collections
import json
import math
import re
import zipfile
from pathlib import Path

from lxml import html
from build_seo import Sources
from translations.import_baiyang72 import classify_image_year

ROOT = Path(__file__).resolve().parents[1]
CN = re.compile(r'[^\u4e00-\u9fff]')
MONTH = re.compile(r'^(?:春|夏|秋|冬)?[，、,\s]*(?:闰)?(正|[一二三四五六七八九十]{1,3})月')
OVERRIDES_PATH = ROOT/'scripts/illustration-placements.json'


def clean(text):
    return CN.sub('', text).translate(str.maketrans({'淩':'凌','锺':'钟','隠':'隐','後':'后'}))


def grams(text, sizes=(2, 3, 4)):
    text = clean(text)
    return {text[i:i+n] for n in sizes for i in range(len(text)-n+1)}


def month_number(value):
    if value in ('正', '一'): return 1
    if value == '十': return 10
    if value.startswith('十'): return 10 + '一二三四五六七八九'.index(value[-1]) + 1
    return '一二三四五六七八九'.index(value) + 1


def narration(text):
    # Parenthetical geography and office glosses differ between the editions.
    result=[];depth=0
    for char in text:
        if char in '（(〔[':depth+=1
        elif char in '）)〕]' and depth:depth-=1
        elif not depth:result.append(char)
    return ''.join(result)


def similarity(a, b):
    if not a or not b: return 0
    overlap = len(a & b)
    return .65 * (2*overlap/(len(a)+len(b))) + .35*(overlap/min(len(a), len(b)))


def source_context(archive, picture, documents):
    file = picture.get('sourceFile')
    if not file or file not in archive.namelist(): return []
    if file not in documents:
        root = html.fromstring(archive.read(file).decode('utf-8'))
        bodies = root.xpath('//body')
        documents[file] = list(bodies[0]) if bodies else []
    nodes = documents[file]
    index = picture.get('sourceElement', 0)
    nearby = []
    for direction in (-1, 1):
        count = 0
        for i in range(index+direction, len(nodes) if direction>0 else -1, direction):
            node = nodes[i]
            if node.tag == 'h4': break
            if node.tag != 'p' or 'content' not in (node.get('class') or '').split(): continue
            text = ''.join(node.itertext()).strip()
            if len(clean(text)) < 12: continue
            nearby.append({'text': text, 'element': i, 'distance': abs(i-index)})
            count += 1
            if count >= 2: break
    return nearby


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--epub', type=Path, default=Path('/home/linqp/tmp/zztj2.epub'))
    parser.add_argument('--report-only', action='store_true')
    args = parser.parse_args()
    reviewed = json.loads(OVERRIDES_PATH.read_text())['images']
    data = ROOT/'dist'
    sources = Sources(data)
    years = collections.defaultdict(list)
    inventory = []
    illustration_paths = list((data/'illustrations').glob('volume[0-9]*.json'))
    for path in illustration_paths:
        doc = json.loads(path.read_text())
        for y in doc['years']:
            inventory.extend((doc['volume'], y['year'], dict(pic)) for pic in y['images'])
    for meta in sources.catalog['volumes']:
        book = sources.effective(meta['volume'])
        for year in book['years']:
            paragraph_months = []
            month = 1
            for p in year['paragraphs']:
                text = ''.join(r['text'] for r in p['runs'] if r['kind']=='text')
                values=[]
                for value in re.findall(r'(正|[一二三四五六七八九十]{1,3})月',text):
                    try:values.append(month_number(value))
                    except ValueError:pass
                if values:month=values[-1]
                paragraph_months.append(set(values or [month]))
            pairs = [p for p in year['bilingual'] if not p.get('difference') and p.get('huIndices')]
            covered = {i for p in pairs for i in p['huIndices']}
            pairs += [{'huIndices':[i], 'modern':'', 'sourceOriginal':p['plain']}
                      for i,p in enumerate(year['paragraphs']) if i not in covered]
            for pair in sorted(pairs, key=lambda p:p['huIndices'][0]):
                original = ''.join(year['paragraphs'][i]['plain'] for i in pair['huIndices'])
                modern = pair.get('modern','')
                titles=' '.join(title for anchor,title in zip(year.get('anchors',[]),year.get('titles',[])) if anchor in pair['huIndices'])
                text = titles + ' ' + modern + original
                years[year['year']].append({'volume':meta['volume'], 'anchor':max(pair['huIndices']), 'indices':pair['huIndices'],
                    'month':sorted(set().union(*(paragraph_months[i] for i in pair['huIndices']))), 'text':text,
                    'original':original, 'modern':modern,
                    'grams':grams(text)|set(clean(text)), 'bigrams':grams(narration(modern or original), (2,))})
    report = []
    result = collections.defaultdict(lambda: collections.defaultdict(list))
    documents = {}
    with zipfile.ZipFile(args.epub) as archive:
        for old_volume, original_year, pic in inventory:
            year=classify_image_year(pic.get('caption',''),pic.get('sourceYear',original_year))
            if year not in years:year=original_year
            basename=Path(pic['src']).name
            review=reviewed.get(basename)
            if review and review.get('caption'):pic['caption']=review['caption']
            candidates = years[year]
            caption = pic.get('caption','')
            tokens = re.split(r'\s+', caption.strip(), maxsplit=1)
            query = tokens[1] if len(tokens)>1 else re.sub(r'^.*?年', '', caption)
            month_values = []
            for m in re.findall(r'(正|[一二三四五六七八九十]{1,3})月', tokens[0]):
                try: month_values.append(month_number(m))
                except ValueError: pass
            context = source_context(archive, pic, documents) if pic.get('sourceYear',year)==year else []
            context_grams = [grams(narration(c['text']),(2,)) for c in context]
            meaningful=re.sub(r'第[一二三四五六七八九十]+次','',query)
            for generic in ['政府','帝国','中央','之战','之役','战区','进攻','攻击','讨伐','全图','形势','失败','大胜']:
                meaningful=meaningful.replace(generic,'')
            aliases={'英布':'黥布','刘彻':'武帝','刘骜':'成帝','李隆基':'玄宗','李亨':'肃宗',
                     '李豫':'代宗','李适':'德宗','李诵':'顺宗','李纯':'宪宗','李恒':'穆宗',
                     '李湛':'敬宗','李昂':'文宗','李炎':'武宗','李忱':'宣宗','李俨':'僖宗',
                     '李晔':'昭宗','李柷':'昭宣帝','郭荣':'世宗','元修':'孝武帝',
                     '拓跋宏':'孝文帝','西羌':'羌人','桀燕':'燕'}
            expanded=meaningful
            for name,alias in aliases.items():expanded=expanded.replace(name,alias)
            query_grams = grams(meaningful)|grams(expanded)
            relation=re.search(r'([秦齐楚赵魏韩燕宋吴越晋鲁郑卫蜀周])(?:国)?(?:灭|攻|伐|击|败)([秦齐楚赵魏韩燕宋吴越晋鲁郑卫蜀周])',expanded)
            if relation:query_grams.update([relation[1],relation[2]])
            weights = {}
            for g in query_grams:
                frequency = sum(g in c['grams'] for c in candidates)
                if frequency: weights[g] = max(1,len(g)-1)*(1+math.log((len(candidates)+1)/(frequency+1)))
            total = sum(weights.values())
            ranked = []
            for index,c in enumerate(candidates):
                hits = [g for g in weights if g in c['grams']]
                caption_score = sum(weights[g] for g in hits)/total if total else 0
                similarities = [similarity(g,c['bigrams']) for g in context_grams]
                context_score = max(similarities,default=0)
                date = 0
                if month_values:
                    date = .12 if any(min(month_values)<=m<=max(month_values) for m in c['month']) else -.12
                score = .78*caption_score + .22*context_score + date
                ranked.append({'index':index,'score':score,'caption':caption_score,'context':context_score,
                               'matched':sorted(hits,key=len,reverse=True)[:8]})
            ranked.sort(key=lambda x:x['score'],reverse=True)
            chosen = candidates[ranked[0]['index']] if ranked else None
            method = 'caption-source-month'
            overview=bool(re.search(r'形势|疆域|版图|世系|行政区|十三姓|开拓疆土',query)) and not bool(re.search(r'攻|战|伐|夺|灭|兵变|叛变|抗|迁|退|收复|入援',query))
            if overview and candidates and (not ranked or ranked[0]['context']<.3):
                chosen=candidates[0];method='annual-overview'
            basename = Path(pic['src']).name
            if review:
                v,yr,anchor=review['volume'],review['year'],review['afterParagraph']
                if year != yr: raise ValueError((basename,year,yr))
                paragraph=next(y for y in sources.canonical(v)['years'] if y['year']==year)['paragraphs'][anchor]
                import hashlib
                digest=hashlib.sha256(json.dumps(paragraph,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
                if digest!=review['sourceParagraphSHA256']:raise ValueError(f'Stale reviewed picture anchor: {basename}')
                chosen = next(c for c in candidates if c['volume']==v and anchor in c['indices'])
                method = 'reviewed-'+review.get('kind','event')
            if not chosen:
                volume,anchor = old_volume,None
                method = 'unrecorded-year-overview'
            else:
                volume,anchor = chosen['volume'],chosen['anchor']
                if not weights and not context_grams:
                    chosen=candidates[0];volume,anchor=chosen['volume'],chosen['anchor'];method='annual-overview'
            original_anchor=pic.get('afterParagraph')
            pic['year'] = year
            pic['afterParagraph'] = anchor
            pic['placementNote'] = (review or {}).get('placementNote', '本年形势与背景参考图' if anchor is None or method.endswith('overview') else '')
            result[volume][year].append(pic)
            report.append({'src':pic['src'],'caption':caption,'year':year,'originalYear':original_year,'oldVolume':old_volume,
                'volume':volume,'afterParagraph':anchor,'originalAnchor':original_anchor,'method':method,
                'chosenText':chosen['text'][:650] if chosen else '',
                'availableCaptionTerms':len(weights),
                'candidates':[{'volume':candidates[r['index']]['volume'],'anchor':candidates[r['index']]['anchor'],
                    'month':candidates[r['index']]['month'],'score':round(r['score'],3),
                    'captionScore':round(r['caption'],3),'contextScore':round(r['context'],3),
                    'matched':r['matched'],'text':candidates[r['index']]['text'][:500]}
                    for r in ranked[:3]],
                'sourceContext':[{'element':c['element'],'text':c['text'][:250]} for c in context]})
    report_path = ROOT/'artifacts/illustration-placement/placement-report.json'
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2))
    if not args.report_only:
        for meta in sources.catalog['volumes']:
            volume=meta['volume']
            path=data/f'illustrations/volume{volume}.json'
            if result.get(volume):
                entries=[{'year':y['year'],'images':result[volume][y['year']]}
                         for y in sources.canonical(volume)['years'] if result[volume].get(y['year'])]
                path.write_text(json.dumps({'volume':volume,'years':entries},ensure_ascii=False,separators=(',',':')))
                meta['illustrations']=str(path.relative_to(data))
            elif path.exists() or meta.get('illustrations'):
                path.write_text(json.dumps({'volume':volume,'years':[]},ensure_ascii=False,separators=(',',':')))
                meta['illustrations']=str(path.relative_to(data))
        (data/'catalog.json').write_text(json.dumps(sources.catalog,ensure_ascii=False,separators=(',',':')))
    print(json.dumps({'images':len(report),'withinNarrative':sum(p['afterParagraph'] is not None for p in report),
                      'unrecordedYear':sum(p['afterParagraph'] is None for p in report),'report':str(report_path)}))


if __name__=='__main__':main()
