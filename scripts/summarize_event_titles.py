"""Apply source-bound title edits and create pending browsing headings."""
import argparse
import hashlib
import json
import re
from pathlib import Path

OVERRIDES = Path(__file__).with_name('event-title-overrides.json')
DATE = re.compile(r'^(?:[春夏秋冬](?:季|天)?(?:，|,)?|闰?[正一二三四五六七八九十]+月(?:间)?(?:，|,)?|[甲乙丙丁戊己庚辛壬癸][子丑寅卯辰巳午未申酉戌亥](?:朔|晦)?(?:夜|旦)?(?:（[^）]*）)?(?:，|,)?|[（(][^）)]*[）)](?:，|,)?|这时(?:候)?[，,]?|当时[，,]?|于是[，,]?|起初[，,]?|当初[，,]?|初[，,]|后来[，,]?|从前[，,]?|(?:是岁|是月|当月|闰月|当夜|翌日|次日|当日)[，,]?)')
REPLACEMENTS = [('国国君','君'),('国国王','王'),('国皇帝','帝'),('国军队','军'),('率领军队','率军'),('率领兵众','率军'),('率军队','率军'),('派遣','遣'),('派人','遣人'),('任命','任'),('攻打','攻'),('进攻','攻'),('夺取','取'),('攻克','克'),('去世','卒'),('其子即位为','子继位为'),('其子继位为','子继位为'),('其子即位','子继位'),('即位为','继位为'),('举行会议','会盟'),('举行会盟','会盟'),('自称为王','称王'),('称为皇帝','称帝'),('投降了','投降'),('返回了','返回'),('占领了','占领'),('打败了','击败'),('全部',''),('再次',''),('首次','始'),('准备要','欲'),('打算','拟'),('想要','欲'),('下令说','下诏'),('下诏说','下诏')]
TOPICS = [('变法','变法'),('法令','法令'),('仁义','仁义'),('赋税','赋税'),('屯田','屯田'),('水利','水利'),('均田','均田'),('科举','科举'),('盐铁','盐铁'),('合纵','合纵'),('连横','连横'),('纳谏','纳谏'),('用人','用人'),('贤才','用人'),('人才','用人'),('节俭','节俭'),('奢侈','奢俭'),('信誉','守信'),('信用','守信'),('信义','信义'),('孝','孝道'),('兵法','用兵'),('征讨','征战'),('军队','军事'),('士兵','军事'),('治国','治国'),('治理','治政'),('法度','法度'),('礼','礼制'),('皇太子','储位'),('太子','储位'),('皇后','后位'),('百姓','民政'),('灾','灾异')]
RANKS = re.compile(r'(?:侍卫马军都指挥使|侍卫步军都指挥使|殿前都点检|右龙武将军|左龙武将军|征[东西南北]大将军|征[东西南北]将军|前将军|后将军|大将军|左将军|右将军|中书令|尚书令|右仆射|左仆射|侍中|大司马|司空|司徒|太尉|参军|太守|刺史|都督)')

def clean(text):
    text = re.sub(r'〔[^〕]*〕', '', text)
    text = re.sub(r'[\ue000-\uf8ff>]', '', text)
    text = re.sub(r'\[\d+\]', '', text).strip()
    text = re.sub(r'[“「]$', '', text).strip()
    text = re.sub(r'^原文[：:]\s*', '', text)
    while True:
        stripped = DATE.sub('', text, count=1).lstrip(' ，,。；;：:')
        if stripped == text:
            break
        text = stripped
    return text

def compress(text):
    text = clean(text).replace(',', '，')
    for old, new in REPLACEMENTS:
        text = text.replace(old, new)
    text = re.sub(r'(齐|秦|魏|赵|韩|燕|楚|鲁|宋|卫)国', r'\1', text)
    text = re.sub(r'([前后](?:秦|燕|赵|凉|蜀|汉|周|唐|晋))国', r'\1', text)
    return text.strip(' ，,。；;：:！？“”「」')

def subject(text):
    # Retain named subject from the opening clause; do not resolve pronouns.
    text = RANKS.sub('', compress(text))
    text = re.split(r'[，。；：“「]|(?:率|遣|任|劝|向|对|欲|拟|命|攻|说|言|奏|请|上表|下诏|封|以|是|有|曾|为|在)', text, maxsplit=1)[0]
    text = re.sub(r'的(?:弟弟|兄弟|儿子|部下|弟|子)$', '', text)
    return text if 1 <= len(text) <= 12 else ''

