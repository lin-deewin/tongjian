"""Build the source-bound '通鉴中的君主之死' topic, without changing book data.

Classification is editorially reviewed in scripts/rulers/reviewed.json. The build
never infers death causes from names, titles, or keyword searches. Source changes
invalidate bindings; --bind-reviewed-sources is only for reviewed source updates.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = [
    ('killed', '被杀／赐死', '#9d513d', '兵变、刺杀、俘后处死等；赐死而方式未述也在此类。'),
    ('suicide', '自尽', '#b7784a', '包括被逼自尽；不因为发生于战败后便归为战死。'),
    ('poison', '中毒／鸩杀', '#756187', '原文明记置毒、酖杀或中毒；不自动确定投毒者。'),
    ('starved', '困围饿死', '#ac8950', '原文明确记断食困围或饿而死。'),
    ('battle', '交战身亡', '#8c624d', '明确在交战中被杀；俘虏后处死列被杀。'),
    ('accident', '意外伤亡', '#698087', '如举鼎伤亡、坠马；不推断现代伤病诊断。'),
    ('illness', '病中去世', '#285342', '死亡上下文明记疾、不豫、疽等，不等同现代医学诊断。'),
    ('medication', '服药相关', '#69784d', '原文明确将服药与伤生相联系，不等同他人投毒。'),
    ('disputed', '记载存疑／多因', '#ae9f83', '正文有异说，或饮食限制、病情、服药等并见而不足单独归因。'),
    ('unknown', '所引原文未述', '#c5c3b8', '仅记崩、薨、卒等，或所引段未述死因，不能推断寿终正寝。'),
]
ERAS = [('warring', '周与战国'), ('han', '秦与两汉'), ('division', '魏晋南北朝'),
        ('tang', '隋唐及隋末诸国'), ('five', '五代十国及契丹')]
NAMES = {'汉高帝':'刘邦', '汉惠帝':'刘盈', '汉文帝':'刘恒', '汉景帝':'刘启', '汉武帝':'刘彻',
         '汉昭帝':'刘弗陵', '汉宣帝':'刘询', '汉元帝':'刘奭', '汉成帝':'刘骜', '汉光武帝':'刘秀',
         '汉少帝':'刘辩', '汉献帝':'刘协', '秦始皇':'嬴政', '秦二世':'胡亥',
         '唐高祖':'李渊', '唐太宗':'李世民', '唐高宗':'李治', '唐中宗':'李显', '唐睿宗':'李旦',
         '唐玄宗':'李隆基', '唐肃宗':'李亨', '唐代宗':'李豫', '唐德宗':'李适', '唐顺宗':'李诵',
         '唐宪宗':'李纯', '唐穆宗':'李恒', '唐敬宗':'李湛', '唐文宗':'李昂', '唐武宗':'李炎',
         '唐宣宗':'李忱', '唐懿宗':'李漼', '唐僖宗':'李儇', '唐昭宗':'李晔', '唐哀帝':'李柷'}


def era(year):
    if year > 221:
        return 'warring'
    if year > -220:
        return 'han'
    if year > -589:
        return 'division'
    if year > -907:
        return 'tang'
    return 'five'


def build(bind=False):
    source_path = ROOT / 'scripts/rulers/reviewed.json'
    review = json.loads(source_path.read_text())
    people = json.loads((ROOT / 'dist/people-index.json').read_text())['people']
    books, rows, seen = {}, [], set()
    for record in review['records']:
        assert record['name'] not in seen, 'Duplicate ruler: ' + record['name']
        seen.add(record['name'])
        assert record['category'] in {item[0] for item in CATEGORIES}
        assert record['reason'] and record['evidence']
        sources = []
        for index, ref in enumerate([record['source'], *record.get('additionalSources', [])]):
            volume, year, anchor = ref['volume'], ref['year'], ref['anchor']
            assert isinstance(year, int) and year != 0 and -959 <= year <= 403
            if volume not in books:
                books[volume] = json.loads((ROOT / f'dist/volume{volume}.json').read_text())
            entry = next(y for y in books[volume]['years'] if y['year'] == year)
            paragraph = entry['paragraphs'][anchor]
            digest = hashlib.sha256(json.dumps(paragraph['runs'], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
            if bind:
                ref['sourceHash'] = digest
            assert ref.get('sourceHash') == digest, f'Unbound/changed source: {record["name"]} {volume}:{year}:{anchor}'
            if index == 0:
                assert record['evidence'] in paragraph['plain'], 'Witness missing: ' + record['name']
            sources.append(dict(volume=volume, year=year, anchor=anchor, quote=paragraph['plain'],
                                href=f'reader.html#volume-{volume}-year-{year}-para-{anchor}'))
        personal_name = NAMES.get(record['name'], '')
        person = next((p for p in people if record['name'] in [p['name'], *p['aliases']]
                       or (personal_name and personal_name in [p['name'], *p['aliases']])), None)
        rows.append(dict(id='r-' + hashlib.sha256(record['name'].encode()).hexdigest()[:12],
                         name=record['name'], personalName=personal_name, polity=record['polity'],
                         category=record['category'], reason=record['reason'],
                         year=sources[0]['year'], era=era(sources[0]['year']),
                         timeNote=record.get('timeNote', '年份为所引通鉴条目的记载年，不一律等同实际卒年。'),
                         witness=record['evidence'], sources=sources,
                         personHref='reader.html#person-' + person['id'] if person else None))
    rows.sort(key=lambda r: (-r['year'], r['sources'][0]['volume'], r['sources'][0]['anchor'], r['name']))
    counts = Counter(row['category'] for row in rows)
    nonnatural = sum(counts[key] for key in ['killed', 'suicide', 'poison', 'starved', 'battle', 'accident'])
    output = dict(schemaVersion=1, title='通鉴中的君主之死', range=dict(start=403, end=-959),
                  scope='统计当前逐条绑定原文的君主死亡记录，包含先秦公侯国君和秦以后实际统治政权的帝王；不纳入仅有王爵的普通宗室。非全书君主穷尽名单。',
                  yearPolicy='采用条目记载年定位；追叙、附叙与实际发生年有差异时另作说明。没有公元0年。',
                  causePolicy='以所引原文为依据；只记崩、薨、卒，不归为自然死亡。分类为本站整理，不是古书原有分类。',
                  categories=[dict(id=key, label=label, color=color, definition=definition) for key, label, color, definition in CATEGORIES],
                  eras=[dict(id=key, label=label) for key, label in ERAS], rows=rows,
                  totals=dict(records=len(rows), nonnatural=nonnatural, unknown=counts['unknown'], disputed=counts['disputed'],
                              categories=dict(counts), eras=dict(Counter(row['era'] for row in rows))))
    assert sum(output['totals']['categories'].values()) == len(rows)
    assert sum(output['totals']['eras'].values()) == len(rows)
    if bind:
        source_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'dist/ruler-deaths.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
    print(f'PASS: {len(rows)} distinct rulers, {len(books)} volumes; every source/witness and binding checked; counts reconcile.')
    print(dict(counts))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind-reviewed-sources', action='store_true')
    build(parser.parse_args().bind_reviewed_sources)
