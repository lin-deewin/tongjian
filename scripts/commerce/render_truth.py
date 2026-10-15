#!/usr/bin/env python3
"""Publish the approved PDF text as an article, with explicit minimal edits."""
import hashlib
import json
import re
from html import escape
from pathlib import Path

from lxml import html
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / 'artifacts/monetization/truth-pack-content.json'
PDF = ROOT / 'output/pdf/tongjian-truth-reader.pdf'
REPORT = ROOT / 'artifacts/monetization/pdf-article-fidelity.json'

content = json.loads(SOURCE.read_text())
pages = {p['id']: p for p in content['pages']}
reader = PdfReader(PDF)
clean = lambda t: re.sub(r'[\s\u2060\ufeff]', '', t)
assert len(reader.pages) == len(content['pages'])
pdf_checks = 0
for pg, pdf_pg in zip(content['pages'], reader.pages):
    text = clean(pdf_pg.extract_text() or '')
    for b in pg['blocks']:
        if b['type'] in ('p', 'heading', 'quote'):
            assert clean(b['text']) in text, (pg['id'], b['text'])
            pdf_checks += 1

# These replace only booklet labels and sentences that relied on a removed
# exercise. Historical narrative and its substantive analysis are not rewritten.
edits = {
    ('opening', 3): ('读这本小册时', '阅读这六个案例时'),
    ('opening', 6): ('为本册自行整理', '为本文自行整理'),
    ('gan-analysis', 5): ('这是本册提出的观察方法', '这是本文提出的观察方法'),
    ('xiang-analysis', 6): ('可以。接待条件由汉方掌握', '即使范增没有私通，汉方仍能制造这场接待。接待条件由汉方掌握'),
    ('deer-analysis', 8): ('可能确有共识，也可能有人担心发言代价。', '“没有人反对”，可能确有共识，也可能有人担心发言代价。'),
    ('zhao-analysis', 6): ('前两句分别检查来源与推理连接，第三句作出远超这份材料的永久保证。',
                          '“这份告发的来源有漏洞”和“增加校尉不必然支持谋反”，分别检查来源与推理连接；“霍光永远不会作乱”则作出远超这份材料的永久保证。'),
    ('sources', 0): ('本册依据通鉴年鉴收录的胡三省注本正文，并参考网站既有“判断真伪”专题。原文短引已逐条与本地段落核对；叙事、解释、练习及图表为本册自行整理，不取用上传现代译文作为正文。图示只表达当次事件的特定路径，不是完整人物关系网。',
                     '本文依据通鉴年鉴收录的胡三省注本正文，并参考网站既有“判断真伪”专题。原文短引已逐条与本地段落核对；叙事、解释及图表为本文自行整理，不取用上传现代译文作为正文。图示只表达当次事件的特定路径，不是完整人物关系网。'),
}
analysis_headings = {
    'chu-analysis': '交付的先后次序',
    'gan-analysis': '继续追问事实',
    'xiang-analysis': '场景能够证明什么',
    'wu-analysis': '核查的实际过程',
    'deer-analysis': '表达条件与真实共识',
    'zhao-analysis': '这条判断的边界',
}
kept, removed, modified = [], [], []


def esc(t):
    return escape(str(t), quote=True)


def local_href(href):
    prefix = 'https://deewins.top/tongjian/'
    assert href.startswith(prefix)
    return href[len(prefix):]


def svg_text(label, x, cy, cls):
    lines = label.split('\n')
    y = cy - (len(lines) - 1) * 11
    return f'<text class="{cls}" x="{x}" text-anchor="middle">' + ''.join(
        f'<tspan x="{x}" y="{y + i * 22}">{esc(line)}</tspan>'
        for i, line in enumerate(lines)) + '</text>'


