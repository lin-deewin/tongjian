#!/usr/bin/env python3
"""Generate source-bound static reading pages without changing canonical data.

Run after rebuilding volumes, translations or reviewed people. Only catalog-selected
translation overlays are applied, in the same precedence as reader.loadVolume().
"""
import argparse
import hashlib
import html
import json
import posixpath
import re
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path

from people_review import event_key, validate_record
from year_reader import enhance_year_page, READER_ASSETS
from translations.overlay import apply as apply_supplement
from translations.replacement import apply as apply_replacement

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://deewins.top/'
CONFIG = ROOT / 'scripts/seo/site.json'
TOPICS = {
    'power-rules.html': '权力、组织与规则：张释之、戴冑与秦二世',
    'truth.html': '判断真伪：楚怀王与张仪（免费试读）',
    'ruler-deaths.html': '君主之死：结局、案例与原文',
    'themes.html': '孤立：能力、授权与支持',
    'relationships.html': '承诺、恩情与利益冲突',
    'risk.html': '明知风险仍继续：处境、投入与退路',
    'history/xiao-he-guanzhong/': '萧何守关中：兵粮、法令与后方',
    'history/yue-yi-qi-campaign/': '乐毅伐齐：大胜之后为何奔赵？',
}
NS = 'http://www.sitemaps.org/schemas/sitemap/0.9'
CORE_PAGES = ['', 'reader.html', 'research.html', *[p for p in TOPICS if p.endswith('.html')]]


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def esc(value):
    return html.escape(str(value), quote=True)


def year_label(year):
    if not isinstance(year, int) or year == 0:
        raise ValueError('Year must be a nonzero BC-positive key')
    return ('公元前' if year > 0 else '公元') + str(abs(year)) + '年'


def href(page, target):
    path, mark, fragment = target.partition('#')
    if not path:
        return '#' + fragment
    relative = posixpath.relpath(path, posixpath.dirname(page) or '.')
    if path.endswith('/') and not relative.endswith('/'):
        relative += '/'
    return relative + (mark + fragment if mark else '')


def link(page, target, label):
    return f'<a href="{esc(href(page, target))}">{esc(label)}</a>'


def reader_target(volume, year=None, index=None):
    value = f'reader.html#volume-{volume}'
    if year is not None:
        value += f'-year-{year}'
    if index is not None:
        value += f'-para-{index}'
    return value


def volume_target(volume, selected, year=None, index=None):
    if volume not in selected:
        return reader_target(volume, year, index)
    value = f'volume/{volume}/'
    if year is not None:
        value += f'#year-{year}'
    if index is not None:
        value += f'-para-{index}'
    return value


class Sources:
    def __init__(self, data):
        self.data = data
        self.catalog = read(data / 'catalog.json')
        self.meta = {m['volume']: m for m in self.catalog['volumes']}
        self.inputs = {}
        self.people_index = None
        self.static_people = set()

    def source(self, relative):
        path = self.data / relative
        # Catalog paths are local inputs, never URLs or paths outside dist.
        if not path.resolve().is_relative_to(self.data.resolve()):
            raise ValueError(f'Invalid data path: {relative}')
        raw = path.read_bytes()
        self.inputs[relative] = sha(raw)
        return json.loads(raw), raw

    @lru_cache(maxsize=None)
    def canonical(self, volume):
        return self.source(f'volume{volume}.json')[0]

    @lru_cache(maxsize=None)
    def effective(self, volume):
        book = self.canonical(volume)
        meta = self.meta[volume]
        key = 'translationReplacement' if meta.get('translationReplacement') else 'translationSupplement'
        if meta.get(key):
            overlay, _ = self.source(meta[key])
            if overlay['volume'] != volume or overlay['schemaVersion'] != 1:
                raise ValueError('Translation overlay schema mismatch')
            digest = self.inputs[f'volume{volume}.json']
            if overlay['baseSHA256'] != digest:
                raise ValueError(f'Stale translation overlay: volume {volume}')
            if key == 'translationReplacement':
                book = apply_replacement(book, overlay, canonical_sha=digest)
            else:
                if any(e.get('provenance') != 'uploaded-recovery' for e in overlay['entries']):
                    raise ValueError('Only uploaded translations may be published')
                book = apply_supplement(book, overlay)
        if meta.get('illustrations'):
            pictures, _ = self.source(meta['illustrations'])
            if pictures['volume'] != volume:
                raise ValueError('Illustration volume mismatch')
            # Copy because canonical() is also used for source/review validation.
            import copy
            book = copy.deepcopy(book)
            years = {y['year']: y for y in book['years']}
            for year in book['years']:
                year['yearIllustrations'] = []
            for entry in pictures['years']:
                years[entry['year']]['yearIllustrations'] = entry['images']
        return book


