"""Read-only, full-book people audit. Flags are review candidates, not verdicts.

Checks every profile/event/source and searches every paragraph for missing name
links. Matching text never certifies identity, date, significance or completeness.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
from people_review import validate_record

ROOT = Path(__file__).resolve().parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def axis(year):
    return 1 - year if year > 0 else -year


def event_key(person, event):
    sources = [(s['volume'], s['year'], s['indices']) for s in event['sources']]
    return person['id'] + ':' + digest([event['title'], sources])[:20]


def audit(output):
    profiles = json.loads((ROOT / 'scripts/people/reviewed.json').read_text())['people']
    lives = json.loads((ROOT / 'scripts/people/life-years.json').read_text())['people']
    paragraphs, title_at, books = {}, {}, {}
    review_path = ROOT / 'scripts/people/semantic-reviews.json'
    reviews = json.loads(review_path.read_text())['reviews'] if review_path.exists() else []
    review_by_key = {r['key']: r for r in reviews}
    for volume in range(1, 295):
        book = json.loads((ROOT / f'dist/volume{volume}.json').read_text())
        books[volume] = book
        for year in book['years']:
            for index, paragraph in enumerate(year['paragraphs']):
                paragraphs[(volume, year['year'], index)] = paragraph
            for title, anchor in zip(year['titles'], year['anchors']):
                title_at[(volume, year['year'], anchor)] = title
    owners = defaultdict(set)
    for person in profiles:
        for alias in set([person['name'], *person['aliases']]):
            if len(alias) >= 2:
                owners[alias].add(person['id'])
    names = re.compile('|'.join(re.escape(n) for n in sorted(owners, key=lambda n: (-len(n), n))))
    linked, events, people, errors = defaultdict(set), [], [], []
    critical_codes = {'invalid-source', 'source-hash', 'invalid-date', 'duplicate-source', 'published-mismatch', 'stale-semantic-review'}
    for person in profiles:
        life = lives.get(person['id'], {})
        rows, seen = [], {}
        published_path = ROOT / 'dist/people' / (person['id'] + '.json')
        published = json.loads(published_path.read_text()) if published_path.exists() else {}
        for index, event in enumerate(person['events']):
            flags, quotes, locations = [], [], []
            key = event_key(person, event)
            if event['year'] is not None and (type(event['year']) is not int or event['year'] == 0):
                flags.append('invalid-date')
            for source in event['sources']:
                locs = [(source['volume'], source['year'], i) for i in source['indices']]
                if not locs or len(set(locs)) != len(locs) or any(loc not in paragraphs for loc in locs):
                    flags.append('invalid-source')
                    continue
                ps = [paragraphs[loc] for loc in locs]
                if digest([p['runs'] for p in ps]) != source.get('sourceHash'):
                    flags.append('source-hash')
                quotes.append(' '.join(p['plain'] for p in ps))
                locations.extend(locs)
                for loc in locs:
                    linked[loc].add(person['id'])
            # One paragraph may substantiate several distinct events.
            signature = (event['title'], tuple(locations))
            if signature in seen:
                flags.append('duplicate-source')
            seen[signature] = key
            text = '\n'.join(quotes)
            if not any(a in text for a in person['aliases']):
                flags.append('identity-not-explicit')
            if life.get('status') == 'confirmed' and event['year'] is not None:
                if axis(event['year']) < axis(life['birthYear']):
                    flags.append('before-birth')
                if life.get('deathYear') is not None and axis(event['year']) > axis(life['deathYear']):
                    flags.append('after-death')
            if event['kind'] == '主要经历':
                if re.match(r'^[\W\ue000-\uf8ff]*(初[，,]|先是|昔|尝|臣光曰|太史公曰|班[彪固].?曰|陈寿评曰|柳芳曰)', text):
                    flags.append('retrospective-or-commentary')
                if event['title'].startswith(('追叙', '追述', '史论')) and event['year'] is not None:
                    flags.append('retrospective-date')
                if event['category'] == '去世':
                    flags.append('death-subject-review')
            if event['kind'] == '相关提及' and event['year'] is None:
                flags.append('mention-date-role-review')
            # No source hash can prove that a modern title names the right emperor.
            if re.search('帝|太后|太祖|高祖|世宗|高宗|武后', event['title']):
                flags.append('ruler-identity-review')
            if index >= len(published.get('events', [])) or any(published['events'][index].get(k) != event.get(k) for k in ('title', 'kind', 'category', 'year', 'dateNote')):
                flags.append('published-mismatch')
            review = review_by_key.get(key)
            reviewed = False
            if review:
                try:
                    validate_record(person, event, books, review)
                    reviewed = True
                except ValueError:
                    flags.append('stale-semantic-review')
            row = dict(key=key, personId=person['id'], person=person['name'], index=index,
                       title=event['title'], year=event['year'], kind=event['kind'],
                       category=event['category'], sources=event['sources'],
                       flags=sorted(set(flags)), excerpt=text[:700],
                       status='verified-against-source' if reviewed else 'needs-context-review' if flags else 'automated-checks-only',
                       review=review if reviewed else None)
            events.append(row)
            rows.append(row)
            errors.extend(dict(key=key, code=f) for f in set(flags) & critical_codes)
        people.append(dict(id=person['id'], name=person['name'], events=len(rows),
                           flaggedEvents=sum(bool(r['flags']) for r in rows),
                           sourceReviewedEntries=sum(r['status'] == 'verified-against-source' for r in rows),
                           semanticReview='not-certified-by-automated-audit'))
    missing = []
    for loc, paragraph in paragraphs.items():
        for alias in set(m.group() for m in names.finditer(paragraph['plain'])):
            for person_id in sorted(owners[alias] - linked[loc]):
                missing.append(dict(personId=person_id, alias=alias, volume=loc[0], year=loc[1],
                                    index=loc[2], title=title_at.get(loc),
                                    status='unreviewed-name-match-not-confirmed-event',
                                    excerpt=paragraph['plain'][:300]))
    counts = Counter(f for e in events for f in e['flags'])
    summary = dict(profiles=len(profiles), events=len(events), volumes=294,
                   paragraphs=len(paragraphs), structuralErrors=len(errors),
                   flaggedEvents=sum(bool(e['flags']) for e in events),
                   sourceReviewedEntries=sum(e['status'] == 'verified-against-source' for e in events),
                   unreviewedFlaggedEvents=sum(bool(e['flags']) and e['status'] != 'verified-against-source' for e in events),
                   missingNameCandidates=len(missing), flagCounts=dict(counts),
                   historicalAccuracyCertified=False, exhaustiveSemanticReviewCompleted=False)
    output.mkdir(parents=True, exist_ok=True)
    for name, value in [('summary', summary), ('profiles', people), ('events', events),
                        ('missing-name-candidates', missing), ('structural-errors', errors)]:
        (output / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    (output / 'README.md').write_text(
        '# 全人物核查\n\n'
        f'机器检查覆盖 {len(profiles)} 人、{len(events)} 条档案记录及294卷的全部 {len(paragraphs)} 段。\n\n'
        f'另有 {summary["sourceReviewedEntries"]} 条具有显式原文复核记录；记录绑定条目字段、人物身份及相邻原文，发生变化即失效。该数字不表示传记已无遗漏。\n\n'
        '此报告不能证明历史判断正确，也不能证明没有漏收。姓名命中可能是同名、姓名前缀、引语、胡注或追叙。'
        '未命中姓名也不能证明无关：原文会使用字、官职、爵号、简称和代词。\n\n'
        f'结构错误：{len(errors)}；需结合上下文核查的记录：{summary["flaggedEvents"]}；'
        f'尚未关联的姓名匹配候选：{len(missing)}。这些数字不是已确认错误数量。\n\n'
        'profiles.json 逐人列出覆盖；events.json 逐条列出来源与疑点；'
        'missing-name-candidates.json 保留可能漏收的原文位置；'
        '已确认修改另记于 scripts/people/research/full-audit-decisions.json。\n'
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return not errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/people-audit')
    args = parser.parse_args()
    raise SystemExit(0 if audit(args.output) else 1)
