"""Archive four Wikipedia biographies with full article text and licensed local images.

Run with --refresh to fetch new article snapshots; otherwise rebuild from sources.
Book text and reviewed people JSON are deliberately left untouched.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import time
from urllib.parse import quote, unquote, urlencode, urljoin, urlsplit
from urllib.request import Request, urlopen

from lxml import etree, html
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ROOT / 'sources/wikipedia'
OUTPUT = ROOT / 'dist/biographies'
MEDIA = OUTPUT / 'images'
NAMES = ['刘备', '诸葛亮', '张飞', '关羽']
HEADERS = {'User-Agent': 'Mozilla/5.0'}


def fetch(url):
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=HEADERS), timeout=40) as response:
                return response.read()
        except Exception:
            if attempt == 2:
                raise
            time.sleep((attempt + 1) * 5)


def plain(value):
    return ' '.join(html.fromstring('<div>' + value + '</div>').text_content().split())


def content(raw):
    root = html.fromstring(raw)
    return max(root.xpath('//div[contains(concat(" ", normalize-space(@class), " "), " mw-parser-output ")]'),
               key=lambda element: len(element.text_content()))


def file_title(image):
    # Derive the actual file from the thumbnail URL, including icons without links.
    path = unquote(urlsplit(image.get('src', '')).path)
    if '/thumb/' in path:
        return 'File:' + path.split('/')[-2].replace('_', ' ')
    if '/wikipedia/' in path:
        return 'File:' + path.split('/')[-1].replace('_', ' ')
    raise ValueError('Unsupported image URL: ' + path)


def image_metadata(titles, refresh):
    path = SOURCES / 'image-metadata.json'
    known = {} if refresh or not path.exists() else json.loads(path.read_text())
    pending = sorted(set(titles) - known.keys())
    for start in range(0, len(pending), 40):
        batch = pending[start:start + 40]
        for host in ['commons.wikimedia.org', 'zh.wikipedia.org']:
            params = dict(action='query', format='json', titles='|'.join(batch), prop='imageinfo',
                          iiprop='url|size|extmetadata', redirects=1)
            data = json.loads(fetch('https://' + host + '/w/api.php?' + urlencode(params)))
            aliases = {item['from']: item['to'] for key in ['normalized', 'redirects']
                       for item in data.get('query', {}).get(key, [])}
            pages = {page['title']: page for page in data['query']['pages'].values()}
            for title in batch:
                canonical = title
                while canonical in aliases:
                    canonical = aliases[canonical]
                page = pages.get(canonical, {})
                if page.get('imageinfo'):
                    known[title] = page['imageinfo'][0]
            batch = [title for title in batch if title not in known]
            if not batch:
                break
        if batch:
            raise ValueError('Image metadata missing: ' + ', '.join(batch))
    path.write_text(json.dumps(known, ensure_ascii=False, indent=2) + '\n')
    return known


def download_image(item):
    title, info = item
    meta = info.get('extmetadata', {})
    license_name = plain(meta.get('LicenseShortName', {}).get('value', ''))
    if not license_name or not any(label in license_name.lower() for label in
                                  ['public domain', 'cc', 'gfdl', 'attribution']):
        raise ValueError('No reusable image license: ' + title + ' (' + license_name + ')')
    key = hashlib.sha256(title.encode()).hexdigest()[:20]
    original_url = info['url'].split('?')[0]
    output_path = MEDIA / (key + '.webp')
    width, height = info['width'], info['height']
    original_path = SOURCES / 'images' / (key + Path(urlsplit(original_url).path).suffix.lower())
    archived_raster = SOURCES / 'images' / (key + '.download')
    if not output_path.exists():
        if original_path.exists() and original_path.suffix != '.svg':
            raster = original_path.read_bytes()
        elif archived_raster.exists():
            raster = archived_raster.read_bytes()
        else:
            path = urlsplit(original_url).path
            thumb_path = path.replace('/commons/', '/commons/thumb/').replace('/zh/', '/zh/thumb/')
            size = 960 if width >= 300 else 120
            extension = '.png' if path.lower().endswith('.svg') else ''
            high_resolution = 'https://thumb.wikimedia.org' + thumb_path + '/' + str(size) + 'px-' + path.split('/')[-1] + extension
            urls = [high_resolution, info['articleThumbnail'], original_url]
            raster = None
            for url in dict.fromkeys(urls):
                try:
                    with urlopen(Request(url, headers=HEADERS), timeout=25) as response:
                        raster = response.read()
                    # Check bytes, so an error document is never saved as an image.
                    with Image.open(io.BytesIO(raster)) as check:
                        check.verify()
                    break
                except Exception as error:
                    print('Image fallback:', title, str(error), flush=True)
                    raster = None
            if raster is None:
                raise ValueError('All image download variants failed: ' + title)
            archived_raster.write_bytes(raster)
        with Image.open(io.BytesIO(raster)) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((1600, 2400), Image.Resampling.LANCZOS)
            if image.mode not in ('RGB', 'RGBA'):
                image = image.convert('RGBA' if 'transparency' in image.info else 'RGB')
            image.save(output_path, 'WEBP', quality=90, method=6)
    with Image.open(output_path) as image:
        display_width, display_height = image.size
    print('Image saved:', title, flush=True)
    return title, dict(file=title, src='biographies/images/' + output_path.name,
                      width=display_width, height=display_height, originalWidth=width,
                      originalHeight=height, originalUrl=original_url,
                      sourceUrl=info['descriptionurl'], license=license_name,
                      licenseUrl=meta.get('LicenseUrl', {}).get('value', ''),
                      artist=plain(meta.get('Artist', {}).get('value', '')),
                      credit=plain(meta.get('Credit', {}).get('value', '')))


def transform(name, person_id, raw, images):
    article = content(raw)
    # Keep every article section, references, infobox, caption, succession table and
    # related-topic navigation. Remove only executable/style markup and edit controls.
    for element in article.xpath('.//script|.//style|.//link|.//meta|.//iframe|.//object|.//embed|.//form|.//input|.//button'):
        element.drop_tree()
    for element in list(article.iter()):
        if not isinstance(element.tag, str):
            parent = element.getparent()
            if parent is not None:
                parent.remove(element)
            continue
        classes = element.get('class', '').split()
        if any(c in classes for c in ['mw-editsection', 'noteTA', 'mw-empty-elt']):
            element.drop_tree()
    text_before = ''.join(article.itertext())
    # Long infoboxes remain complete but do not squeeze the introductory prose
    # between two parallel floats. Keep adjacent source tables together.
    infoboxes = article.xpath('./table[contains(concat(" ",normalize-space(@class)," ")," infobox ")]')
    if infoboxes:
        details = etree.Element('details', {'class': 'wiki-facts'})
        summary = etree.SubElement(details, 'summary', {'class': 'wiki-generated-summary'})
        summary.text = '人物信息表 · 身份、生卒、家庭与官职'
        article.insert(article.index(infoboxes[0]), details)
        grid = etree.SubElement(details, 'div', {'class': 'wiki-facts-grid'})
        for table in infoboxes:
            grid.append(table)
    for notice in article.xpath('./table[contains(concat(" ",normalize-space(@class)," ")," ambox ")]'):
        details = etree.Element('details', {'class': 'wiki-source-notice'})
        summary = etree.SubElement(details, 'summary', {'class': 'wiki-generated-summary'})
        summary.text = '原条目提示'
        article.replace(notice, details)
        details.append(notice)
    prefix = 'wiki-' + person_id + '-'
    sections = []
    for heading in article.xpath('.//h2|.//h3|.//h4|.//h5|.//h6'):
        if heading.get('id'):
            sections.append(dict(id=prefix + heading.get('id'), title=heading.text_content().strip(),
                                 level=int(heading.tag[1])))
    article_images = []
    portrait_title = None
    infobox_images = article.xpath('.//table[contains(@class, "infobox")]//img')
    if infobox_images:
        portrait_title = file_title(infobox_images[0])
    preferred_portraits = {'关羽': 'File:Guanyu.jpg', '诸葛亮': 'File:Zhuge Liang by Zhang Feng.jpg'}
    if preferred_portraits.get(name) in {file_title(image) for image in article.xpath('.//img')}:
        portrait_title = preferred_portraits[name]
    for image in article.xpath('.//img'):
        title = file_title(image)
        asset = images[title]
        image.attrib.clear()
        image.set('src', asset['src'])
        image.set('alt', title.removeprefix('File:').rsplit('.', 1)[0])
        image.set('width', str(asset['width']))
        image.set('height', str(asset['height']))
        image.set('loading', 'lazy')
        image.set('decoding', 'async')
        if asset not in article_images:
            article_images.append(asset)
        parent = image.getparent()
        if parent.tag == 'a':
            parent.set('href', asset['originalUrl'])
            parent.set('class', 'wiki-image-link')
    for element in article.iter():
        if not isinstance(element.tag, str):
            continue
        if element.get('id'):
            element.set('id', prefix + element.get('id'))
        for attribute in list(element.attrib):
            if attribute.lower().startswith('on') or attribute not in {
                'id', 'class', 'title', 'lang', 'dir', 'href', 'src', 'alt', 'width', 'height',
                'colspan', 'rowspan', 'scope', 'loading', 'decoding', 'start', 'value', 'type'}:
                del element.attrib[attribute]
        if element.tag == 'a':
            href = element.get('href', '')
            if href.startswith('#'):
                anchor = prefix + unquote(href[1:])
                element.set('href', '#' + anchor)
                element.set('data-wiki-anchor', anchor)
            else:
                href = urljoin('https://zh.wikipedia.org', href)
                if urlsplit(href).scheme not in ('https', 'http'):
                    element.attrib.pop('href', None)
                    continue
                element.set('href', href)
                element.set('target', '_blank')
                element.set('rel', 'noopener noreferrer')
    # Wide tables keep their full content in independently scrollable wrappers.
    for table in article.xpath('.//table[not(ancestor::table)]'):
        if 'infobox' in table.get('class', '').split():
            continue
        parent = table.getparent()
        wrapper = etree.Element('div', {'class': 'wiki-table-scroll', 'tabindex': '0',
                                       'role': 'region', 'aria-label': '资料表格，可横向滚动'})
        parent.replace(table, wrapper)
        wrapper.append(table)
    # Related-page templates stay available, without overwhelming the biography.
    for navbox in article.xpath('.//div[contains(concat(" ",normalize-space(@class)," ")," navbox ") and not(ancestor::div[contains(concat(" ",normalize-space(@class)," ")," navbox ")])]'):
        parent = navbox.getparent()
        details = etree.Element('details', {'class': 'wiki-related'})
        summary = etree.SubElement(details, 'summary', {'class': 'wiki-generated-summary'})
        summary.text = '相关条目'
        parent.replace(navbox, details)
        details.append(navbox)
    preserved_text = ''.join(article.xpath('.//text()[not(ancestor::summary[@class="wiki-generated-summary"])]'))
    assert preserved_text == text_before, 'Article text or source order changed: ' + name
    revision = int(re.search(r'"wgRevisionId":(\d+)', raw.decode()).group(1))
    toc_ids = {section['id'] for section in sections}
    element_ids = {element.get('id') for element in article.iter() if isinstance(element.tag, str)}
    assert toc_ids <= element_ids
    for anchor in article.xpath('.//a[@data-wiki-anchor]'):
        # Some source templates contain anchors to collapsed/omitted site chrome.
        if anchor.get('data-wiki-anchor') not in element_ids:
            original = anchor.get('data-wiki-anchor').removeprefix(prefix)
            anchor.set('href', 'https://zh.wikipedia.org/zh-cn/' + quote(name) + '#' + quote(original))
            del anchor.attrib['data-wiki-anchor']
            anchor.set('target', '_blank')
            anchor.set('rel', 'noopener noreferrer')
    body = ''.join(etree.tostring(child, encoding='unicode', method='html') for child in article)
    return dict(id=person_id, name=name, source='中文维基百科',
                sourceUrl='https://zh.wikipedia.org/zh-cn/' + quote(name), revision=revision,
                revisionUrl='https://zh.wikipedia.org/w/index.php?oldid=' + str(revision),
                historyUrl='https://zh.wikipedia.org/w/index.php?title=' + quote(name) + '&action=history',
                license='CC BY-SA 4.0', licenseUrl='https://creativecommons.org/licenses/by-sa/4.0/deed.zh-hans',
                fetchedAt=datetime.fromtimestamp((SOURCES / (name + '.html')).stat().st_mtime, timezone.utc).isoformat(),
                adaptation='保留条目内容；调整版式、站内锚点及图片格式，相关条目导航改为折叠显示。',
                sections=sections, portrait=images.get(portrait_title), images=article_images,
                textLength=len(text_before), html=body)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    for path in [SOURCES, SOURCES / 'images', OUTPUT, MEDIA]:
        path.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((ROOT / 'dist/people-index.json').read_text())['people']
    people = {name: next(person for person in catalog if person['name'] == name) for name in NAMES}
    raw = {}
    for name in NAMES:
        path = SOURCES / (name + '.html')
        if args.refresh or not path.exists():
            path.write_bytes(fetch('https://zh.wikipedia.org/zh-cn/' + quote(name)))
        raw[name] = path.read_bytes()
    titles = {file_title(image) for source in raw.values() for image in content(source).xpath('.//img')}
    metadata = image_metadata(titles, args.refresh)
    for source in raw.values():
        for image in content(source).xpath('.//img'):
            metadata[file_title(image)]['articleThumbnail'] = urljoin('https://zh.wikipedia.org', image.get('src'))
    with ThreadPoolExecutor(max_workers=3) as executor:
        images = dict(executor.map(download_image, ((title, metadata[title]) for title in sorted(titles))))
    report = []
    for name in NAMES:
        person_id = people[name]['id']
        biography = transform(name, person_id, raw[name], images)
        (OUTPUT / (person_id + '.json')).write_text(json.dumps(biography, ensure_ascii=False, indent=2) + '\n')
        report.append({key: biography[key] for key in ['id', 'name', 'revision', 'textLength', 'fetchedAt']})
        report[-1].update(sections=len(biography['sections']), images=len(biography['images']))
        print(name, biography['textLength'], 'characters;', len(biography['sections']), 'sections;', len(biography['images']), 'local images', flush=True)
    (OUTPUT / 'manifest.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')


if __name__ == '__main__':
    main()
