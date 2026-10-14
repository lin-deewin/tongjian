"""Scan famine clues separately; never invalidate the original ten review batches."""
import hashlib
import json
import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
PATTERN = (r'饥|飢|饑|饿|餓|馁|餒|殍|餧|饉|馑|歉|不登|不稔|失稔|'
           r'人相食|民相食|相食|相啖|食人|菜色|食尽|食盡|无食|無食|乏食|'
           r'绝粮|絕糧|粮尽|糧盡|粮竭|糧竭|乏粮|乏糧|谷贵|穀貴|榖贵|榖貴|'
           r'米贵|米貴|籴贵|糴貴|踊贵|踴貴|谷踊|榖踊|赈|賑|振贷|振貸|'
           r'草根|鬻子|易子|卖妻|賣妻|卖子|賣子|就食')

def scan():
    rows = []
    digest = hashlib.sha256()
    for v in range(1, 295):
        raw = (ROOT / f'dist/volume{v}.json').read_bytes()
        digest.update(raw)
        for y in json.loads(raw)['years']:
            for a, p in enumerate(y['paragraphs']):
                text = p.get('plain', '')
                if p.get('structural') or not re.search(PATTERN, text):
                    continue
                rows.append(dict(id=f'v{v}-y{y["year"]}-p{a}', volume=v,
                                 year=y['year'], anchor=a, text=text,
                                 matches=sorted(set(re.findall(PATTERN, text)))))
    return dict(schemaVersion=1, corpusSHA256=digest.hexdigest(), pattern=PATTERN,
                paragraphs=rows)

if __name__ == '__main__':
    result = scan()
    out = ROOT / 'artifacts/famine-supplement'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'scan.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(f'Famine clue paragraphs: {len(result["paragraphs"])}')
