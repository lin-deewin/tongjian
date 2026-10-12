"""Real-browser checks for the four complete Wikipedia biography pilots."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import shutil
from threading import Thread

from lxml import html
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'artifacts/biographies'


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    manifest = json.loads((ROOT / 'dist/biographies/manifest.json').read_text())
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT / 'dist')))
    Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}/reader.html'
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=shutil.which('google-chrome') or shutil.which('google-chrome-stable'),
                                                 args=['--no-sandbox'])
            page = browser.new_page(viewport={'width':1440, 'height':1000})
            errors, missing = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: missing.append(response.url) if response.status >= 400 else None)
            for item in manifest:
                biography = json.loads((ROOT / f'dist/biographies/{item["id"]}.json').read_text())
                # Article sections and every citation remain, not just a prose summary.
                archived = html.parse(str(ROOT / f'sources/wikipedia/{item["name"]}.html'))
                original = max(archived.xpath('//div[contains(concat(" ",normalize-space(@class)," ")," mw-parser-output ")]'),
                               key=lambda element: len(element.text_content()))
                rebuilt = html.fromstring('<div>' + biography['html'] + '</div>')
                assert [node.text_content().strip() for node in original.xpath('.//h2|.//h3|.//h4|.//h5|.//h6')] == [node.text_content().strip() for node in rebuilt.xpath('.//h2|.//h3|.//h4|.//h5|.//h6')]
                assert len(original.xpath('.//li[starts-with(@id,"cite_note")]')) == len(rebuilt.xpath('.//li[contains(@id,"-cite_note")]'))
                assert all((ROOT / 'dist' / image['src']).exists() for image in biography['images'])
                assert not rebuilt.xpath('.//script|.//style|.//iframe|.//*[@onclick]')
                page.set_viewport_size({'width':1440, 'height':1000})
                page.goto(url + '#person-' + item['id'])
                page.wait_for_selector('.wiki-article')
                assert page.locator('.person-identity h1').inner_text() == item['name']
                assert page.locator('.biography-toc a').count() == len(biography['sections']) + 2
                assert page.locator('.person-timeline-panel').is_hidden()
                # Force local media to decode, including lazy images near the article end.
                failed = page.locator('.wiki-article img, .person-portrait img').evaluate_all('''async images => {
                  for (const image of images) image.loading = 'eager';
                  return (await Promise.all(images.map(async image => {
                    try { await image.decode(); return null; } catch { return image.src; }
                  }))).filter(Boolean);
                }''')
                assert not failed, failed
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(ARTIFACTS / (item['id'] + '-desktop.png')))
                page.locator('.biography-toc .toc-level-2').first.click()
                assert page.url.endswith('#person-' + item['id'])
                assert page.evaluate('scrollY > 200')
                citation = page.locator('.wiki-article sup.reference a[data-wiki-anchor]:visible').first
                if citation.count():
                    target = citation.get_attribute('data-wiki-anchor')
                    citation.click()
                    assert page.evaluate('(id) => document.activeElement.id === id', target)
                    assert page.url.endswith('#person-' + item['id'])
                page.locator('[data-person-panel="timeline"]').click()
                page.wait_for_selector('.person-timeline-panel:not(.hidden)')
                page.click('[data-timeline-layout]')
                assert page.locator('.timeline-vertical').count()
                page.locator('.timeline-event-link').first.click()
                page.wait_for_selector('#readerBackdrop:not(.hidden)')
                assert '-para-' in page.url
                page.click('#closeReader')
                page.wait_for_selector('.timeline-vertical')
                assert page.locator('[data-person-panel="timeline"]').get_attribute('aria-pressed') == 'true'
                page.click('[data-person-panel="biography"]')
                page.wait_for_selector('.wiki-article')
                page.set_viewport_size({'width':390, 'height':844})
                page.reload()
                page.wait_for_selector('.wiki-article')
                page.locator('.person-portrait img').evaluate('(image) => image.decode()')
                page.evaluate('scrollTo(0,0)')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(ARTIFACTS / (item['id'] + '-mobile.png')))
                page.locator('.biography-toc summary').click()
                page.locator('.wiki-facts summary').click()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.locator('.wiki-facts summary').click()
                page.locator('.biography-toc .toc-level-2').first.click()
                assert page.url.endswith('#person-' + item['id'])
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(ARTIFACTS / (item['id'] + '-mobile-article.png')))
                print('PASS:', item['name'], 'full sections, references, local images, desktop/mobile, TOC, citation anchors, timeline and source return', flush=True)
            page.goto(url + '#person-wu-qi')
            page.wait_for_selector('[data-timeline-layout]')
            assert page.locator('.person-panel-tabs').count() == 0
            assert not errors, errors
            assert not missing, missing
            browser.close()
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
