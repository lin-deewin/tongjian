"""Publish reviewed people without altering volume data; refuse stale source bindings."""
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def digest(paragraphs):
    return hashlib.sha256(json.dumps([p['runs'] for p in paragraphs], ensure_ascii=False, sort_keys=True).encode()).hexdigest()

def build(bind=False):
    path = ROOT / 'scripts/people/reviewed.json'
    data = json.loads(path.read_text())
    life_years = json.loads((ROOT / 'scripts/people/life-years.json').read_text())['people']
    volumes = {s['volume'] for p in data['people'] for e in p['events'] for s in e['sources']}
    books = {v: json.loads((ROOT / f'dist/volume{v}.json').read_text()) for v in volumes}
    locations, catalog, outputs = {}, [], []
    ids = set()
    for person in data['people']:
        life = life_years.get(person['id'])
        if not life or life['name'] != person['name']:
            raise ValueError(f"Missing/mismatched life-year review: {person['id']}")
        assert life['status'] in ('confirmed', 'unknown', 'disputed', 'approximate', 'unconfirmed')
        if life['status'] == 'confirmed':
            assert type(life['birthYear']) is int and life['birthYear'] != 0
            assert life['source'] and life['source'].startswith('https://')
            assert life['deathYear'] is None or (type(life['deathYear']) is int and life['deathYear'] != 0)
        else:
            assert life['birthYear'] is None and life['deathYear'] is None
        person.update(birthYear=life['birthYear'], deathYear=life['deathYear'], birthSource=life['source'],
                      birthStatus=life['status'], birthNote=life['note'])
        assert person['id'] not in ids
        ids.add(person['id'])
        for number, event in enumerate(person['events']):
            event['id'] = f"{person['id']}-{number + 1}"
            assert event['year'] is None or (isinstance(event['year'], int) and event['year'] != 0)
            assert event['category'] in ('任职', '战争', '政争', '改革', '言论', '去世')
            assert event['sources']
            assert event['kind'] in ('主要经历', '相关提及', '史家评论')
            for source in event['sources']:
                y = next(y for y in books[source['volume']]['years'] if y['year'] == source['year'])
                assert source['indices'] and len(set(source['indices'])) == len(source['indices'])
                assert all(isinstance(i, int) and 0 <= i < len(y['paragraphs']) for i in source['indices'])
                paragraphs = [y['paragraphs'][i] for i in source['indices']]
                current = digest(paragraphs)
                if bind:
                    source['sourceHash'] = current
                if source.get('sourceHash') != current:
                    raise ValueError(f"Stale/unbound source: {event['id']}; review source before binding")
                source['quote'] = ' '.join(p['plain'] for p in paragraphs)
                for i in source['indices']:
                    key = f"{source['volume']}:{source['year']}:{i}"
                    locations.setdefault(key, [])
                    if person['id'] not in locations[key]:
                        locations[key].append(person['id'])
        output = ROOT / 'dist/people' / f"{person['id']}.json"
        outputs.append((output, json.dumps(person, ensure_ascii=False, indent=2) + '\n'))
        meta = {k: person[k] for k in ('id', 'name', 'aliases', 'identity', 'coverage')}
        meta.update(birthYear=person['birthYear'], birthStatus=person['birthStatus'])
        meta['mainVolumes'] = sorted({s['volume'] for e in person['events'] if e['kind'] == '主要经历' for s in e['sources']})
        catalog.append(meta)
    if set(life_years) != ids:
        raise ValueError('Life-year reviews must cover exactly the current people directory')
    def year_axis(year):
        return 1 - year if year > 0 else -year
    age_counts = Counter()
    for person in data['people']:
        for event in person['events']:
            if person['birthStatus'] != 'confirmed':
                age_counts['withoutConfirmedBirth'] += 1
            elif event['year'] is None:
                age_counts['withoutEventYear'] += 1
            elif year_axis(event['year']) < year_axis(person['birthYear']):
                age_counts['beforeBirth'] += 1
            elif person['deathYear'] is not None and year_axis(event['year']) > year_axis(person['deathYear']):
                age_counts['afterDeath'] += 1
            else:
                age_counts['withAge'] += 1
    life_report = dict(reviewedPeople=len(ids), birthStatuses=dict(Counter(p['birthStatus'] for p in data['people'])),
                       eventAgeCoverage=dict(age_counts), totalEvents=sum(age_counts.values()))
    # Publish only after every source has passed verification.
    for output, content in outputs:
        output.parent.mkdir(exist_ok=True)
        output.write_text(content)
    (ROOT / 'dist/people-life-report.json').write_text(json.dumps(life_report, ensure_ascii=False, indent=2) + '\n')
    if bind:
        # Quote is generated data, hashes are the persistent source contract.
        for person in data['people']:
            for event in person['events']:
                for source in event['sources']:
                    source.pop('quote', None)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    (ROOT / 'dist/people-index.json').write_text(json.dumps(dict(schemaVersion=1, people=catalog, locations=locations), ensure_ascii=False, indent=2) + '\n')
    print(f"PASS: {len(catalog)} people, {sum(len(p['events']) for p in data['people'])} reviewed entries, {len(locations)} source locations")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bind-reviewed-sources', action='store_true', help='Only after reading changed passages; update source hashes')
    build(parser.parse_args().bind_reviewed_sources)
