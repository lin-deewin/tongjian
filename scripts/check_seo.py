#!/usr/bin/env python3
"""Check generated HTML, complete source order, translations and crawl links."""
import copy
import json
import re
from urllib.parse import unquote, urljoin, urlsplit
import xml.etree.ElementTree as ET

from lxml import html
from build_seo import BASE, CONFIG, NS, ROOT, Sources, modern_html, read, sha, validate_person, selection

DATA = ROOT / 'dist'


def text(node):
    return ''.join(node.itertext())


def css_class(node, name):
    return node.xpath(f'.//*[contains(concat(" ",normalize-space(@class)," ")," {name} ")]')


def local_target(url):
    path = unquote(urlsplit(url).path)
    if not path.startswith('/'):
        return None
    relative = path.removeprefix('/')
    result = DATA / (relative + 'index.html' if relative.endswith('/') or not relative else relative)
    assert result.resolve().is_relative_to(DATA.resolve()), path
    return result


def main():
    manifest = read(DATA / 'seo-manifest.json')
    from history_articles import CONFIG as HISTORY_CONFIG
    assert sha(HISTORY_CONFIG.read_bytes()) == manifest['historyArticlesSHA256']
    config, _, excluded = selection(Sources(DATA))
    assert manifest['volumes'] == config['volumes'] and manifest['people'] == config['people']
    assert manifest['configurationSHA256'] == sha(CONFIG.read_bytes())
    assert manifest['excludedPeople'] == excluded
    assert set(manifest['people']).isdisjoint({p['id'] for p in excluded})
    for name, digest in manifest['assets'].items():
        assert sha((DATA / name).read_bytes()) == digest, f'Stale asset: {name}'
    for name, digest in manifest['inputs'].items():
        assert sha((DATA / name).read_bytes()) == digest, f'Stale input: {name}; regenerate SEO pages'
    assert sha((ROOT / 'scripts/people/semantic-reviews.json').read_bytes()) == manifest['semanticReviewsSHA256']
    sources = Sources(DATA)
    reviews = {r['key']: r for r in read(ROOT / 'scripts/people/semantic-reviews.json')['reviews']}
    trees, titles, descriptions = {}, set(), set()
    originals = translations = 0
    for name, digest in manifest['pages'].items():
        path = DATA / name
        assert sha(path.read_bytes()) == digest, f'Edited generated page: {name}; edit generator instead'
        tree = html.fromstring(path.read_bytes())
        trees[name] = tree
        assert len(tree.xpath('//h1')) == 1, name
        title = tree.xpath('string(//title)')
        description = tree.xpath('//meta[@name="description"]/@content')
        assert title and title not in titles, name
        assert len(description) == 1 and description[0] not in descriptions, name
        titles.add(title)
        descriptions.add(description[0])
        assert tree.xpath('//link[@rel="canonical"]/@href') == [BASE + name.removesuffix('index.html')]
        assert tree.xpath('//link[@rel="stylesheet"]/@href')[0].endswith(
            'static-reading.css?v=' + manifest['assets']['static-reading.css'][:12])
        ids = tree.xpath('//*[@id]/@id')
        assert len(ids) == len(set(ids)), f'Duplicate IDs in {name}'
        assert 'undefined' not in text(tree) and '⟦glyph:' not in text(tree), name
        assert not tree.xpath('//script[not(@src) and not(@type="application/ld+json")]'), 'No script-only content or redirects'
        for script in tree.xpath('//script[@type="application/ld+json"]'):
            schema = json.loads(script.text)
            assert schema['@context'] == 'https://schema.org'
            assert schema['@graph'][0]['url'] == BASE + name.removesuffix('index.html')
    for volume in config['volumes']:
        book = sources.effective(volume)
        tree = trees[f'volume/{volume}/index.html']
        intro = tree.xpath('//*[contains(@class,"source-intro")]/p')
        assert [text(n) for n in intro] == [''.join(r['text'] for r in p['runs']) for p in book['intro']]
        assert tree.xpath('string(//p[@class="source-volume-title"])') == (book.get('fullTitle') or book['title'])
        years = tree.xpath('//section[@data-year]')
        assert [int(n.get('data-year')) for n in years] == [y['year'] for y in book['years']]
        for node, year in zip(years, book['years']):
            assert node.xpath('string(./p[@class="source-heading"])') == year.get('heading', '')
            ps = css_class(node, 'source-original')
            assert [int(p.get('data-index')) for p in ps] == list(range(len(year['paragraphs'])))
            assert [text(p) for p in ps] == [''.join(r['text'] for r in p['runs']) for p in year['paragraphs']]
            originals += len(ps)
            expected = [p for p in year['bilingual'] if not p['difference']]
            expected.sort(key=lambda p: p['huIndices'][0])
            expected += [p for p in year['bilingual'] if p['difference']]
            got = css_class(node, 'modern-text')
            assert len(got) == len(expected), (volume, year['year'], 'translation group coverage')
            for markup, pair in zip(got, expected):
                reference = html.fragment_fromstring('<p>' + modern_html(pair['modern'], 'index.html') + '</p>')
                assert text(markup) == text(reference), (volume, year['year'], 'translation mismatch')
            translations += len(got)
            assert len(css_class(node, 'missing')) == len(year['translationMissing'])
            assert [text(p) for p in node.xpath('./div[@class="source-transition"]/p[not(@class)]')] == year.get('after', [])
            for raw in year.get('translationBlocks', []):
                assert raw in text(node), (volume, year['year'], 'unparsed translation omitted')
            if year['year'] == 403:
                assert '追叙' in text(node)
        assert not any(y['year'] == 0 for y in book['years'])
    # Every calendar year must keep all cross-volume paragraphs in source order.
    calendar = {}
    for volume in config['volumes']:
        for year in sources.effective(volume)['years']:
            calendar.setdefault(year['year'], []).append((volume, year))
    assert len(calendar) == 1362 and 0 not in calendar
    for key, parts in calendar.items():
        name = f'year/{"bce" if key > 0 else "ce"}-{abs(key)}/index.html'
        tree = trees[name]
        sections = tree.xpath('//section[@data-year]')
        assert len(sections) == len(parts), (key, 'missing continuation')
        for section, (volume, year) in zip(sections, parts):
            assert section.get('id') == f'volume-{volume}-year-{key}'
            assert [text(n) for n in css_class(section, 'source-original')] == [
                ''.join(r['text'] for r in p['runs']) for p in year['paragraphs']]
            reference = trees[f'volume/{volume}/index.html'].xpath(f'//section[@data-year="{key}"]')[0]
            assert [text(n) for n in css_class(section, 'modern-text')] == [
                text(n) for n in css_class(reference, 'modern-text')], (volume, key, 'year translation mismatch')
    for pid in config['people']:
        person = read(DATA / 'people' / (pid + '.json'))
        validate_person(person, sources, reviews)
        tree = trees[f'people/{pid}/index.html']
        for event in person['events']:
            nodes = tree.xpath('//*[@id=$id]', id=event['id'])
            assert len(nodes) == 1 and event['summary'] in text(nodes[0]), pid
            if event['year'] is None:
                assert event['timeLabel'] in text(nodes[0]) and event['dateNote'] in text(nodes[0])
        # Matching hash alone must never substitute for a source/context review.
        bad = copy.deepcopy(person)
        bad['events'][0]['summary'] += 'changed'
        try:
            validate_person(bad, sources, reviews)
        except ValueError:
            pass
        else:
            raise AssertionError('Changed person summary accepted by source review')
    sitemap = ET.parse(DATA / 'sitemap.xml').getroot()
    assert sitemap.tag == f'{{{NS}}}urlset'
    urls = [n.text for n in sitemap.findall(f'{{{NS}}}url/{{{NS}}}loc')]
    assert len(urls) == len(set(urls))
    assert all('#' not in url and local_target(url).exists() for url in urls)
    assert {BASE + p.removesuffix('index.html') for p in manifest['pages']} <= set(urls)
    index = ET.parse(DATA / 'sitemap-index.xml').getroot()
    assert index.tag == f'{{{NS}}}sitemapindex'
    assert [n.text for n in index.findall(f'{{{NS}}}sitemap/{{{NS}}}loc')] == [BASE + 'sitemap.xml']
    assert 'Sitemap: ' + BASE + 'sitemap.xml' in (DATA / 'robots.txt').read_text()
    for name in ('account.html', 'home.html'):
        tree = html.fromstring((DATA / name).read_bytes())
        assert 'noindex' in tree.xpath('string(//meta[@name="robots"]/@content)')
        assert BASE + name not in urls
    for name, digest in manifest['publicPages'].items():
        path = DATA / (name or 'index.html')
        assert sha(path.read_bytes()) == digest, f'Stale public metadata: {name}'
        tree = html.fromstring(path.read_bytes())
        assert len(tree.xpath('//h1')) == 1 and len(tree.xpath('//link[@rel="canonical"]')) == 1
        assert tree.xpath('//link[@rel="canonical"]/@href') == [BASE + name]
        assert len(tree.xpath('//meta[@name="description"]')) == 1
        assert tree.xpath('//script[@id="seoSchema"]')
        schema = json.loads(tree.xpath('//script[@id="seoSchema"]')[0].text)
        assert schema['@graph'][0]['url'] == BASE + name
        if name == 'truth.html':
            assert '免费试读' in tree.xpath('string(//title)')
            assert not tree.xpath('//*[@id="ganmao"]'), 'Paid chapter leaked into public preview'
    # Check every ordinary internal link and static fragment on new/edited pages.
    target_ids = {}
    for name in [*manifest['pages'], *[p or 'index.html' for p in manifest['publicPages']]]:
        tree = trees.get(name)
        if tree is None:
            tree = html.fromstring((DATA / name).read_bytes())
        for value in tree.xpath('//@href|//img/@src|//script/@src'):
            url = urljoin(BASE + name, value)
            if urlsplit(url).netloc != urlsplit(BASE).netloc:
                continue
            path = local_target(url)
            if path is None or '/account/' in url or '/article/' in url:
                continue
            assert path.exists(), (name, value)
            fragment = unquote(urlsplit(url).fragment)
            if not fragment or path.suffix != '.html':
                continue
            if path.name in ('reader.html', 'index.html') and re.match(r'(volume-|person-|people|year-|search)', fragment):
                match = re.fullmatch(r'volume-(\d+)-year-(-?\d+)(?:-para-(\d+))?', fragment)
                if match:
                    book = sources.canonical(int(match[1]))
                    year = next(y for y in book['years'] if y['year'] == int(match[2]))
                    if match[3] is not None:
                        assert int(match[3]) < len(year['paragraphs'])
                continue
            if path not in target_ids:
                target_name = str(path.relative_to(DATA))
                target_tree = trees.get(target_name)
                if target_tree is None:
                    target_tree = html.fromstring(path.read_bytes())
                target_ids[path] = set(target_tree.xpath('//*[@id]/@id'))
            assert fragment in target_ids[path], (name, value, 'missing anchor')
    # Follow ordinary links from homepage: a sitemap alone is not discovery.
    pending, visited = [BASE], set()
    while pending:
        url = pending.pop()
        path = local_target(url)
        if path is None or not path.exists() or path.suffix != '.html' or path in visited:
            continue
        visited.add(path)
        tree = trees.get(str(path.relative_to(DATA)))
        if tree is None:
            tree = html.fromstring(path.read_bytes())
        for value in tree.xpath('//a[@href]/@href'):
            dest = urljoin(url, value)
            if urlsplit(dest).netloc == urlsplit(BASE).netloc:
                pending.append(dest.split('#')[0])
    assert all(DATA / name in visited for name in manifest['pages'])
    # Overlay source binding is checked even outside the initial five clean volumes.
    altered = Sources(DATA)
    altered.canonical(28)
    altered.inputs['volume28.json'] = '0' * 64
    try:
        altered.effective(28)
    except ValueError:
        pass
    else:
        raise AssertionError('Stale overlay binding accepted')
    result = dict(pages=len(manifest['pages']), volumes=len(config['volumes']), people=len(config['people']),
                  excludedPendingPeople=len(excluded), publicMetadataPages=len(manifest['publicPages']),
                  originalParagraphs=originals, translationGroups=translations,
                  sitemapURLs=len(urls), ordinaryLinksReachable=True, sourceOrder='exact',
                  staleInputGuards='passed', status='passed')
    report = ROOT / 'artifacts/seo'
    report.mkdir(parents=True, exist_ok=True)
    (report / 'static-validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
