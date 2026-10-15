#!/usr/bin/env python3
"""Read-only block coverage and text checks for an approved PDF article."""
import argparse
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from urllib.parse import urlsplit


def normalize(value):
    return re.sub(r'[\s\u2060\ufeff]', '', str(value))


class ArticleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.links = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        if tag == 'a':
            self.links += [v for k, v in attrs if k == 'href' and v]

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def read_article(path):
    raw = path.read_text(encoding='utf-8')
    if path.suffix.lower() in ('.html', '.htm'):
        parser = ArticleText()
        parser.feed(raw)
        return normalize(' '.join(parser.parts)), parser.links
    # Keep Markdown link labels and Mermaid labels in the text comparison.
    links = re.findall(r'\]\(([^)]+)\)', raw)
    text = re.sub(r'<!--[\s\S]*?-->', '', raw)
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.I)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    return normalize(html.unescape(text)), links


def parts(block):
    typ = block['type']
    if typ in ('p', 'heading', 'source'):
        return [block['text']]
    if typ == 'quote':
        return [block['text']] + ([block['source']] if block.get('source') else [])
    if typ == 'exercise':
        return [block.get('title', ''), block.get('prompt', '')]
    if typ == 'list':
        return block['items']
    if typ == 'table':
        return block['headers'] + [cell for row in block['rows'] for cell in row]
    if typ == 'diagram':
        return ([block['title'], block.get('caption', '')]
                + [node['label'] for node in block['nodes']]
                + [edge['label'] for edge in block['edges']])
    raise ValueError(f'Unsupported source block type: {typ}')


def link_key(href):
    parsed = urlsplit(href)
    filename = parsed.path.rsplit('/', 1)[-1]
    return filename, parsed.fragment


def link_matches(source_href, article_href):
    source, candidate = urlsplit(source_href), urlsplit(article_href)
    if candidate.netloc or candidate.scheme:
        return (source.scheme, source.netloc, source.path, source.query, source.fragment) == (
            candidate.scheme, candidate.netloc, candidate.path, candidate.query, candidate.fragment)
    return link_key(source_href) == link_key(article_href)


def verify(source, policy, article_path, pdf_path=None):
    article_text, article_links = read_article(article_path)
    source_blocks = {}
    errors = []
    for page in source['pages']:
        for index, block in enumerate(page['blocks']):
            key = (page['id'], index)
            if key in source_blocks:
                errors.append(f'Duplicate source key: {key}')
            source_blocks[key] = block
    decisions = {}
    for decision in policy['blocks']:
        key = (decision['page'], decision['block'])
        if key in decisions:
            errors.append(f'Duplicate policy key: {key}')
        decisions[key] = decision
    for key in source_blocks.keys() - decisions.keys():
        errors.append(f'Unclassified source block: {key}')
    for key in decisions.keys() - source_blocks.keys():
        errors.append(f'Invalid policy key: {key}')
    counts = {'keep': 0, 'edit': 0, 'omit': 0, 'source_blocks': len(source_blocks),
              'text_parts_checked': 0, 'links_checked': 0}
    for key, decision in decisions.items():
        if key not in source_blocks:
            continue
        block = source_blocks[key]
        action = decision.get('action')
        if action not in ('keep', 'edit', 'omit'):
            errors.append(f'Invalid action for {key}: {action}')
            continue
        counts[action] += 1
        if action in ('edit', 'omit') and not decision.get('reason', '').strip():
            errors.append(f'Missing reason for {action}: {key}')
        if action == 'omit':
            continue
        expected = parts(block)
        if action == 'edit':
            expected = decision.get('expected_parts')
            if not isinstance(expected, list) or not expected or not all(isinstance(p, str) for p in expected):
                errors.append(f'Missing complete expected_parts for edited block: {key}')
                continue
        for text in expected:
            if normalize(text):
                counts['text_parts_checked'] += 1
                if normalize(text) not in article_text:
                    errors.append(f'Missing/changed text {key}: {text[:80]}')
        if block.get('href'):
            counts['links_checked'] += 1
            if not any(link_matches(block['href'], href) for href in article_links):
                errors.append(f'Missing source link {key}: {block["href"]}')
    if pdf_path:
        from pypdf import PdfReader
        pdf = PdfReader(pdf_path)
        if len(pdf.pages) != len(source['pages']):
            errors.append('PDF and source page counts differ')
        for page, pdf_page in zip(source['pages'], pdf.pages):
            pdf_text = normalize(pdf_page.extract_text() or '')
            for index, block in enumerate(page['blocks']):
                for text in parts(block):
                    if normalize(text) and normalize(text) not in pdf_text:
                        errors.append(f'Source differs from PDF {(page["id"], index)}: {text[:80]}')
    return {'passed': not errors, 'counts': counts, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--article', required=True, type=Path)
    parser.add_argument('--policy', required=True, type=Path)
    parser.add_argument('--pdf', type=Path)
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    result = verify(json.loads(args.source.read_text()), json.loads(args.policy.read_text()),
                    args.article, args.pdf)
    if args.report:
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