def summarize(text, original):
    text = clean(text) or clean(original)
    text = re.sub(r'^天刚蒙蒙亮的时候[，,]?', '', text)
    if re.match(r'^(?:臣(?:司马)?光曰|臣司马光曰|臣光言)', text):
        topic = next((label for word, label in TOPICS if word in text), '史事得失')
        return '司马光论' + topic
    if text.startswith('太史公曰'):
        topic = next((label for word, label in TOPICS if word in text), '史事得失')
        return '太史公论' + topic
    opening = re.split(r'[。！？\n]', text)[0]
    # Dialogue is described as dialogue, rather than presenting quoted advice as fact.
    speech = re.search(r'(?:说|说道|道|曰|问|答|对|称|上言|上疏|奏报|奏言|奏|认为)[：:]?[“「]', opening)
    if speech:
        prefix = compress(opening[:speech.start()])
        who = subject(opening)
        topic = next((label for word, label in TOPICS if word in text), '')
        if re.search(r'劝|谏|上疏|上言|奏', prefix):
            if who and topic:
                return who + '进言论' + topic
            if 2 <= len(prefix) <= 26:
                return prefix + '进言'
        if who and topic:
            return who + '论' + topic
        if 2 <= len(prefix) <= 26:
            return prefix + '对话'
        if who:
            return who + '议事'
    clauses = [compress(c) for c in re.split(r'[，；]', opening)]
    clauses = [c for c in clauses if c]
    # Use complete clauses; never cut a phrase at an arbitrary character count.
    if clauses:
        if len(clauses)>1 and not re.search(r'攻|伐|战|败|遣|任|封|卒|死|杀|诛|立|请|奏|归|还|进|出|入|有|欲|拟|以|为|患|闻|至|使|告|发|命|修|改|减|增|废|会|降|置|罢|薨|反|乱|围|取|克|救|征|讨', clauses[0]):
            # Avoid headings that consist only of a list of offices and names.
            predicate = next((c for c in clauses[1:] if re.match(r'^(全都|皆|都|并|俱|尽|一同|全部)?(?:投降|归降|降|反|叛|卒|死|入|出|归|还|被杀)', c)), None)
            if predicate:
                first_name = RANKS.sub('', clauses[0]).split('、')[0]
                return first_name + ('等' if '、' in opening else '') + re.sub(r'^(全都|皆|都|并|俱|尽|一同|全部)', '', predicate)
        first = RANKS.sub('', clauses[0]) if len(clauses[0]) > 24 else clauses[0]
        if 2 <= len(first) <= 28:
            title = first
            if len(clauses) > 1 and len(title) + len(clauses[1]) < 25 and not re.match(r'^(他|她|其|这|那|因|但|而|又|却|并|已|就|将|时|是)', clauses[1]):
                title += '，' + clauses[1]
            return title
        # A long declarative clause can often be reduced to its subject and action.
        match = re.match(r'^(.{1,12}?)(?:率领|率)(?:.{1,25}?)(攻|伐|围|救|征讨)(.{1,12})$', first)
        if match:
            return match[1] + match[2] + match[3]
        match = re.match(r'^(.{1,12}?)(?:在|于).{1,30}?(击败|大败|击破|打败)(.{1,12})$', first)
        if match:
            return match[1] + match[2] + match[3]
        # Keep the full clause if it cannot safely be condensed. Accuracy wins over length.
        if len(first)<2:
            return {'旱':'旱灾记事','寒':'异常寒冷记事','喜':'校勘残文（待核对）'}.get(first, '本段记事（待核对）')
        return first
    return compress(original) or '本段记事'