def runs_html(runs, volume=None):
    value = ''.join(f'<span class="source-note">{esc(r["text"])}</span>'
                    if r['kind'] == 'note' else esc(r['text']) for r in runs)
    # Keep the source artifact in HTML but match the reader's visible-text fix.
    if volume == 9:
        value = value.replace('\ue160', '<span class="source-artifact" hidden>\ue160</span>')
    return value


def modern_html(text, page):
    # Match reader presentation: remove a leading source number on each line.
    result = []
    for line in text.split('\n'):
        line = re.sub(r'^\[\d+\]', '', line)
        pieces, start = [], 0
        for token in re.finditer(r'⟦glyph:([A-Za-z0-9._-]+)⟧', line):
            pieces.append(esc(line[start:token.start()]))
            src = href(page, 'images/baiyang72/glyph/' + token[1])
            pieces.append(f'<img class="translation-glyph" src="{esc(src)}" alt="原书字形" loading="lazy">')
            start = token.end()
        pieces.append(esc(line[start:]))
        result.append(''.join(pieces))
    return '<br><br>'.join(result)


def illustration(pic, page):
    src = pic['src']
    parts = src.split('/')
    if parts[:2] != ['images', 'baiyang72'] or any(
        p in ('.', '..') or not re.fullmatch(r'[A-Za-z0-9._-]+', p) for p in parts
    ):
        raise ValueError('Invalid illustration path')
    url = esc(href(page, src))
    caption = esc(pic.get('caption', '译本原书插图'))
    dimensions = (f' width="{pic["width"]}" height="{pic["height"]}"'
                  if isinstance(pic.get('width'), int) and isinstance(pic.get('height'), int) else '')
    return (f'<figure><a href="{url}"><img src="{url}" alt="{caption}"{dimensions} loading="lazy" decoding="async"></a>'
            f'<figcaption>{caption} · 译本原书插图<br>{esc(pic.get("placementNote", ""))}</figcaption></figure>')


def shell(page, title, description, content, controls=False):
    public = page.removesuffix('index.html')
    canonical = BASE + public
    nav = ' '.join(link(page, path, label) for path, label in [
        ('index.html', '主页'), ('reading.html', '卷次与人物'),
        ('reader.html', '逐年阅读'), ('year/', '逐年目录'), ('research.html', '专题研究')])
    def asset(name):
        return href(page, name) + '?v=' + sha((ROOT / 'dist' / name).read_bytes())[:12]
    scripts = f'<script src="{esc(asset("static-reading.js"))}" defer></script>' if controls else ''
    schema_type = 'WebPage' if page.startswith(('volume/', 'year/')) and page not in ('volume/index.html', 'year/index.html') else 'CollectionPage'
    crumbs = [('资治通鉴', BASE), ('阅读目录', BASE + 'reading.html')]
    if page.startswith('volume/') and page != 'volume/index.html':
        crumbs.append(('全书卷次', BASE + 'volume/'))
    elif page.startswith('people/') and page != 'people/index.html':
        crumbs.append(('人物目录', BASE + 'people/'))
    if page != 'reading.html':
        crumbs.append((title, canonical))
    graph = [dict(**{'@type': schema_type, '@id': canonical + '#page'}, url=canonical,
                  name=title, description=description, inLanguage='zh-CN',
                  isPartOf={'@id': BASE + '#website'}),
             {'@type': 'BreadcrumbList', 'itemListElement': [
                 {'@type': 'ListItem', 'position': i, 'name': label, 'item': url}
                 for i, (label, url) in enumerate(crumbs, 1)]}]
    if page.startswith('history/'):
        graph[0]['@type'] = 'WebPage'
        graph[0]['mainEntity'] = {'@type': 'Article', 'headline': title, 'description': description,
                                  'inLanguage': 'zh-CN', 'mainEntityOfPage': canonical, 'isAccessibleForFree': True}
    if re.fullmatch(r'volume/\d+/index.html', page):
        graph[0]['mainEntity'] = {'@type': 'Chapter', 'name': title,
            'position': int(page.split('/')[1]), 'inLanguage': 'zh-CN',
            'isPartOf': {'@type': 'Book', 'name': '资治通鉴', 'author': {'@type': 'Person', 'name': '司马光'}}}
    elif page.startswith('people/') and page != 'people/index.html':
        graph[0]['about'] = {'@type': 'Person', 'name': title.removesuffix('在资治通鉴中的记载：生平线索与原文出处')}
    schema = json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False).replace('<', '\\u003c')
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{esc(title)}</title><meta name="description" content="{esc(description)}">
<link rel="canonical" href="{esc(canonical)}">
<meta property="og:type" content="article"><meta property="og:site_name" content="资治通鉴">
<meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{esc(canonical)}">
<meta property="og:image" content="{BASE}share-card.svg"><meta name="twitter:card" content="summary">
<script type="application/ld+json">{schema}</script>
<link rel="stylesheet" href="{esc(asset('static-reading.css'))}">{scripts}</head>
<body><header><a class="brand" href="{esc(href(page, 'index.html'))}">鉴 · 资治通鉴</a><nav aria-label="主导航">{nav}</nav></header>
<main>{content}</main><footer>{link(page, 'reading.html', '返回卷次与人物目录')} · {link(page, 'reader.html', '进入逐年阅读器')}</footer></body></html>
'''


def toolbar():
    return '''<div class="reading-controls" hidden aria-label="阅读设置">
