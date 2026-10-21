"""Render canonical annual pages with the same interface as reader.html.

The original static article remains available without JavaScript. Assets and
interactive controls come directly from the reader template.
"""
import json
import hashlib
import re
import posixpath
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
READER_ASSETS = ('checkin.js', 'checkin.css', 'reader.html', 'app.js', 'people.js', 'bookmarks.js', 'reader-tools.js',
                 'annotations.css', 'reading-layout.css', 'reader-tools.css', 'reader-themes.css',
                 'select-controls.css', 'select-controls.js', 'commerce.js', 'account-dialog.css', 'yearbook.css', 'yearbook-controls.js')
META_START, META_END = '<!-- annual-metadata -->', '<!-- /annual-metadata -->'
SOURCE_START, SOURCE_END = '<!-- annual-source -->', '<!-- /annual-source -->'


def between(text, start, end):
    return text.split(start, 1)[1].split(end, 1)[0]


def enhance_year_page(page, markup, volume, year):
    template = (ROOT / 'dist/reader.html').read_text()
    reader_head = re.search(r'<head>(.*?)</head>', template, re.S)[1]
    reader_body = re.search(r'<body[^>]*>(.*?)</body>', template, re.S)[1]
    # Keep the annual canonical metadata rather than the reader landing metadata.
    reader_head = re.sub(r'<script\b[^>]*type="application/ld\+json"[^>]*>.*?</script>', '', reader_head, flags=re.S)
    reader_head = re.sub(r'<meta\b[^>]*>|<title>.*?</title>|<link\b[^>]*rel="canonical"[^>]*>', '', reader_head, flags=re.S)
    if META_START in markup:
        metadata = between(markup, META_START, META_END)
        static_body = between(markup, SOURCE_START, SOURCE_END)
    else:
        metadata = re.search(r'<head>(.*?)</head>', markup, re.S)[1]
        static_body = re.search(r'<body[^>]*>(.*?)</body>', markup, re.S)[1]
        metadata = re.sub(r'<link\b[^>]*static-reading\.css[^>]*>', '', metadata)
        metadata = re.sub(r'<script\b[^>]*static-reading\.js[^>]*></script>', '', metadata)
    route = json.dumps(f'#volume-{volume}-year-{year}')
    bootstrap = '''<script>
(()=>{
 const root=new URL('../../',location.href);
 document.querySelector('base').href=root.href;
 document.documentElement.dataset.yearReader='true';
 if(!/^#(?:volume-\\d+(?:-year--?\\d+(?:-para-\\d+)?|-intro)?|people|person-[a-z0-9-]+)$/.test(location.hash)){
  document.documentElement.dataset.initialYearRoute=DEFAULT_ROUTE;
  document.documentElement.classList.add('reader-route-pending');
 }
 document.addEventListener('click',event=>{
  if(event.defaultPrevented||event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
  const link=event.target.closest('a[href^="#"]');
  if(!link||link.target||link.hasAttribute('download'))return;
  event.preventDefault();
  if(typeof updateRoute==='function'){updateRoute(link.getAttribute('href'));routeFromHash();}
  else location.hash=link.getAttribute('href');
 });
})();
</script>'''.replace('DEFAULT_ROUTE', route)
    def fallback_url(match):
        attr, value = match[1], match[2]
        if value.startswith('#'):
            value = page.removesuffix('index.html') + value
        elif value.startswith(('../', './')):
            trailing = value.endswith('/')
            value = posixpath.normpath(posixpath.join(posixpath.dirname(page), value))
            if trailing and not value.endswith('/'):
                value += '/'
        return f'{attr}="{value}"'
    static_body = re.sub(r'(href|src)="([^"]*)"', fallback_url, static_body)
    fallback = ('<noscript data-year-fallback><style>body>:not(noscript){display:none!important}</style>'
                '<link rel="stylesheet" href="static-reading.css">'
                + SOURCE_START + static_body + SOURCE_END + '</noscript>')
    return ('<!doctype html><html lang="zh-CN" data-theme="light"><head>'
            + META_START + metadata + META_END + '<base href="../../">' + bootstrap + reader_head
            + '</head><body>' + reader_body + fallback + '</body></html>\n')


def refresh_shells():
    """Update shared UI without regenerating articles or annual SEO metadata."""
    data = ROOT / 'dist'
    manifest_path = data / 'seo-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    updated = 0
    for path in sorted((data / 'year').glob('*/index.html')):
        markup = path.read_text()
        route = re.search(r'(?:location\.pathname\+location\.search\+|dataset\.initialYearRoute=)"#volume-(\d+)-year-(-?\d+)"', markup)
        if not route:
            raise ValueError(f'Annual bootstrap route missing: {path}')
        relative = path.relative_to(data).as_posix()
        refreshed = enhance_year_page(relative, markup, int(route[1]), int(route[2]))
        for start, end in ((META_START, META_END), (SOURCE_START, SOURCE_END)):
            if between(refreshed, start, end) != between(markup, start, end):
                raise ValueError(f'Shell refresh changed annual source or metadata: {relative}')
        if refreshed != markup:
            path.write_text(refreshed)
            updated += 1
        manifest['pages'][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    for relative in READER_ASSETS:
        manifest['assets'][relative] = hashlib.sha256((data / relative).read_bytes()).hexdigest()
    manifest['publicPages']['reader.html'] = hashlib.sha256((data / 'reader.html').read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'Updated {updated} annual reader shells; original articles and canonical metadata unchanged.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-shell-only', action='store_true',
                        help='Preserve existing articles and SEO metadata; update reader UI only.')
    if parser.parse_args().refresh_shell_only:
        refresh_shells()
        return
    # Recreate annual fallbacks from the same source-bound generator as all
    # static pages, rather than preserving an outdated copy of their articles.
    from build_seo import Sources, selection, year_pages
    data = ROOT / 'dist'
    sources = Sources(data)
    sources.source('catalog.json')
    config, _, _ = selection(sources)
    pages = year_pages(sources, config)
    for relative, markup in pages:
        (data / relative).write_text(markup)
    manifest_path = data / 'seo-manifest.json'
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text())
        def digest(path):
            return hashlib.sha256(path.read_bytes()).hexdigest()
        # Synchronize the manifest with current local generated content,
        # including the translation corrections already applied to volume pages.
        for relative in manifest['pages']:
            manifest['pages'][relative] = digest(data / relative)
        manifest['inputs'].update(sources.inputs)
        for relative in READER_ASSETS:
            manifest['assets'][relative] = digest(data / relative)
        for relative in manifest['publicPages']:
            manifest['publicPages'][relative] = digest(data / (relative or 'index.html'))
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
    print(f'Updated {len(pages)-1} annual pages from reader.html; source-bound static articles retained without JavaScript.')


if __name__ == '__main__':
    main()