def digest(paragraph):
    return hashlib.sha256(json.dumps(paragraph, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def review_group(year, anchor):
    pair = next((p for p in year.get('bilingual', [])
                 if not p.get('difference') and p.get('huIndices')
                 and p['huIndices'][0] == anchor), None)
    return pair['huIndices'] if pair else [anchor]

def update(data_dir, overrides_path=OVERRIDES):
    data_dir = Path(data_dir)
    overrides = json.loads(Path(overrides_path).read_text())
    report = {'rewritten': 0, 'pending': 0, 'longTitles': [], 'volumes': []}
    volumes = [v for v in range(2, 295) if (data_dir / f'volume{v}.json').exists()]
    for volume in volumes:
        path = data_dir / f'volume{volume}.json'
        b = json.loads(path.read_text())
        before = json.dumps({k: v for k, v in b.items() if k not in ('indexKind', 'titleMethod', 'titleReview', 'years')}, sort_keys=True)
        unchanged = [{k: v for k, v in y.items() if k != 'titles'} for y in b['years']]
        reviewed = overrides.get(str(volume), {})
        for y in b['years']:
            titles = []
            for anchor in y['anchors']:
                p = y['paragraphs'][anchor]
                original = ''.join(r['text'] for r in p['runs'] if r['kind'] == 'text')
                pair = next((p for p in y.get('bilingual', []) if not p.get('difference') and p['huIndices'] and p['huIndices'][0] == anchor), None)
                row = reviewed.get(f"{y['year']}:{anchor}")
                if row:
                    if row['sourceHash'] != digest(p):
                        raise ValueError(f'Stale reviewed title: {volume}/{y["year"]}/{anchor}')
                    if row.get('reviewStatus') == 'rewritten':
                        indices = review_group(y, anchor)
                        if row.get('reviewedIndices') != indices or row.get('groupHash') != digest([y['paragraphs'][i] for i in indices]):
                            raise ValueError(f'Stale reviewed passage group: {volume}/{y["year"]}/{anchor}')
                        report['rewritten'] += 1
                    else:
                        report['pending'] += 1
                    title = row['title']
                else:
                    title = summarize(pair['modern'] if pair else original, original)
                    report['pending'] += 1
                titles.append(title)
                if len(title) > 36:
                    report['longTitles'].append({'volume': volume, 'year': y['year'], 'anchor': anchor, 'title': title})
            assert len(titles) == len(y['titles']) == len(y['anchors'])
            y['titles'] = titles
        total = sum(len(y['titles']) for y in b['years'])
        complete_review = report['rewritten'] and all(
            overrides.get(str(volume), {}).get(f"{y['year']}:{a}", {}).get('reviewStatus') == 'rewritten'
            for y in b['years'] for a in y['anchors'])
        b['titleReview'] = {'rewritten': sum(1 for y in b['years'] for a in y['anchors'] if overrides.get(str(volume), {}).get(f"{y['year']}:{a}", {}).get('reviewStatus') == 'rewritten'), 'total': total}
        b['indexKind'] = 'editorialSummary' if complete_review else 'mixedSummary' if b['titleReview']['rewritten'] else 'automaticSummary'
        b['titleMethod'] = '逐条按对应正文重写并校对' if complete_review else f"已按正文重写 {b['titleReview']['rewritten']} / {total} 条，其余待逐条校对"
        assert unchanged == [{k: v for k, v in y.items() if k != 'titles'} for y in b['years']]
        assert before == json.dumps({k: v for k, v in b.items() if k not in ('indexKind', 'titleMethod', 'titleReview', 'years')}, sort_keys=True)
        path.write_text(json.dumps(b, ensure_ascii=False, separators=(',', ':')))
        search_path = data_dir / f'search{volume}.json'
        rows = json.loads(search_path.read_text()) if search_path.exists() else [dict(year=y['year'],king=y['king'],reign=y['reign'],dynasty=y.get('dynasty','周'),reignLabel=y.get('reignLabel'),recorded=y['recorded'],titles=y['titles'],anchors=y['anchors'],paragraphCount=len(y['paragraphs']),pairCount=sum(not p.get('difference') for p in y.get('bilingual',[])),text=' '.join([''.join(r['text'] for r in p['runs']) for p in y['paragraphs']]+[p['modern'] for p in y.get('bilingual',[])]+y.get('translationBlocks',[]))) for y in b['years']]
        for row, y in zip(rows, b['years'], strict=True):
            assert row['year'] == y['year'] and row['anchors'] == y['anchors']
            row['titles'] = y['titles']
            row['indexKind'] = b['indexKind']
            row['titleReview'] = b['titleReview']
        search_path.write_text(json.dumps(rows, ensure_ascii=False, separators=(',', ':')))
        report['volumes'].append({'volume': volume, 'indexKind': b['indexKind'], **b['titleReview']})
    cat_path = data_dir / 'catalog.json'
    cat = json.loads(cat_path.read_text()) if cat_path.exists() else {'volumes': []}
    for meta in cat['volumes']:
        if meta['volume'] in volumes:
            info = next(v for v in report['volumes'] if v['volume']==meta['volume'])
            meta['indexKind'] = info['indexKind']
            meta['titleReview'] = {k: info[k] for k in ('rewritten', 'total')}
    if cat_path.exists():
        cat_path.write_text(json.dumps(cat, ensure_ascii=False, separators=(',', ':')))
    (data_dir / 'event-title-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k not in ('longTitles', 'volumes')}, ensure_ascii=False), f"long titles: {len(report['longTitles'])}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--data', type=Path, default=Path('dist'))
    args = parser.parse_args()
    update(args.data)
