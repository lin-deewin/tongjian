#!/usr/bin/env python3
"""Generate immutable private delivery and a chapter-whitelisted public preview."""
import argparse
import copy
import hashlib
import json
import runpy
from pathlib import Path
from lxml import html, etree

ROOT = Path(__file__).resolve().parents[1]

def sha(data):
    return hashlib.sha256(data).hexdigest()

def validate_markup(tree):
    if tree.xpath('//script|//iframe|//object|//embed|//*[local-name()="foreignObject"]'):
        raise ValueError('Active markup in content')
    for node in tree.iter():
        for key, value in node.attrib.items():
            if key.lower().startswith('on') or value.strip().lower().startswith(('javascript:', 'data:text/html')):
                raise ValueError('Unsafe content attribute')
        if node.tag in {'img', 'image'}:
            value = node.get('src', node.get('href', ''))
            if value.startswith(('http:', 'https:', '//')):
                raise ValueError('Unapproved external media')

def write_immutable(path, data):
    if path.exists() and path.read_bytes() != data:
        raise ValueError(f'Published content is immutable; increment manifest version: {path.name}')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

def build(slug):
    if slug != 'truth':
        raise ValueError('Only reviewed truth product is configured')
    manifest_path = ROOT / 'content/products' / slug / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    source = runpy.run_path(str(ROOT / manifest['source_renderer']))['doc']
    tree = html.fromstring(source)
    validate_markup(tree)
    main = tree.xpath('//main')[0]
    allowed = set(manifest['preview_sections'])
    protected = []
    for section in main.xpath('./section'):
        if section.get('id') not in allowed:
            protected.extend(''.join(p.itertext()).strip() for p in section.xpath('.//p[@data-pdf-page]') if len(''.join(p.itertext()).strip()) >= 50)
    private = copy.deepcopy(main)
    for node in private.xpath('.//*[@href]'):
        href = node.get('href')
        if not href.startswith(('#', '/', 'https://', 'http://')):
            node.set('href', '/' + href.lstrip('./'))
        elif href.startswith('./'):
            node.set('href', '/' + href[2:])
    article = (''.join(etree.tostring(node, encoding='unicode', method='html') for node in private)).encode()
    pdf = (ROOT / manifest['source_pdf']).read_bytes()
    if not pdf.startswith(b'%PDF-'):
        raise ValueError('Invalid PDF')
    directory = ROOT / 'private-content' / slug / manifest['version']
    write_immutable(directory / 'article.html', article)
    write_immutable(directory / 'reader.pdf', pdf)
    delivery = {**manifest, 'article_sha256': sha(article), 'pdf_sha256': sha(pdf),
                'relative_directory': f'{slug}/{manifest["version"]}', 'source_html_sha256': sha(source.encode())}
    write_immutable(directory / 'delivery.json', (json.dumps(delivery, ensure_ascii=False, indent=2) + '\n').encode())
    (ROOT / 'private-content' / slug / 'current.json').write_text(json.dumps(delivery, ensure_ascii=False, indent=2) + '\n')
    (directory / 'protected-paragraphs.json').write_text(json.dumps(protected, ensure_ascii=False) + '\n')
    for section in list(main.xpath('./section')):
        if section.get('id') not in allowed:
            main.remove(section)
    for anchor in main.xpath('.//a[starts-with(@href,"#")]'):
        target = anchor.get('href')[1:]
        if target not in allowed:
            anchor.set('href', '/article/truth/#' + target)
    commerce = html.fragment_fromstring('''<section class="purchase-panel" data-product="truth">
<h2>继续阅读完整专题</h2><p>试读到这里结束。购买内容包括六个案例的完整分析、比较与核验方法，以及配套 PDF。</p>
<p class="product-price" aria-live="polite">正在获取购买信息…</p>
<p><a class="purchase-button" href="/account/login/?next=/truth.html" data-buy>登录与购买</a>
 <a href="/account/purchases/">我的购买</a></p>
<label><input type="checkbox" data-accept-terms> 我已阅读并同意 <a href="/account/terms/">商品购买说明与隐私说明</a></label>
<p class="commerce-message" role="status" aria-live="polite"></p></section>''')
    main.insert(len(main) - 1, commerce)
    nav = tree.xpath('//header//nav')[0]
    nav.append(html.fragment_fromstring('<a href="account.html" data-account-link>登录</a>'))
    nav.append(html.fragment_fromstring('<a href="account.html" data-register-link>注册</a>'))
    head = tree.xpath('//head')[0]
    head.append(html.fragment_fromstring('<link rel="stylesheet" href="commerce.css?v=20261015-password">'))
    tree.xpath('//body')[0].append(html.fragment_fromstring('<script src="commerce.js?v=20261015-password" defer></script>'))
    preview = ('<!doctype html>\n' + etree.tostring(tree, encoding='unicode', method='html') + '\n').encode()
    (ROOT / 'dist/truth.html').write_bytes(preview)
    safe = ROOT / 'private-content/safe-preview' / slug / manifest['version']
    safe.mkdir(parents=True, exist_ok=True)
    (safe / 'truth.html').write_bytes(preview)
    report = ROOT / 'artifacts/commerce/content-build'
    report.mkdir(parents=True, exist_ok=True)
    (report / 'report.json').write_text(json.dumps({'slug': slug, 'version': manifest['version'],
        'source_html_sha256': delivery['source_html_sha256'], 'article_sha256': sha(article), 'pdf_sha256': sha(pdf),
        'preview_sha256': sha(preview), 'preview_sections': sorted(allowed), 'protected_paragraphs': len(protected)}, indent=2) + '\n')
    print(f'{slug}: private content built; public preview sections={sorted(allowed)}')

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--product', required=True)
    args = parser.parse_args(argv)
    build(args.product)

if __name__ == '__main__':
    main()