def graph_svg(block, graph_id, mobile=False):
    width, height = (340, 398) if mobile else (780, 160)
    marker = graph_id + ('-mobile-arrow' if mobile else '-desktop-arrow')
    nodes = block['nodes']
    positions = {}
    if mobile:
        for i, n in enumerate(nodes):
            positions[n['id']] = (30, 20 + i * 134, 280, 70)
    else:
        for i, n in enumerate(nodes):
            positions[n['id']] = (20 + i * 270, 62, 200, 70)
    title = block['title']
    result = [f'<svg class="diagram-{("mobile" if mobile else "desktop")}" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
              f'<title>{esc(title)}</title>',
              f'<defs><marker id="{marker}" markerWidth="9" markerHeight="9" refX="8" refY="4.5" orient="auto"><path d="M1 1 L8 4.5 L1 8" class="arrow-head"/></marker></defs>']
    for edge in block['edges']:
        a, b = positions[edge['from']], positions[edge['to']]
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        if mobile:
            x1 = x2 = 170
            y1, y2 = (ay + ah + 5, by - 5) if by > ay else (ay - 5, by + bh + 5)
            tx, ty = 185, (y1 + y2) / 2 + 5
            anchor = 'start'
            # Keep the mobile label clear of the vertical path.
            lines = [edge['label']] if len(edge['label']) <= 7 else [edge['label'][:5], edge['label'][5:]]
        else:
            y1 = y2 = ay + ah / 2
            x1, x2 = (ax + aw + 5, bx - 5) if bx > ax else (ax - 5, bx + bw + 5)
            tx, ty = (x1 + x2) / 2, 39
            anchor = 'middle'
            lines = [edge['label']]
        dash = ' stroke-dasharray="5 4"' if edge.get('dashed') else ''
        result += [f'<line class="diagram-arrow" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" marker-end="url(#{marker})"{dash}/>']
        result += [f'<text class="diagram-edge-label" x="{tx}" text-anchor="{anchor}">' + ''.join(
            f'<tspan x="{tx}" y="{ty + i * 18}">{esc(line)}</tspan>' for i, line in enumerate(lines)) + '</text>']
    for node in nodes:
        x, y, w, h = positions[node['id']]
        result += [f'<rect class="diagram-node" x="{x}" y="{y}" width="{w}" height="{h}" rx="4"/>',
                   svg_text(node['label'], x + w / 2, y + h / 2 + 6, 'diagram-node-label')]
    result += ['</svg>']
    return ''.join(result)


def render_block(page_id, index, level=3):
    b = pages[page_id]['blocks'][index]
    typ = b['type']
    if typ == 'exercise' or (page_id == 'opening' and index in (4, 5)):
        removed.append({'page': page_id, 'block': index, 'reason': 'exercise-or-reading-instructions'})
        return ''
    attrs = f'data-pdf-page="{page_id}" data-pdf-block="{index}"'
    kept.append({'page': page_id, 'block': index, 'type': typ})
    if typ == 'p':
        text = b['text']
        if (page_id, index) in edits:
            old, new = edits[page_id, index]
            assert old in text
            text = text.replace(old, new)
            modified.append({'page': page_id, 'block': index, 'original': b['text'], 'article': text,
                             'reason': 'booklet-label-or-removed-question-connection'})
        return f'<p {attrs}>{esc(text)}</p>'
    if typ == 'heading':
        text = b['text']
        if text == '参考分析':
            text = analysis_headings[page_id]
            modified.append({'page': page_id, 'block': index, 'original': b['text'], 'article': text,
                             'reason': 'replace-answer-heading-only'})
        return f'<h{level} {attrs}>{esc(text)}</h{level}>'
    if typ == 'quote':
        ref = b['ref']
        return (f'<blockquote class="quote" {attrs} data-volume="{ref["volume"]}" data-year="{ref["year"]}" data-paragraph="{ref["index"]}">'
                f'<p class="source-text">{esc(b["text"])}</p><cite>{esc(b["source"])}<br>'
                f'<a href="{esc(local_href(b["href"]))}">阅读本段原文 →</a></cite></blockquote>')
    if typ == 'source':
        return f'<p class="article-source" {attrs}><a href="{esc(local_href(b["href"]))}">{esc(b["text"])}</a></p>'
    if typ == 'diagram':
        gid = page_id + '-graph'
        return (f'<figure class="article-diagram" {attrs}><h4>{esc(b["title"])}</h4>'
                + graph_svg(b, gid) + graph_svg(b, gid, True)
                + f'<figcaption>{esc(b["caption"])}</figcaption></figure>')
    if typ == 'table':
        widths = b.get('widths', [1] * len(b['headers']))
        cols = ''.join(f'<col style="width:{100 * w / sum(widths):.3f}%">' for w in widths)
        heads = ''.join(f'<th scope="col">{esc(t)}</th>' for t in b['headers'])
        rows = ''.join('<tr>' + ''.join(f'<td>{esc(t)}</td>' for t in row) + '</tr>' for row in b['rows'])
        return f'<div class="article-table-wrap" {attrs}><table class="article-table"><colgroup>{cols}</colgroup><thead><tr>{heads}</tr></thead><tbody>{rows}</tbody></table></div>'
    if typ == 'list':
        return '<ul ' + attrs + '>' + ''.join(f'<li>{esc(t)}</li>' for t in b['items']) + '</ul>'
    raise ValueError((page_id, index, typ))


def render_page(page_id, level=3, skip=()):
    return '\n'.join(render_block(page_id, i, level) for i in range(len(pages[page_id]['blocks'])) if i not in skip)


