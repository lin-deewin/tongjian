"""Extract uploaded EPUB in source TOC order without changing its text."""
import argparse
import html
import json
import posixpath
import zipfile
from pathlib import Path
from lxml import etree


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('epub')
    parser.add_argument('--output', default='dist/vertical-book')
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    catalog = []
    with zipfile.ZipFile(args.epub) as archive:
        toc = etree.fromstring(archive.read('OEBPS/toc.ncx'))
        ns = {'n': 'http://www.daisy.org/z3986/2005/ncx/'}
        for number, item in enumerate(toc.findall('.//n:navPoint', ns)):
            title = item.find('.//n:text', ns).text
            path = posixpath.normpath(posixpath.join('OEBPS', item.find('n:content', ns).get('src').split('#')[0]))
            root = etree.fromstring(archive.read(path))
            body = root.find('{http://www.w3.org/1999/xhtml}body')
            def render(el):
                tag = etree.QName(el).localname
                content = html.escape(el.text or '') + ''.join(render(child) + html.escape(child.tail or '') for child in el)
                if tag == 'br':
                    return '<br/>'
                if tag in ('p', 'h1', 'h2', 'h3', 'div'):
                    return f'<{tag}>{content}</{tag}>'
                if tag == 'span' and 'zhushi' in el.get('class', '').split():
                    return f'<span class="note">{content}</span>'
                return content
            content = render(body)
            # Check all source characters, including note text, survive extraction.
            check = etree.fromstring(('<body>' + content + '</body>').encode())
            assert ''.join(body.itertext()) == ''.join(check.itertext()), path
            name = f'chapter-{number:03}.json'
            (out / name).write_text(json.dumps({'title': title, 'html': content}, ensure_ascii=False), encoding='utf-8')
            catalog.append({'title': title, 'file': name, 'source': path})
    (out / 'catalog.json').write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Extracted and verified {len(catalog)} chapters')


if __name__ == '__main__':
    main()