<label>阅读模式 <select id="staticMode"><option value="compare">原文／白话对照</option><option value="original">只读原文</option><option value="modern">只读白话</option></select></label>
<label><input id="staticNotes" type="checkbox" checked>显示胡注与校勘</label>
<button type="button" id="staticSmaller" aria-label="减小字号">A−</button><button type="button" id="staticLarger" aria-label="增大字号">A＋</button>
</div>'''


def render_year(book, y, page, sources, selected):
    year = y['year']
    out = [f'<section class="year" id="year-{year}" data-year="{year}">',
           f'<h2>{year_label(year)} · {esc(y.get("reignLabel") or y["king"] + "在位第" + str(y["reign"]) + "年")}</h2>',
           f'<p>{link(page, reader_target(book["volume"], year), "在阅读器中读本年 →")} · {link(page, year_target(year), "本年独立阅读页")}</p>']
    if y.get('headingRuns'):
        out.append(f'<p class="source-heading">{runs_html(y["headingRuns"])}</p>')
    for key in ('warning', 'translationWarning', 'noteWarning', 'contextNote'):
        if y.get(key):
            out.append(f'<p class="notice">{esc(y[key])}</p>')
    if year == 403:
        out.append('<p class="notice">本年含晋阳之战等更早事件的追叙与史家评论；编年位置不等于事件发生年份。</p>')
    parts = sources.catalog['yearVolumes'].get(str(year), [book['volume']])
    if len(parts) > 1:
        links = ' · '.join(link(page, volume_target(v, selected, year), f'第{v}卷') for v in parts)
        out.append(f'<p class="notice">本年记事分属相邻卷，按原书顺序分别保留：{links}。</p>')
    if not y['recorded']:
        out.append('<p>胡注本未在本卷单列这一年记事；不能据此认为当年没有历史事件。</p>')
    if y.get('titles'):
        out.append('<details class="event-toc"><summary>本年事件索引（现代整理）</summary><ol>' + ''.join(
            f'<li><a href="#year-{year}-para-{y["anchors"][i]}">{esc(title)}</a></li>'
            for i, title in enumerate(y['titles'])) + '</ol></details>')
    pictures = y.get('yearIllustrations', [])
    out.extend(illustration(pic, page) for pic in pictures if pic.get('afterParagraph') is None)
    groups = [p for p in y['bilingual'] if not p['difference']]
    groups += [{'huIndices': [i], 'missing': True} for i in y['translationMissing']]
    groups.sort(key=lambda p: p['huIndices'][0])
    order = [i for p in groups for i in p['huIndices']]
    if order != list(range(len(y['paragraphs']))):
        raise ValueError(f'Grouping would reorder or omit original: v{book["volume"]} y{year}')
    for pair in groups:
        indices = pair['huIndices']
        originals = ''.join(
            f'<p class="source-original" id="year-{year}-para-{i}" data-index="{i}">{runs_html(y["paragraphs"][i]["runs"], book["volume"])}</p>'
            for i in indices)
        is_commentary = pair.get('kind') == 'commentary' or any(
            re.match(r'^(臣光曰|太史公曰)', y['paragraphs'][i]['plain']) for i in indices)
        kind = '<p class="kind-label">史家评论 · 原文及其白话</p>' if is_commentary else ''
        warning = esc(pair.get('dateWarning', ''))
        if pair.get('sourceYear'):
            warning += '译本记年：' + year_label(pair['sourceYear']) + '。'
        if pair.get('reviewStatus') == 'check-source':
            warning += '两版字句有差异，建议核对原文。'
        if pair.get('missing'):
            text = ('原书年号衔接，非记事正文。' if y['paragraphs'][indices[0]].get('structural') else
                    '本段缺少可靠对应白话，原文完整保留；未使用生成译文。')
            modern = f'<p class="missing">{text}</p>'
        else:
            modern = f'<p class="modern-text">{modern_html(pair["modern"], page)}</p>'
        person_ids = set()
        if sources.people_index:
            for i in indices:
                person_ids.update(sources.people_index['locations'].get(f'{book["volume"]}:{year}:{i}', []))
        person_links = [link(page, f'people/{p["id"]}/', p['name'])
                        for p in (sources.people_index or {}).get('people', [])
                        if p['id'] in person_ids and p['id'] in sources.static_people]
        related = '<p class="paragraph-people">本段人物：' + ' · '.join(person_links) + '</p>' if person_links else ''
        out.append(f'<div class="comparison-row">{kind}<div class="original-cell"><span class="column-label">原文 · 胡三省注本</span>{originals}</div>'
                   f'<div class="modern-cell"><span class="column-label">白话 · 所据译本</span><p class="notice">{warning}</p>{modern}</div>{related}</div>')
        out.extend(illustration(pic, page) for pic in pair.get('illustrations', []))
        out.extend(illustration(pic, page) for pic in pictures if pic.get('afterParagraph') in indices)
    differences = [p for p in y['bilingual'] if p['difference']]
    if differences:
        out.append('<details class="differences"><summary>译本中未与胡注本可靠对应的内容</summary><p>以下另列供核对版本差异，不并入胡注本正文。</p>')
        for pair in differences:
            out.append(f'<p class="column-label">译本所附古文</p><p>{esc(pair.get("sourceOriginal", ""))}</p>'
                       f'<p class="column-label">{esc(pair.get("sourceLabel", "译本白话"))}</p><p class="modern-text">{modern_html(pair["modern"], page)}</p>')
        out.append('</details>')
    if y.get('translationBlocks'):
        out.append('<details class="differences"><summary>译本所载内容待核对（不作白话）</summary>' +
                   ''.join(f'<p>{esc(t)}</p>' for t in y['translationBlocks']) + '</details>')
    if y.get('after'):
        out.append('<div class="source-transition"><p class="column-label">原书衔接</p>' +
                   ''.join(f'<p>{esc(t)}</p>' for t in y['after']) + '</div>')
    out.append('</section>')
    return ''.join(out)


def volume_page(volume, sources, config, people):
    book = sources.effective(volume)
    meta = sources.meta[volume]
    page = f'volume/{volume}/index.html'
    available = sum(len(p['huIndices']) for y in book['years'] for p in y['bilingual'] if not p['difference'])
    total = sum(len(y['paragraphs']) for y in book['years'])
    scope = '原文、白话与胡三省注' if available else '原文与胡三省注（白话缺译）'
    title = f'资治通鉴卷{volume} {meta["title"].split("【")[-1].rstrip("】")}：{scope}'
    date_range = year_label(meta['start']) + '至' + year_label(meta['end'])
    description = f'阅读《资治通鉴》{meta["title"]}，{date_range}。完整保留{total}段原文与胡注，{available}段有译文对应；缺译或待核对内容另作标注，附逐年索引与上下卷。'
    source_titles = re.findall(r'《[^》]+》', book.get('translationSource', ''))
    translation_source = '、'.join(source_titles) or '本站所据白话资料'
    introduction = ('本页按胡注本编排保存全卷内容。白话采用本站所据译本，未可靠对应的内容另列说明；事件标题用于定位，并非原书文字。'
                    if available else '本页按胡注本编排保存全卷原文与注释。本卷暂无可靠对应的白话，逐段保留缺译说明；不将古文当作白话。事件标题用于定位，并非原书文字。')
    out = [f'<p class="eyebrow">{link(page, "reading.html", "卷次与人物目录")} / 卷{volume}</p>',
           f'<h1>资治通鉴 · {esc(meta["title"])}</h1><p class="lead">{date_range} · {scope}</p>',
           f'<p>{introduction}</p>',
           f'<p class="notice">本卷共{total}段原文，{available}段有译文对应，{total - available}段缺译或待核对。</p>',
           f'<p>{link(page, reader_target(volume), "进入本卷逐年年表与阅读工具 →")}</p>', toolbar(),
           '<nav class="year-toc" aria-label="逐年目录">' + ''.join(
               f'<a href="#year-{y["year"]}">{year_label(y["year"])}</a>' for y in book['years']) + '</nav>',
           f'<p class="source-volume-title">{esc(book.get("fullTitle") or book["title"])}</p>',
           '<details class="source-intro"><summary>卷首原文与注释</summary>' +
           ''.join(f'<p>{runs_html(p["runs"])}</p>' for p in book['intro']) + '</details>']
    out.extend(render_year(book, y, page, sources, config['volumes']) for y in book['years'])
    neighbors = [(n, label) for n, label in [(volume - 1, '上一卷'), (volume + 1, '下一卷')] if n in sources.meta]
    out.append('<nav class="neighbors" aria-label="上下卷">' + ' · '.join(
        link(page, volume_target(n, config['volumes']), f'{label}：{sources.meta[n]["title"]}') for n, label in neighbors) + '</nav>')
    related = [p for p in people if any(s['volume'] == volume for e in p['events'] for s in e['sources'])]
    out.append('<aside class="related"><h2>沿人物与专题继续读</h2><ul>' + ''.join(
        f'<li>{link(page, "people/" + p["id"] + "/", p["name"] + "的通鉴记载")}</li>' for p in related) +
        f'<li>{link(page, "research.html", "从历史案例进入专题研究")}</li></ul></aside>')
    out.append('<section class="sources"><h2>版本与范围</h2><p>原文：司马光主编《资治通鉴》，胡三省注本。胡注与校勘以原书括注保留；史家评论按原书标识。</p>'
               f'<p>白话所据资料文件署名为{esc(translation_source)}。沿用来源文件的版本标识，未另作版本鉴定；未以生成译文补齐。</p>'
               '<p>追叙、评论与原书衔接不改列到推测年份。同年跨卷的记事分别保留。阅读器仍提供模式、注释、字号、搜索及返回浏览位置等工具。</p></section>')
    return page, shell(page, title, description, ''.join(out), controls=True)


def year_target(year):
    return f'year/{"bce" if year > 0 else "ce"}-{abs(year)}/'


def year_pages(sources, config):
    # Use source volume order, including all continuations of a calendar year.
    grouped = {}
    for volume in config['volumes']:
        book = sources.effective(volume)
        for year in book['years']:
            grouped.setdefault(year['year'], []).append((book, year))
    years = sorted(grouped, reverse=True)
    pages = []
    for i, year in enumerate(years):
        page = year_target(year) + 'index.html'
        parts = grouped[year]
        count = sum(len(y['paragraphs']) for _, y in parts)
        title = year_label(year) + '资治通鉴：本年记事、原文与白话对照'
        description = (f'阅读《资治通鉴》{year_label(year)}条，按原书顺序保留{count}段原文、胡注与可对应白话。'
                       '跨卷续篇合并展示，缺译、追叙与版本差异保留说明。')
        out = [f'<p>{link(page, "year/", "逐年目录")}</p><h1>{esc(title)}</h1>',
               '<p class="notice">按原书编年位置阅读；追叙和史论不等于本年发生的事件。白话采用所据译本，缺译不以生成译文补齐。</p>', toolbar()]
        for book, y in parts:
            volume = book['volume']
            out.append(f'<h2>{link(page, f"volume/{volume}/#year-{year}", f"卷{volume} · 本年记事")}</h2>')
            markup = render_year(book, y, page, sources, config['volumes'])
            # A cross-volume year can repeat paragraph indices; namespace every anchor.
            markup = markup.replace(f'id="year-{year}', f'id="volume-{volume}-year-{year}')
            markup = markup.replace(f'href="#year-{year}', f'href="#volume-{volume}-year-{year}')
            out.append(markup)
        neighbors = []
        if i:
            neighbors.append(link(page, year_target(years[i - 1]), '← 上一年：' + year_label(years[i - 1])))
        if i + 1 < len(years):
            neighbors.append(link(page, year_target(years[i + 1]), '下一年：' + year_label(years[i + 1]) + ' →'))
        out.append('<nav class="neighbors" aria-label="前后年份">' + ' · '.join(neighbors) + '</nav>')
        annual_markup = shell(page, title, description, ''.join(out), controls=True)
        pages.append((page, enhance_year_page(page, annual_markup, parts[0][0]['volume'], year)))
    page = 'year/index.html'
    content = '<h1>资治通鉴逐年目录</h1><p>公元前403年至公元959年；同年跨卷内容在同一页面按原书顺序保留。</p><ul class="directory-list">'
    content += ''.join(f'<li>{link(page, year_target(y), year_label(y))}</li>' for y in years) + '</ul>'
    pages.append((page, shell(page, '资治通鉴1362年逐年目录：原文、胡注与白话',
                              '逐年阅读公元前403年至公元959年的资治通鉴原文与可对应白话，包含跨卷续篇、缺译说明与前后年导航。', content)))
    return pages


def validate_person(person, sources, reviews):
    books = {s['volume']: sources.canonical(s['volume']) for e in person['events'] for s in e['sources']}
    for event in person['events']:
        record = reviews.get(event_key(person, event))
        if not record or event.get('semanticReview', {}).get('status') != 'verified-against-source':
            raise ValueError(f'Pilot requires reviewed entries: {person["id"]} {event["id"]}')
        validate_record(person, event, books, record)
        for source in event['sources']:
            year = next(y for y in books[source['volume']]['years'] if y['year'] == source['year'])
            ps = [year['paragraphs'][i] for i in source['indices']]
            digest = sha(json.dumps([p['runs'] for p in ps], ensure_ascii=False, sort_keys=True).encode())
            if source['sourceHash'] != digest or source['quote'] != ' '.join(p['plain'] for p in ps):
                raise ValueError(f'Stale person source: {event["id"]}')


def person_page(person, config):
    page = f'people/{person["id"]}/index.html'
    title = person['name'] + '在资治通鉴中的记载：生平线索与原文出处'
    description = person['identity'] + f'整理《资治通鉴》已关联的{len(person["events"])}条记载，提供经历摘要、原文与卷年出处；追叙和记载位置分开说明，不代表生平无遗漏。'
    out = [f'<p class="eyebrow">{link(page, "reading.html#people", "人物目录")}</p><h1>{esc(person["name"])}在《资治通鉴》中的记载</h1>',
           f'<p class="lead">{esc(person["identity"])}</p><p>姓名／别名：{esc("、".join(person["aliases"]))}</p>',
           f'<p class="notice">{esc(person["coverage"])}</p>',
           '<p>以下为本站已关联记载，按有明确年份的经历、年份未详或附叙／评论分组。摘要为本站整理；引文为《通鉴》原文。</p>',
           f'<p>{link(page, "reader.html#person-" + person["id"], "打开阅读器中的人物档案 →")}</p>']
    dated = sorted((e for e in person['events'] if e['year'] is not None), key=lambda e: -e['year'])
    undated = [e for e in person['events'] if e['year'] is None]
    for label, events in [('有明确年份的经历', dated), ('年份未详、附叙与评论', undated)]:
        if not events:
            continue
        out.append(f'<section><h2>{label}</h2>')
        for event in events:
            out.append(f'<article class="person-event" id="{esc(event["id"])}"><p class="eyebrow">{esc(event["timeLabel"])} · {esc(event["kind"])}</p>'
                       f'<h3>{esc(event["title"])}</h3><p>{esc(event["summary"])}</p><p class="notice">{esc(event["dateNote"])}</p>')
            for source in event['sources']:
                v, y, i = source['volume'], source['year'], source['indices'][0]
                out.append(f'<blockquote><p>{esc(source["quote"])}</p><cite>《资治通鉴》卷{v} · 载于{year_label(y)}条</cite></blockquote>'
                           f'<p>{link(page, volume_target(v, config["volumes"], y, i), "阅读这一段的原文与白话")} · '
                           f'{link(page, reader_target(v, y, i), "在阅读器中核对上下文")}</p>')
            out.append('</article>')
        out.append('</section>')
    volumes = sorted({s['volume'] for e in person['events'] for s in e['sources']})
    out.append('<aside class="related"><h2>沿原文继续读</h2><ul>' + ''.join(
        f'<li>{link(page, f"volume/{v}/", f"资治通鉴卷{v}原文与白话说明")}</li>' for v in volumes) + ''.join(
        f'<li>{link(page, topic, TOPICS[topic.split("#")[0]])}</li>' for topic in config['related'].get(person['id'], [])) + '</ul></aside>')
    out.append('<p class="notice">编年条目的位置不一定是事件发生时间。人物经历仍在补充，未以未收录推断某事不存在，也未据未知生年计算年龄。</p>')
    return page, shell(page, title, description, ''.join(out))


def chronicle_groups(sources, config):
    groups = {}
    for v in config['volumes']:
        groups.setdefault(sources.meta[v]['dynasty'], []).append(v)
    return list(groups.items())


def directory(sources, config, people):
    page = 'reading.html'
    groups = chronicle_groups(sources, config)
    out = ['<p class="eyebrow">资治通鉴 / 阅读目录</p><h1>按卷次与人物读《资治通鉴》</h1>',
           '<p class="lead">从全书原文进入，沿人物与出处读下去。</p>',
           f'<p>全书{len(config["volumes"])}卷，覆盖公元前403年至公元959年。原文、胡注、白话对照与缺译说明均可直接阅读。</p>',
           '<nav class="catalog-links" aria-label="阅读目录">' +
           link(page, 'volume/', '全书卷次目录') + link(page, 'people/', '人物记载目录') +
           link(page, 'reader.html', '逐年年表与搜索') + '</nav>',
           '<section id="volumes"><h2>全书十六纪</h2><ul class="directory-list compact-directory">']
    for i, (dynasty, volumes) in enumerate(groups, 1):
        first, last = sources.meta[volumes[0]], sources.meta[volumes[-1]]
        out.append(f'<li>{link(page, f"volume/#chronicle-{i}", dynasty + "纪")}<span>卷{volumes[0]}—{volumes[-1]} · {year_label(first["start"])}—{year_label(last["end"])}</span></li>')
    out.append('</ul></section><section id="people"><h2>沿人物读史</h2>')
    out.append(f'<p>独立页面收录{len(people)}人的已核读记载，附原文与上下文；其余档案可在阅读器中查看。</p><ul class="person-links">')
    featured = [p for p in people if p['id'] in ['wu-qi', 'wei-wen-hou', 'zhao-xiang-zi', 'shang-yang', 'zhang-yi', 'zhao-wu-ling-wang', 'p-73bb90f91552', 'yue-yi']]
    out.extend(f'<li>{link(page, "people/" + p["id"] + "/", p["name"])}</li>' for p in featured)
    out.append('</ul><p>' + link(page, 'people/', '查看人物目录与收录范围 →') + '</p></section><section><h2>从问题进入专题</h2><ul>')
    out.extend(f'<li>{link(page, topic, label)}</li>' for topic, label in TOPICS.items())
    out.append('</ul></section>')
    return page, shell(page, '资治通鉴阅读目录：全书294卷原文白话与人物记载',
                       '从十六纪浏览资治通鉴294卷原文、白话与胡三省注，沿人物已核读记载核对出处，再进入逐年年表、全文搜索与历史专题。', ''.join(out))


def volumes_directory(sources, config):
    page = 'volume/index.html'
    groups = chronicle_groups(sources, config)
    out = ['<p class="eyebrow">' + link(page, 'reading.html', '阅读目录') + '</p><h1>资治通鉴全书294卷目录</h1>',
           '<p class="lead">前403年至公元959年，按原书卷次连续阅读。</p>',
           '<p>各卷完整保存原文与胡注；有可靠对应的白话随段呈现，缺译、追叙和跨卷续篇另作说明。</p>',
           '<nav class="year-toc" aria-label="按纪跳转">' + ''.join(
               f'<a href="#chronicle-{i}">{esc(dynasty)}纪</a>' for i, (dynasty, _) in enumerate(groups, 1)) + '</nav>']
    for i, (dynasty, volumes) in enumerate(groups, 1):
        out.append(f'<section id="chronicle-{i}"><h2>{esc(dynasty)}纪</h2><ol class="directory-list compact-directory" start="{volumes[0]}">')
        for v in volumes:
            m = sources.meta[v]
            out.append(f'<li>{link(page, f"volume/{v}/", m["title"])}<span>{year_label(m["start"])}—{year_label(m["end"])}</span></li>')
        out.append('</ol></section>')
    return page, shell(page, '资治通鉴全书294卷目录：十六纪原文、白话与胡注',
                       '完整列出资治通鉴294卷，按周、秦、汉、魏、晋至五代十六纪浏览，直接阅读各卷原文、胡三省注与可对应白话，跨卷接续阅读。', ''.join(out))


def people_directory(sources, config, people):
    page = 'people/index.html'
    total = len(sources.people_index['people'])
    out = ['<p class="eyebrow">' + link(page, 'reading.html', '阅读目录') + '</p><h1>资治通鉴人物记载目录</h1>',
           f'<p class="lead">{len(people)}人的已核读记载，逐条回到原文。</p>',
           f'<p>本站共整理{total}个人物档案。本目录仅将全部已收录条目均已核读的{len(people)}人列为独立阅读页，仍不代表生平完整；其余档案保留在' +
           link(page, 'reader.html#people', '阅读器人物目录') + '中，待继续核对。</p>',
           '<div class="directory-search" hidden><label for="peopleFilter">查找姓名或别名</label> <input id="peopleFilter" type="search" autocomplete="off" placeholder="如 吴起、张仪"><p id="peopleFilterStatus" role="status"></p></div>',
           '<ul class="directory-list compact-directory" id="staticPeopleList">']
    for person in people:
        aliases = '、'.join(person['aliases'])
        out.append(f'<li data-names="{esc(aliases)}">{link(page, "people/" + person["id"] + "/", person["name"])}<span>{esc(person["identity"])}</span><small>{len(person["events"])}条已关联记载</small></li>')
    out.append('</ul>')
    # The same small progressive script handles directory filtering without hiding initial HTML.
    return page, shell(page, '资治通鉴人物目录：已核读记载、生平线索与原文出处',
                       f'浏览{len(people)}人的资治通鉴已核读记载，按姓名与别名查找人物，核对经历摘要、卷年及原文出处；说明收录范围，不将追叙当作发生年。', ''.join(out), controls=True)


def selection(sources):
    settings = read(CONFIG)
    config = {**settings}
    config['volumes'] = list(sources.meta) if settings['volumes'] == 'all' else settings['volumes']
    sources.people_index = sources.source('people-index.json')[0]
    reviews = {r['key']: r for r in read(ROOT / 'scripts/people/semantic-reviews.json')['reviews']}
    people, excluded = [], []
    for meta in sources.people_index['people']:
        if settings['people'] != 'reviewed' and meta['id'] not in settings['people']:
            continue
        person = sources.source(f'people/{meta["id"]}.json')[0]
        pending = sum(e.get('semanticReview', {}).get('status') != 'verified-against-source' for e in person['events'])
        if pending or not person['events']:
            if settings['people'] != 'reviewed':
                raise ValueError(f'Explicitly selected person has unreviewed entries: {meta["id"]}')
            excluded.append(dict(id=meta['id'], name=meta['name'], pendingEntries=pending,
                                 totalEntries=len(person['events']), reason='待完成已收录条目的上下文复核'))
            continue
        # A purportedly reviewed but stale record must FAIL, never silently disappear.
        validate_person(person, sources, reviews)
        people.append(person)
    config['people'] = [p['id'] for p in people]
    sources.static_people = set(config['people'])
    return config, people, excluded


def build(data):
    sources = Sources(data)
    sources.source('catalog.json')
    config, people, excluded = selection(sources)
    # Validate everything before replacing any generated output.
    pages = dict([directory(sources, config, people), volumes_directory(sources, config), people_directory(sources, config, people)] +
                 [volume_page(v, sources, config, people) for v in config['volumes']] +
                 [person_page(p, config) for p in people] + year_pages(sources, config))
    from history_articles import render_articles, CONFIG as HISTORY_CONFIG
    pages.update(render_articles(sources, shell, link, esc, year_label))
    # Rebuild from authoritative public content; never retain removed/unsafe sitemap entries.
    sitemap = ET.Element(f'{{{NS}}}urlset')
    for url in dict.fromkeys([BASE + p for p in CORE_PAGES] + [BASE + p.removesuffix('index.html') for p in pages]):
        ET.SubElement(ET.SubElement(sitemap, f'{{{NS}}}url'), f'{{{NS}}}loc').text = url
    previous = read(data / 'seo-manifest.json') if (data / 'seo-manifest.json').exists() else {'pages': {}}
    # Remove only former generator-owned pages whose recorded bytes still match.
    for obsolete, digest in previous['pages'].items():
        if obsolete not in pages:
            path = data / obsolete
            if not path.resolve().is_relative_to(data.resolve()) or not re.fullmatch(
                r'(?:volume/\d+|year/(?:bce|ce)-\d+|people/[a-z0-9-]+|history/[a-z0-9-]+)/index\.html', obsolete
            ):
                raise ValueError(f'Not an owned content page: {obsolete}')
            if path.exists():
                if sha(path.read_bytes()) != digest:
                    raise ValueError(f'Refusing to remove edited generated file: {obsolete}')
                path.unlink()
    from seo_metadata import optimize
    optimize(data)
    ET.register_namespace('', NS)
    ET.indent(sitemap, space='  ')
    for page, markup in pages.items():
        path = data / page
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markup, encoding='utf-8')
    ET.ElementTree(sitemap).write(data / 'sitemap.xml', encoding='utf-8', xml_declaration=True)
    manifest = dict(historyArticlesSHA256=sha(HISTORY_CONFIG.read_bytes()), volumes=config['volumes'], people=config['people'],
                    pages={p: sha(t.encode()) for p, t in pages.items()}, inputs=sources.inputs,
                    semanticReviewsSHA256=sha((ROOT / 'scripts/people/semantic-reviews.json').read_bytes()),
                    configurationSHA256=sha(CONFIG.read_bytes()), excludedPeople=excluded,
                    publicPages={p: sha((data / (p or 'index.html')).read_bytes()) for p in CORE_PAGES},
                    assets={p: sha((data / p).read_bytes()) for p in ('static-reading.css', 'static-reading.js', *READER_ASSETS)})
    (data / 'seo-manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Generated {len(pages)} static pages (directory + {len(config["volumes"])} volumes + {len(people)} people); sitemap updated.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / 'dist')
    build(parser.parse_args().data)