sections = [
    ('chenzhen', 'chu-story', 'chu-analysis'),
    ('ganmao', 'gan-story', 'gan-analysis'),
    ('chenping', 'xiang-story', 'xiang-analysis'),
    ('wugu', 'wu-story', 'wu-analysis'),
    ('deer', 'deer-story', 'deer-analysis'),
    ('zhaodi', 'zhao-story', 'zhao-analysis'),
]
toc = ''.join(f'<li><a href="#{sid}">{esc(pages[story]["kicker"])}：{esc(pages[story]["title"])}</a></li>' for sid, story, _ in sections)
toc += '<li><a href="#comparison">六种困难，需要六种核验</a></li><li><a href="#practice">给下一步，找一个够用的依据</a></li>'
intro = (f'<section class="article-section" id="question"><h2>{esc(pages["opening"]["title"])}</h2>'
         + render_page('opening', skip=(6,))
         + '<div class="method" aria-label="文章目录"><ul>' + toc + '</ul></div></section>')
body = [intro]
for sid, story, analysis in sections:
    pg = pages[story]
    body += [f'<section class="article-section" id="{sid}"><p class="label">{esc(pg["kicker"])}</p><h2>{esc(pg["title"])}</h2>',
             f'<p class="dek">{esc(pg["subtitle"])}</p><div class="case">',
             render_page(story),
             f'<div class="case-analysis"><h3>{esc(pages[analysis]["title"])}</h3>',
             render_page(analysis, 4), '</div></div></section>']
for sid, pid in [('comparison', 'comparison'), ('practice', 'method')]:
    body += [f'<section class="article-section" id="{sid}"><h2>{esc(pages[pid]["title"])}</h2>', render_page(pid), '</section>']
body += ['<section class="article-section" id="limits"><h2>来源与阅读边界</h2>',
         render_block('opening', 6), render_page('sources'), '</section>']

doc = '''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>先别急着相信 · 判断真伪 · 通鉴年鉴</title>
<meta name="description" content="六个历史现场，六种判断困难。从楚怀王到汉昭帝，追问承诺、见闻、调查与沉默如何影响判断，结合图示、比较与原文出处。">
<link rel="stylesheet" href="research-topic.css">
<link rel="stylesheet" href="truth-article.css?v=20261014-pdf-text">
</head>
<body><header><div class="header-inner"><a class="brand" href="./" aria-label="通鉴年鉴主页"><span class="seal" aria-hidden="true">鉴</span>通鉴年鉴</a><nav aria-label="主导航"><a href="reader.html">读通鉴</a><a href="research.html" aria-current="page">专题研究</a><a href="ruler-deaths.html">君主之死</a><a href="./#about">关于本站</a></nav></div></header>
<main>
<p class="eyebrow"><a href="research.html">专题研究</a> / 判断真伪</p>
<h1>先别急着相信</h1>
<p class="dek">''' + esc(pages['cover']['blocks'][0]['text']) + '''</p>
''' + '\n'.join(body) + '''
<p class="footer-link"><a href="research.html">返回专题研究</a> · <a href="reader.html">从年表继续读《资治通鉴》 →</a></p>
</main>
</body>
</html>
'''

for pid in ('practice', 'practice-answer', 'discussion'):
    removed.append({'page': pid, 'reason': 'whole-training-or-host-page'})
removed += [{'page': 'cover', 'block': 1, 'reason': 'workbook-reading-prompt'},
            {'page': 'cover', 'block': 2, 'reason': 'pdf-edition-label'}]

tree = html.fromstring(doc)
for record in kept:
    elements = tree.xpath(f'//*[@data-pdf-page="{record["page"]}" and @data-pdf-block="{record["block"]}"]')
    assert len(elements) == 1, record
    block = pages[record['page']]['blocks'][record['block']]
    if block['type'] == 'p':
        changed = next((m for m in modified if m['page'] == record['page'] and m['block'] == record['block']), None)
        assert elements[0].text_content() == (changed['article'] if changed else block['text']), record
story_p = sum(b['type'] == 'p' for _, story, _ in sections for b in pages[story]['blocks'])
story_verbatim = sum(1 for r in kept if r['page'].endswith('-story') and r['type'] == 'p')
assert story_verbatim == story_p
for bad in ('主持人', '读书会', '会议', '练习', '参考分析', '参考答案', '填写', '作答', '轮到你', '先停一下'):
    # The concluding ordinary phrase '先停下来' is preserved, not a task prompt.
    assert bad not in tree.xpath('//main')[0].text_content(), bad

REPORT.write_text(json.dumps({
    'source_pdf': str(PDF), 'pdf_sha256': hashlib.sha256(PDF.read_bytes()).hexdigest(),
    'pdf_text_blocks_verified': pdf_checks,
    'story_paragraphs_verbatim': story_verbatim,
    'retained_blocks': kept, 'removed_blocks': removed, 'minimal_edits': modified,
    'article_sha256': hashlib.sha256(doc.encode()).hexdigest(),
}, ensure_ascii=False, indent=2) + '\n')
print(f'Article built from approved PDF: {len(kept)} blocks retained, {story_verbatim} story paragraphs verbatim, {len(modified)} minimal label/connection edits.')
