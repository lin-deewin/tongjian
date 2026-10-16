"""Idempotent metadata and ordinary source links for existing public pages.

This does not rebuild, unlock, or modify private articles and never adds crawler-only
content. Run build_seo.py after rebuilding any existing article's public HTML.
"""
import html
import json
import re

from lxml import html as H

BASE = 'https://deewins.top/'
PUBLIC = ['index.html', 'reader.html', 'research.html', 'themes.html', 'truth.html',
          'relationships.html', 'risk.html', 'power-rules.html', 'ruler-deaths.html']
TOPICS = PUBLIC[3:]


def meta(markup, name, value, prop=False):
    attribute = 'property' if prop else 'name'
    tag = f'<meta {attribute}="{name}" content="{html.escape(value, quote=True)}">'
    pattern = rf'<meta\b(?=[^>]*\b{attribute}=[\"\']{re.escape(name)}[\"\'])[^>]*>'
    if re.search(pattern, markup, re.I):
        return re.sub(pattern, lambda _: tag, markup, flags=re.I)
    return markup.replace('</head>', tag + '\n</head>', 1)


def optimize(data):
    for name in PUBLIC:
        path = data / name
        markup = path.read_text()
        tree = H.fromstring(markup)
        title = tree.xpath('string(//title)')
        description = tree.xpath('//meta[@name="description"]/@content')[0]
        if name == 'truth.html':
            title = '资治通鉴判断真伪：楚怀王与张仪免费试读｜先别急着相信'
            description = '免费试读楚怀王与张仪的六百里土地之约，理解承诺与履约顺序。完整专题另含五组案例与核验方法，付费阅读范围与购买方式见页面说明。'
        if name == 'research.html':
            title = '资治通鉴专题研究：人物选择、权力、关系与判断'
            description = '从吴起、商鞅、楚怀王、韩信等人物的具体处境进入资治通鉴，阅读孤立、判断真伪、承诺与关系、风险、权力规则及君主之死专题，附原文出处。'
        markup = re.sub(r'<title>.*?</title>', lambda _: '<title>' + html.escape(title) + '</title>', markup, count=1, flags=re.S)
        canonical = BASE if name == 'index.html' else BASE + name
        tag = f'<link rel="canonical" href="{canonical}">'
        pattern = r'<link\b(?=[^>]*\brel=[\"\']canonical[\"\'])[^>]*>'
        markup = re.sub(pattern, lambda _: tag, markup, flags=re.I) if re.search(pattern, markup, re.I) else markup.replace('</head>', tag + '\n</head>')
        for field, value, prop in [
            ('description', description, False), ('og:title', title, True),
            ('og:description', description, True), ('og:url', canonical, True),
            ('og:site_name', '资治通鉴', True), ('og:type', 'article' if name in TOPICS and name != 'truth.html' else 'website', True),
            ('og:image', BASE + 'share-card.svg', True), ('twitter:card', 'summary', False),
        ]:
            markup = meta(markup, field, value, prop)
        schema = {'@context': 'https://schema.org', '@graph': [
            {'@type': 'WebPage', '@id': canonical + '#page', 'url': canonical,
             'name': title, 'description': description, 'inLanguage': 'zh-CN', 'isPartOf': {'@id': BASE + '#website'}},
            {'@type': 'BreadcrumbList', 'itemListElement': [
                {'@type': 'ListItem', 'position': 1, 'name': '资治通鉴', 'item': BASE},
            ] + ([{'@type': 'ListItem', 'position': 2, 'name': title, 'item': canonical}] if name != 'index.html' else [])}
        ]}
        if name == 'index.html':
            schema['@graph'].append({'@type': 'WebSite', '@id': BASE + '#website', 'name': '资治通鉴', 'url': BASE, 'inLanguage': 'zh-CN'})
        elif name in TOPICS and name != 'truth.html':
            schema['@graph'][0]['mainEntity'] = {'@type': 'Article', 'headline': title,
                'description': description, 'inLanguage': 'zh-CN', 'mainEntityOfPage': canonical,
                'isAccessibleForFree': True}
        # Avoid inventing publication dates, author identities, reviews or paid-content markup.
        markup = re.sub(r'<script\b[^>]*\bid=[\"\']seoSchema[\"\'][^>]*>.*?</script>\s*', '', markup, flags=re.S)
        encoded = json.dumps(schema, ensure_ascii=False).replace('<', '\\u003c')
        markup = markup.replace('</head>', '<script type="application/ld+json" id="seoSchema">' + encoded + '</script>\n</head>', 1)
        if name in TOPICS:
            def source_link(match):
                quote, volume, year, index = match.groups()
                target = f'volume/{volume}/#year-{year}' + (f'-para-{index}' if index is not None else '')
                return 'href=' + quote + target + quote
            markup = re.sub(r'href=([\"\'])(?:\./)?reader\.html#volume-(\d+)-year-(-?\d+)(?:-para-(\d+))?\1', source_link, markup)
            block = '<!-- seo-related:start --><p class="footer-link"><a href="year/">逐年原文与白话</a> · <a href="volume/">查阅全书卷次原文与白话</a> · <a href="people/">人物记载与出处</a> · <a href="research.html">专题目录</a></p><!-- seo-related:end -->'
            markup = re.sub(r'<!-- seo-related:start -->.*?<!-- seo-related:end -->\s*', '', markup, flags=re.S)
            markup = markup.replace('</main>', block + '\n</main>', 1)
        if name == 'reader.html':
            if 'href="reading.html"' not in markup:
                markup = markup.replace('<div class="header-right">', '<div class="header-right"><a href="reading.html">卷次与人物目录</a>', 1)
            markup = markup.replace('全书294卷全文取自你上传的 EPUB · 对照上传的胡注本与柏杨版文件',
                                    '全书294卷 · 胡三省注本原文与所据译本白话对照')
            markup = markup.replace('网站载入你上传的胡三省注版与白话版 EPUB', '本站依据胡三省注本原文与所据白话译本整理')
            if 'id="readerStaticFallback"' not in markup:
                markup = markup.replace('<section class="chronicle" id="chronicle">',
                    '<section class="chronicle" id="chronicle"><noscript id="readerStaticFallback"><p>逐年交互阅读器需要 JavaScript。也可直接打开<a href="volume/">全书294卷原文与白话目录</a>或<a href="people/">人物记载目录</a>阅读完整内容。</p></noscript>', 1)
        if name == 'index.html':
            markup = markup.replace('打开周纪、汉纪与唐纪的原文白话，沿赵襄子、张仪、赵武灵王的记载核对出处。',
                                    '浏览全书294卷原文、胡注与可对应白话，沿已核读的人物记载回查出处。')
        path.write_text(markup)
    # Utility and duplicate landing pages are not search landing pages.
    path = data / 'account.html'
    path.write_text(meta(path.read_text(), 'robots', 'noindex,follow'))
    path = data / 'home.html'
    markup = path.read_text()
    if 'rel="canonical"' not in markup:
        markup = markup.replace('</head>', f'<link rel="canonical" href="{BASE}">\n</head>', 1)
    path.write_text(meta(markup, 'robots', 'noindex,follow'))
