#!/usr/bin/env python3
"""Build auditable full-book translation replacements from the Baiyang 72-volume EPUB."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path

from lxml import etree, html
from PIL import Image
import io

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
DIGITS = '〇一二三四五六七八九'
EXPECTED_SHA = 'a856d8baeb52ddcadf83b8bbd75910a1254566d7b5b1779419a6e7e49d6e133a'
YEAR_RE = re.compile(r'公元(前)?([〇一二三四五六七八九元零]+)年')


def compact_sha(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def get_year(text):
    m = YEAR_RE.search(text)
    if m:
        digits = m.group(2)
        explicit_bce = bool(m.group(1))
    else:
        # After the BCE/CE transition, this EPUB labels annual headings simply
        # "一年、二年…".  In the project calendar those are -1, -2, … .
        m = re.search(r'^([〇一二三四五六七八九元零]+)年', text)
        if not m:
            return None
        digits = m.group(1)
        explicit_bce = False
    if digits in ('元', '〇', '零'):
        n = 1 if digits == '元' else 0
    else:
        n = int(''.join(str(DIGITS.index(c)) if c in DIGITS else '1' for c in digits))
    if n == 0:
        return None
    return n if explicit_bce else -n


def body_text(node):
    """Keep source s-pic glyphs visible as small image tokens in the web reader."""
    out = [node.text or '']
    for child in node:
        if child.tag.lower() == 'img' and 's-pic' in (child.get('class') or '').split():
            src = Path(child.get('src', '')).name
            out.append(f'⟦glyph:{src}⟧')
        else:
            out.append(body_text(child))
        out.append(child.tail or '')
    return ''.join(out)


def clean_space(text):
    return re.sub(r'[ \t\u3000]+', ' ', text).strip()


def norm(text):
    return re.sub(r'[\s\W_]+', '', text)


def ngram_set(text):
    value = norm(text)
    return set(zip(value, value[1:])) if len(value) > 1 else set(value)


def dice_similarity(left, right):
    a, b = ngram_set(left), ngram_set(right)
    return dice_sets(a, b)


def dice_sets(a, b):
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return 2 * len(a & b) / (len(a) + len(b))


def get_spine_files(archive):
    opf_name = next(n for n in archive.namelist() if n.endswith('content.opf'))
    root = etree.fromstring(archive.read(opf_name))
    ns = {'opf': 'http://www.idpf.org/2007/opf'}
    manifest = {item.get('id'): item.get('href') for item in root.xpath('//opf:manifest/opf:item', namespaces=ns)}
    base = str(Path(opf_name).parent)
    result = []
    for itemref in root.xpath('//opf:spine/opf:itemref', namespaces=ns):
        href = manifest.get(itemref.get('idref'))
        if href and href.endswith(('.html', '.htm', '.xhtml')):
            result.append(str(Path(base, href)).replace('\\', '/'))
    return result


def label_author(text):
    label = re.sub(r'[*\s\u3000：:]+', '', text)
    return label


def parse_source(epub):
    years = defaultdict(lambda: {'headers': [], 'rows': [], 'comments': [], 'images': []})
    glyphs = set()
    dropped_comments = 0
    spine = []
    with zipfile.ZipFile(epub) as archive:
        all_files = set(archive.namelist())
        spine = get_spine_files(archive)
        active_year = None
        record = None
        comment = None
        comment_author = ''

        def flush_record():
            nonlocal record
            if record and record['text'].strip():
                record['text'] = record['text'].strip()
                years[active_year]['rows'].append(record)
            record = None

        def flush_comment():
            nonlocal comment, comment_author, dropped_comments
            if comment and '柏杨' in comment['author']:
                dropped_comments += 1
            elif comment and comment['text'].strip():
                comment['text'] = comment['text'].strip()
                years[active_year]['comments'].append(comment)
            comment = None
            comment_author = ''

        for file in spine:
            if file not in all_files:
                continue
            try:
                doc = html.fromstring(archive.read(file).decode('utf-8'))
            except (ValueError, UnicodeDecodeError):
                continue
            body = doc.xpath('//body')
            if not body:
                continue
            for element_no, element in enumerate(body[0]):
                cls = (element.get('class') or '').split()
                text = clean_space(''.join(element.itertext()))
                if element.tag.lower() == 'h4':
                    flush_record()
                    flush_comment()
                    found = get_year(text)
                    active_year = found
                    if found is not None and ((-403 <= found <= -1) or (1 <= found <= 403) or (-960 <= found <= -404)):
                        years[found]['headers'].append(text)
                    continue
                if active_year is None or not (-960 <= active_year <= -1 or 1 <= active_year <= 403):
                    continue
                if element.tag.lower() == 'div' and 'bodyPic' in cls:
                    caption = clean_space(''.join(element.itertext()))
                    for image in element.xpath('.//img[@src]'):
                        name = Path(image.get('src')).name
                        member = str(Path(file).parent / name).replace('\\', '/')
                        if member not in all_files:
                            continue
                        years[active_year]['images'].append({
                            'file': file, 'element': element_no, 'name': name,
                            'member': member, 'caption': caption,
                        })
                    continue
                if element.tag.lower() != 'p':
                    continue
                if 's-pic' in ' '.join(element.xpath('.//img/@class')):
                    glyphs.update(Path(src).name for src in element.xpath('.//img[@class="s-pic"]/@src'))
                if 'content_106' in cls:
                    flush_comment()
                    author = label_author(text)
                    comment_author = author
                    comment = {'text': '', 'author': author, 'file': file, 'element': element_no}
                    continue
                if 'quotation' in cls:
                    if comment is None:
                        comment = {'text': '', 'author': comment_author or '原书评论', 'file': file, 'element': element_no}
                    if '柏杨' not in comment['author']:
                        q = body_text(element).strip()
                        comment['text'] += ('\n' if comment['text'] else '') + q
                    continue
                if 'content' not in cls or not text:
                    continue
                # A narrative paragraph with a bold number begins a numbered entry.
                bold = ''.join(element.xpath('./span[contains(concat(" ",normalize-space(@class)," ")," bold ")][1]//text()')).strip()
                m = re.match(r'^(\d+)\*?', bold)
                if not m:
                    plain = clean_space(''.join(element.itertext()))
                    m = re.match(r'^(\d+)\*?(?=\s|　)', plain)
                if m:
                    flush_record()
                    flush_comment()
                    paragraph_text = body_text(element)
                    # Remove the source's bold item number but retain any following footnote mark.
                    paragraph_text = re.sub(r'^\s*\d+\*?\s*', '', paragraph_text, count=1)
                    record = {'text': paragraph_text.strip(), 'file': file, 'element': element_no, 'number': int(m.group(1))}
                    continue
                # Regular paragraphs after a commentary section resume the previous numbered entry.
                if comment is not None:
                    flush_comment()
                if record:
                    q = body_text(element).strip()
                    if q:
                        record['text'] += ('\n' if record['text'] else '') + q
        flush_record()
        flush_comment()
        # Keep exact bodyPic images and inline source glyphs; exclude unrelated cover/navigation artwork.
        image_members = {img['member'] for y in years.values() for img in y['images']}
        glyph_members = {str(Path('OEBPS') / name).replace('\\', '/') for name in glyphs}
        copied = {}
        for member in sorted(image_members | glyph_members):
            if member not in all_files:
                continue
            copied[member] = archive.read(member)
    return years, copied, dropped_comments, spine


def existing_references(catalog, data_dir):
    """Read current reviewed pairs only as a text-comparison alignment aid."""
    refs = defaultdict(list)
    for volume in range(1, 295):
        base_path = data_dir / f'volume{volume}.json'
        if not base_path.exists():
            continue
        base_bytes = base_path.read_bytes()
        book = json.loads(base_bytes)
        overlay_path = data_dir / 'translation-supplements' / f'volume{volume}.json'
        if overlay_path.exists():
            overlay = json.loads(overlay_path.read_text())
            if hashlib.sha256(base_bytes).hexdigest() == overlay.get('baseSHA256'):
                try:
                    from translations.overlay import apply
                    book = apply(book, overlay)
                except (AssertionError, KeyError, ValueError):
                    pass
        for y in book['years']:
            for pair in y.get('bilingual', []):
                if pair.get('difference') or not pair.get('huIndices') or '柏杨' in pair.get('modern', ''):
                    continue
                refs[y['year']].append({
                    'volume': volume,
                    'huIndices': pair['huIndices'],
                    'text': pair['modern'],
                    'kind': pair.get('kind', 'record'),
                })
    return refs


def align_rows(rows, refs, threshold=0.76):
    """Monotonic fuzzy alignment to existing reviewed translation groups; low matches stay unpaired."""
    if not rows or not refs:
        return {}
    row_sets = [ngram_set(r['text']) for r in rows]
    ref_sets = [ngram_set(r['text']) for r in refs]
    # Cache the few adjacent-reference spans the edition may have merged.
    spans = {}
    for j in range(len(refs)):
        combined = set()
        for k in range(j, min(len(refs), j + 3)):
            combined |= ref_sets[k]
            spans[(j, k + 1)] = combined.copy()
    # Dynamic programming lets either edition split or merge an event across adjacent groups.
    @lru_cache(None)
    def best(i, j):
        if i >= len(rows) or j >= len(refs):
            return 0.0, ()
        score, path = best(i + 1, j)
        s2, p2 = best(i, j + 1)
        if s2 > score:
            score, path = s2, p2
        target_set = row_sets[i]
        if len(target_set) >= 5:
            for k in range(j, min(len(refs), j + 3)):
                combined_set = spans[(j, k + 1)]
                # The maximum possible Dice score is bounded by the set-size ratio.
                if min(len(target_set), len(combined_set)) / max(len(target_set), len(combined_set)) < threshold / (2 - threshold):
                    continue
                candidate = dice_sets(target_set, combined_set)
                if candidate >= threshold:
                    reward = (candidate - threshold + 0.08) * min(len(target_set), 1000)
                    tail, tailpath = best(i + 1, k + 1)
                    if reward + tail > score:
                        score, path = reward + tail, ((i, j, k + 1, candidate),) + tailpath
        return score, path
    return {i: (refs[j:k], ratio) for i, j, k, ratio in best(0, 0)[1]}


def map_comment(comment, paragraphs, occupied=()):
    author = comment['author']
    marker = '臣光曰' if '司马光' in author else '太史公曰' if '司马迁' in author else author.rstrip('曰：:')
    candidates = [i for i, p in enumerate(paragraphs) if marker and marker in p['plain'] and i not in occupied]
    return candidates[:1]


def paragraph_ranges(year_books):
    rows = []
    for volume, y in year_books:
        anchors = y.get('anchors', [])
        titles = y.get('titles', [])
        ps = y.get('paragraphs', [])
        for idx, anchor in enumerate(anchors):
            end = anchors[idx + 1] if idx + 1 < len(anchors) else len(ps)
            rows.append({'volume': volume, 'indices': list(range(anchor, end)), 'title': titles[idx] if idx < len(titles) else ''})
    return rows


def classify_image_year(caption, source_year):
    explicit = get_year(caption)
    if explicit is None:
        m = re.search(r'前([〇一二三四五六七八九]{1,4})年', caption)
        if m:
            explicit = int(''.join(str(DIGITS.index(c)) for c in m.group(1)))
        else:
            m = re.search(r'([〇一二三四五六七八九]{1,4})年', caption)
            if m:
                value = int(''.join(str(DIGITS.index(c)) for c in m.group(1)))
                explicit = -value
    return explicit if explicit and 1 <= abs(explicit) <= 960 else source_year


def year_label(year):
    return f'前{year}年' if year > 0 else f'公元{abs(year)}年'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--epub', type=Path, default=Path('/home/linqp/tmp/zztj2.epub'))
    ap.add_argument('--data', type=Path, default=ROOT / 'dist')
    ap.add_argument('--output', type=Path, default=ROOT / 'dist/translation-replacements')
    ap.add_argument('--assets', type=Path, default=ROOT / 'dist/images/baiyang72')
    ap.add_argument('--dry-run', action='store_true', help='Only produce an alignment and image report in /tmp')
    args = ap.parse_args()
    source_sha = hashlib.sha256(args.epub.read_bytes()).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f'Unexpected EPUB SHA256: {source_sha}')
    catalog = json.loads((args.data / 'catalog.json').read_text())
    volumes = {v['volume']: json.loads((args.data / f"volume{v['volume']}.json").read_text()) for v in catalog['volumes']}
    year_books = defaultdict(list)
    for v, book in volumes.items():
        for y in book['years']:
            year_books[y['year']].append((v, y))
    refs = existing_references(catalog, args.data)
    source_years, copied_assets, dropped_comments, spine = parse_source(args.epub)
    spine_order = {name: index for index, name in enumerate(spine)}
    replacement_by_volume = {v: {} for v in volumes}
    occupied_indices = defaultdict(set)
    stats = Counter()
    year_report = []
    img_counter = 0

    if not args.dry_run:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.assets / 'glyph').mkdir(parents=True, exist_ok=True)
    for member, raw in copied_assets.items():
        glyph = Path(member).name not in {img['name'] for sy in source_years.values() for img in sy['images']}
        if not args.dry_run:
            target = args.assets / ('glyph' if glyph else '') / Path(member).name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        stats['assetFiles'] += 1
        stats['assetBytes'] += len(raw)
        if glyph:
            stats['glyphAssets'] += 1

    for year, source in source_years.items():
        if year not in year_books or year == 960:
            continue
        books_for_year = year_books[year]
        ranges = paragraph_ranges(books_for_year)
        aligned = align_rows(source['rows'], refs.get(year, []))
        for idx, row in enumerate(source['rows']):
            refgroups, ratio = aligned.get(idx, ([], 0.0))
            by_volume = defaultdict(list)
            for ref in refgroups:
                by_volume[ref['volume']].extend(ref['huIndices'])
            # Avoid crossing years or assigning a paragraph twice; every tie stays a visible source difference.
            assigned = set()
            pairs = []
            for v, indices in by_volume.items():
                target_year = next(y for vv, y in books_for_year if vv == v)
                clean = sorted(set(i for i in indices if i not in assigned and 0 <= i < len(target_year['paragraphs'])))
                if clean:
                    assigned.update(clean)
                    pairs.append((v, clean))
                    occupied_indices[(year, v)].update(clean)
            if len(pairs) == 1 and ratio >= 0.76:
                v, indices = pairs[0]
                pairs_json = [dict(huIndices=indices, sourceOriginal='', modern=row['text'], score=ratio,
                                   kind='record', difference=False, alignmentMethod='reviewed-translation-sequence',
                                   provenance='uploaded-epub', sourceLabel='新上传译本白话',
                                   sourceNumber=row['number'],
                                   sourceLocations=[dict(file=row['file'], element=row['element'])])]
                stats['matchedRows'] += 1
                stats['matchedParagraphs'] += len(indices)
            else:
                # Keep every unmatched translation for review rather than fabricating a paragraph association.
                v = books_for_year[0][0]
                pairs_json = [dict(huIndices=[], sourceOriginal='', modern=row['text'], score=0,
                                   kind='record', difference=True, alignmentMethod='unmatched-source-entry',
                                   provenance='uploaded-epub', sourceLabel=f"上传译本第{row['number']}条白话 · 待核对",
                                   sourceNumber=row['number'],
                                   sourceLocations=[dict(file=row['file'], element=row['element'])])]
                stats['unmatchedRows'] += 1
            replacement_by_volume[v][year] = replacement_by_volume[v].get(year, []) + pairs_json

        # Non-Baiyang commentaries are preserved and aligned only to source commentary paragraphs.
        for comment in source['comments']:
            text = comment['text'].strip()
            if not text or '柏杨' in comment['author']:
                continue
            stats['keptCommentaries'] += 1
            placed = False
            for v, y in books_for_year:
                indices = map_comment(comment, y['paragraphs'], occupied_indices[(year, v)])
                if indices:
                    occupied_indices[(year, v)].update(indices)
                    replacement_by_volume[v][year] = replacement_by_volume[v].get(year, []) + [dict(
                        huIndices=indices, sourceOriginal='', modern=text, score=0.9, kind='commentary', difference=False,
                        alignmentMethod='commentary-source-header', provenance='uploaded-epub',
                        sourceLabel=f"{comment['author']} 白话评语",
                        sourceLocations=[dict(file=comment['file'], element=comment['element'])])]
                    stats['matchedComments'] += 1
                    placed = True
                    break
            if not placed:
                v = books_for_year[0][0]
                replacement_by_volume[v][year] = replacement_by_volume[v].get(year, []) + [dict(
                    huIndices=[], sourceOriginal='', modern=text, score=0, kind='commentary', difference=True,
                    alignmentMethod='unmatched-commentary', provenance='uploaded-epub',
                    sourceLabel=f"{comment['author']} 白话评语 · 待核对",
                    sourceLocations=[dict(file=comment['file'], element=comment['element'])])]
                stats['unmatchedComments'] += 1

        # Map each bodyPic by its own printed year; fall back to section year if undated.
        for img in source['images']:
            target_year = classify_image_year(img['caption'], year)
            if target_year == 960 or target_year not in year_books:
                target_year = year
            if target_year == 960 or target_year not in year_books:
                stats['excludedImages'] += 1
                continue
            vol = year_books[target_year][0][0]
            try:
                width, height = Image.open(io.BytesIO(copied_assets[img['member']])).size
            except Exception:
                width = height = None
            item = dict(src=f"images/baiyang72/{img['name']}", caption=img['caption'] or '原书插图',
                        width=width, height=height, sourceFile=img['file'], sourceElement=img['element'],
                        sourceYear=year, year=target_year,
                        placementNote='' if target_year == year else f"按原书图题年份放置；EPUB年段位置为{year_label(year)}。")
            replacement_by_volume[vol].setdefault(target_year, [])
            replacement_by_volume[vol][target_year].append({'__illustration': item})
            stats['illustrations'] += 1
            if not img['caption']:
                stats['uncaptionedImages'] += 1

    for volume, book in volumes.items():
        entries = []
        for y in book['years']:
            year = y['year']
            content = replacement_by_volume[volume].get(year, [])
            illustrations = [x['__illustration'] for x in content if '__illustration' in x]
            pairs = [x for x in content if '__illustration' not in x]
            # Comments and numbered events share their exact EPUB reading order.
            pairs.sort(key=lambda pair: (
                spine_order.get(pair.get('sourceLocations', [{}])[0].get('file', ''), 10**9),
                pair.get('sourceLocations', [{}])[0].get('element', 10**9),
            ))
            covered = set(i for p in pairs if not p['difference'] for i in p['huIndices'])
            missing = [i for i in range(len(y['paragraphs'])) if i not in covered]
            warning = ''
            if any(p['difference'] for p in pairs):
                warning = '本年有上传译本内容尚未与胡注本段落可靠匹配，已保留在版本差异区；原文不删。'
            entry = dict(year=year, sourceParagraphSHA256=compact_sha(y['paragraphs']), bilingual=pairs,
                         translationMissing=missing, translationHeaders=source_years.get(year, {}).get('headers', []),
                         translationWarning=warning, yearIllustrations=illustrations)
            entries.append(entry)
            stats['sourceParagraphs'] += len(y['paragraphs'])
            stats['remainingMissing'] += len(missing)
        raw_base = (args.data / f'volume{volume}.json').read_bytes()
        overlay = dict(schemaVersion=1, volume=volume, baseSHA256=hashlib.sha256(raw_base).hexdigest(),
                       sourceSHA256=source_sha, translationSource='用户提供的zztj2.epub（文件元数据署名柏杨；按用户要求过滤其标注评论）',
                       years=entries)
        overlay['stats'] = dict(missing=sum(len(y['translationMissing']) for y in entries),
                                matched=sum(sum(len(p['huIndices']) for p in y['bilingual'] if not p['difference']) for y in entries),
                                differenceGroups=sum(sum(p['difference'] for p in y['bilingual']) for y in entries),
                                illustrations=sum(len(y['yearIllustrations']) for y in entries))
        if not args.dry_run:
            (args.output / f'volume{volume}.json').write_text(json.dumps(overlay, ensure_ascii=False, separators=(',', ':')))
        for y in entries:
            year_report.append(dict(volume=volume, year=y['year'], sourceGroups=len(y['bilingual']),
                                    matched=sum(not p['difference'] for p in y['bilingual']),
                                    missing=len(y['translationMissing']), illustrations=len(y['yearIllustrations'])))

    if not args.dry_run:
        # Search text and visible volume metadata must describe the replacement,
        # while canonical paragraphs, titles and anchors remain untouched.
        current_catalog = json.loads((args.data / 'catalog.json').read_text())
        for meta in current_catalog['volumes']:
            volume = meta['volume']
            path = args.output / f'volume{volume}.json'
            overlay = json.loads(path.read_text())
            meta['translationReplacement'] = f'translation-replacements/volume{volume}.json'
            meta['translationMissing'] = overlay['stats']['missing']
            for obsolete in ('translationSupplement', 'translationRecovered', 'translationGenerated'):
                meta.pop(obsolete, None)
            base = volumes[volume]
            entry_by_year = {x['year']: x for x in overlay['years']}
            search_path = args.data / f'search{volume}.json'
            search_rows = json.loads(search_path.read_text())
            for search_row, y in zip(search_rows, base['years']):
                entry = entry_by_year[y['year']]
                search_row['pairCount'] = sum(not p['difference'] for p in entry['bilingual'])
                search_row['text'] = ' '.join(
                    [''.join(run['text'] for run in paragraph['runs']) for paragraph in y['paragraphs']]
                    + [p['modern'] for p in entry['bilingual']]
                )
            search_path.write_text(json.dumps(search_rows, ensure_ascii=False, separators=(',', ':')))
        (args.data / 'catalog.json').write_text(json.dumps(current_catalog, ensure_ascii=False, separators=(',', ':')))
        coverage_path = args.data / 'coverage.json'
        coverage = json.loads(coverage_path.read_text())
        coverage['matchedOriginal'] = sum(
            sum(len(p['huIndices']) for p in y['bilingual'] if not p['difference'])
            for volume in volumes
            for y in json.loads((args.output / f'volume{volume}.json').read_text())['years']
        )
        coverage['uploadedMatchedOriginal'] = coverage['matchedOriginal']
        coverage['uploadedRecoveredOriginal'] = 0
        coverage['aiSupplementedOriginal'] = 0
        coverage['unmatchedOriginal'] = coverage['sourceBody'] - coverage['matchedOriginal']
        coverage['ancientOnlyVolumes'] = []
        coverage['mixedTranslationVolumes'] = []
        coverage['replacementTranslationGroups'] = sum(
            len(y['bilingual'])
            for volume in volumes
            for y in json.loads((args.output / f'volume{volume}.json').read_text())['years']
        )
        coverage['removedBaiyangCommentaries'] = dropped_comments
        coverage['replacementIllustrations'] = stats['illustrations']
        coverage['translationReplacementSHA256'] = source_sha
        coverage['coverageNote'] = '未可靠匹配的白话仍完整保留在对应年份的译本待核区；“未匹配”不表示没有白话文本。'
        coverage['volumesWithMissing'] = [
            dict(volume=meta['volume'], title=meta['title'], missing=meta['translationMissing'],
                 body=meta['bodyParagraphs'], reason='新译本白话保留；部分原文段落尚未完成可靠对齐。')
            for meta in current_catalog['volumes'] if meta['translationMissing']
        ]
        coverage_path.write_text(json.dumps(coverage, ensure_ascii=False, separators=(',', ':')))

    report_path = Path('/tmp/baiyang72-import-report.json') if args.dry_run else ROOT / 'artifacts/translation-baiyang72/import-report.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = dict(sourceSHA256=source_sha, spineFiles=len(spine), epubYearHeadings=sum(len(x['headers']) for x in source_years.values()),
                  yearsExtracted=len(source_years), droppedBaiyangCommentaries=dropped_comments,
                  totalNumberedRecords=sum(len(y['rows']) for y in source_years.values()),
                  totalKeptCommentaries=sum(len(y['comments']) for y in source_years.values()),
                  statistics=dict(stats), years=year_report)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({k: v for k, v in report.items() if k != 'years'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
