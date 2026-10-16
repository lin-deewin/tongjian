"""Regression checks for identity, dates, categories and citations found in the audit."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
profiles = json.loads((ROOT / 'scripts/people/reviewed.json').read_text())['people']
people = {p['name']: p for p in profiles}


def event(name, title):
    return next(e for e in people[name]['events'] if e['title'] == title)


def source_years(name):
    return {s['year'] for e in people[name]['events'] for s in e['sources']}


assert all(s['volume'] < 100 for e in people['张衡']['events'] for s in e['sources'])
assert source_years('张衡（隋）') == {-610, -612}
assert source_years('刘弘') == {-304, -305}
assert source_years('王衍（西晋）') == {-272, -297, -300, -301, -306, -307, -309}
assert all(y <= -580 for y in source_years('魏征'))
assert all(e['year'] is None or e['year'] >= -226 for e in people['曹丕']['events'])
assert all(e['year'] is None or e['year'] >= -482 for e in people['萧道成']['events'])
assert not any('西魏文帝' in e['title'] for e in people['曹丕']['events'])
assert not any('后汉高祖' in e['title'] or '南汉高祖' in e['title'] for e in people['刘邦']['events'])
assert '刘知远' in people and '刘龑' in people
assert event('汉文帝', '刘恒在代邸即位，是为汉文帝')['year'] == 180
assert event('汉景帝', '刘启即位，是为景帝')['year'] == 157
assert event('萧何', '萧何守关中，转粮发兵定法令')['kind'] == '主要经历'
assert event('萧何', '萧何守关中，转粮发兵定法令')['year'] == 205
assert event('曹操', '曹操病逝洛阳，司马光评其知人善任而法令严峻')['category'] == '去世'
assert event('曹操', '曹操诛杀马腾及其三族')['category'] != '去世'
assert event('韩信', '吕后萧何诱韩信入宫，诛灭三族')['category'] == '去世'
assert event('萧何', '吕后萧何诱韩信入宫，诛灭三族')['category'] != '去世'
assert event('司马昭', '王仪直言司马昭应承担战败之责，遭杀害，子王裒终身不仕')['year'] is None
assert event('班彪', '班彪称元帝宽仁好儒，却优柔寡断致宣帝之业衰退')['kind'] == '史家评论'
assert event('班彪', '班彪称元帝宽仁好儒，却优柔寡断致宣帝之业衰退')['year'] is None
for name, title, index in [
    ('王褒（梁北周）', '萧绎任王褒为吏部尚书', 0),
    ('王褒（梁北周）', '王褒等梁朝官员被送至长安，宇文泰厚礼接待于谨', 50),
    ('刘康祖', '魏攻悬瓠项城并杀刘康祖', 47),
]:
    assert event(name, title)['sources'][0]['indices'] == [index]

# Every published event must reproduce its cited original, including note runs.
books = {}
index = json.loads((ROOT / 'dist/people-index.json').read_text())
assert {p['id'] for p in profiles} == {p['id'] for p in index['people']}
total = 0
for person in profiles:
    published = json.loads((ROOT / 'dist/people' / (person['id'] + '.json')).read_text())
    assert len(published['events']) == len(person['events'])
    for original, generated in zip(person['events'], published['events']):
        total += 1
        for field in ['title', 'category', 'kind', 'year', 'dateNote']:
            assert original[field] == generated[field], (person['name'], field)
        for source in generated['sources']:
            v = source['volume']
            if v not in books:
                books[v] = json.loads((ROOT / f'dist/volume{v}.json').read_text())
            year = next(y for y in books[v]['years'] if y['year'] == source['year'])
            paragraphs = [year['paragraphs'][i] for i in source['indices']]
            raw = json.dumps([p['runs'] for p in paragraphs], ensure_ascii=False, sort_keys=True)
            assert hashlib.sha256(raw.encode()).hexdigest() == source['sourceHash']
            assert source['quote'] == ' '.join(p['plain'] for p in paragraphs)
            for i in source['indices']:
                assert person['id'] in index['locations'][f'{v}:{source["year"]}:{i}']
assert total == json.loads((ROOT / 'dist/people-life-report.json').read_text())['totalEvents']
print(f'PASS: {len(profiles)} profiles, {total} source-linked entries; identity/date/category/citation regressions')
