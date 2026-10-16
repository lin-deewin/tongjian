"""Render reviewed historical essays; refuse changed quotations/source bindings."""
import json
import re
from pathlib import Path

from build_people import digest

CONFIG = Path(__file__).resolve().parent / 'seo/history-articles.json'


def render_articles(sources, shell, link, esc, year_label):
    data = json.loads(CONFIG.read_text())
    pages = []
    slugs = set()
    for article in data['articles']:
        slug = article['slug']
        if not re.fullmatch(r'[a-z0-9-]+', slug) or slug in slugs:
            raise ValueError('Invalid/duplicate historical essay slug')
        slugs.add(slug)
        page = f'history/{slug}/index.html'
        sections = article['sections']
        ids = [s['id'] for s in sections]
        if len(ids) != len(set(ids)) or not all(re.fullmatch(r'[a-z0-9-]+', i) for i in ids):
            raise ValueError('Invalid/duplicate historical essay section')
        out = ['<article class="history-essay"><p class="eyebrow">' + link(page, 'research.html', '专题研究') + ' / 史事细读</p>',
               '<h1>' + esc(article['title']) + '</h1>',
               '<p class="lead">' + esc(article['lead']) + '</p>',
               '<p>本站整理与分析 · 核读日期：' + esc(article['reviewedOn']) + '。文中概述与解释不属于上传译本；引文可回到原文核对。</p>',
               '<nav aria-label="文章目录"><ol>' + ''.join(f'<li><a href="#{esc(s["id"])}">{esc(s["title"])}</a></li>' for s in sections) + '</ol></nav>']
        for section in sections:
            if len(section.get('reviewNote', '')) < 20 or not section['sources']:
                raise ValueError('Missing historical essay research notes')
            out.append(f'<section id="{esc(section["id"])}"><h2>{esc(section["title"])}</h2>')
            out.extend('<p>' + esc(p) + '</p>' for p in section['paragraphs'])
            for ref in section['sources']:
                book = sources.canonical(ref['volume'])
                year = next(y for y in book['years'] if y['year'] == ref['year'])
                paragraph = year['paragraphs'][ref['index']]
                if digest([paragraph]) != ref['sourceHash'] or ref['excerpt'] not in paragraph['plain']:
                    raise ValueError(f'Stale historical essay source: {slug} {section["id"]}')
                target = f'volume/{ref["volume"]}/#year-{ref["year"]}-para-{ref["index"]}'
                label = f'《资治通鉴》卷{ref["volume"]} · {year_label(ref["year"])}条 · 段{ref["index"] + 1}'
                out.append('<blockquote><p>' + esc(ref['excerpt']) + '</p><cite>' + link(page, target, label + ' · 核对原文与上下文') + '</cite></blockquote>')
            out.append('</section>')
        out.append('<section class="related"><h2>沿人物与原文继续读</h2><p>' +
                   link(page, 'people/' + article['personId'] + '/', article['personName'] + '的已核读记载') + ' · ' +
                   link(page, 'volume/', '全书原文与白话目录') + ' · ' + link(page, 'research.html', '更多专题研究') + '</p></section></article>')
        pages.append((page, shell(page, article['title'], article['description'], ''.join(out))))
    return pages
