"""Repair the verified chapter290.htm separator/split at volume 294, year 959.

No original text is changed. Both translation fragments are read verbatim from
uploaded EPUB paragraphs; the following source/translation remain a difference.
"""
import json
import zipfile
from pathlib import Path
from lxml import html

ROOT = Path(__file__).resolve().parents[1]


def repair():
    with zipfile.ZipFile(ROOT / 'sources/baiyang.epub') as epub:
        paragraphs = [p.text_content() for p in html.fromstring(epub.read('OPS/chapter290.htm')).xpath('//p')]
    assert paragraphs[170].startswith('陛下武功既著，垂意礼乐')
    assert paragraphs[171] == '>'
    assert paragraphs[172].startswith('“陛下武功既已卓著，开始注意振兴礼乐')
    assert paragraphs[173].startswith('、夷则、夹钟、无射、中吕')
    assert paragraphs[174] == '诏从之。百官皆以为然，乃行之。'
    assert paragraphs[175] == '>'
    assert paragraphs[176] == '世宗下诏采用王朴所奏旋宫之法。百官都认为是这样，于是实行。'
    path = ROOT / 'dist/volume294.json'
    book = json.loads(path.read_text())
    year = next(y for y in book['years'] if y['year'] == -959)
    modern = '\n'.join(paragraphs[172:174])
    existing = [p for p in year['bilingual'] if 4 in p['huIndices']]
    if existing:
        assert len(existing) == 1 and existing[0]['modern'] == modern
        print('Volume 294 split translation already repaired.')
        return
    assert 4 in year['translationMissing']
    difference = next(p for p in year['bilingual'] if p['difference'] and p['sourceOriginal'] == paragraphs[172])
    assert paragraphs[173] in difference['modern'] and paragraphs[176] in difference['modern']
    pair = dict(huIndices=[4], sourceOriginal=paragraphs[170], modern=modern,
                score=0.944, kind='record', difference=False,
                translationFiles=['OPS/chapter290.htm'], reviewStatus='source-verified',
                sourceRepair=dict(reason='Skip separator-only paragraph and join split uploaded white text',
                                  originalParagraph=170, modernParagraphs=[172, 173]))
    year['bilingual'].insert(year['bilingual'].index(difference), pair)
    # Keep the following item available for version checking rather than mixing
    # its original text into this paragraph's white text.
    difference.update(sourceOriginal=paragraphs[174], modern=paragraphs[176])
    year['translationMissing'].remove(4)
    path.write_text(json.dumps(book, ensure_ascii=False, separators=(',', ':')))
    print('Repaired volume 294 / year 959 / paragraph 4 from exact uploaded paragraphs 172–173.')


if __name__ == '__main__':
    repair()
