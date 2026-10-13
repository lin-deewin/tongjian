"""Validate the source-bound monarch-death topic in real Chromium."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import csv
import io
import json
from pathlib import Path
import shutil
from threading import Thread

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / 'artifacts/ruler-deaths'


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    data = json.loads((ROOT / 'dist/ruler-deaths.json').read_text())
    records = data['rows']
    assert len({row['name'] for row in records}) == len(records)
    assert sum(data['totals']['categories'].values()) == len(records)
    assert sum(data['totals']['eras'].values()) == len(records)
    # Reopening original excerpts does not depend on the topic's own explanations.
    books = {}
    for row in records:
        for source in row['sources']:
            if source['volume'] not in books:
                books[source['volume']] = json.loads((ROOT / f'dist/volume{source["volume"]}.json').read_text())
            year = next(y for y in books[source['volume']]['years'] if y['year'] == source['year'])
            assert year['paragraphs'][source['anchor']]['plain'] == source['quote']
        assert row['witness'] in row['sources'][0]['quote']
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT / 'dist')))
    Thread(target=server.serve_forever, daemon=True).start()
    url = f'http://127.0.0.1:{server.server_port}'
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(executable_path=shutil.which('google-chrome') or shutil.which('google-chrome-stable'), args=['--no-sandbox'])
            page = browser.new_page(viewport={'width':1440, 'height':1000})
            errors, failures = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: failures.append(response.url) if response.status >= 400 else None)
            page.goto(url + '/ruler-deaths.html')
            page.wait_for_selector('.life-dot')
            assert page.locator('.life-dot').count() == len(records)
            assert page.locator('#metrics strong').first.inner_text() == str(len(records))
            assert page.locator('#rulerRows tr').count() == 20
            assert page.locator('.era-row').count() == 5
            assert '尚非全书' in page.locator('#coverageNote').inner_text()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            page.screenshot(path=str(ARTIFACTS / 'desktop-overview.png'), full_page=True)
            page.locator('#pagination [data-page="2"]').click()
            assert '第 2 /' in page.locator('#pagination').inner_text()
            assert 'page=2' in page.url
            page.locator('#resetFilters').click()
            page.locator('#causeBars [data-cause="killed"]').click()
            assert page.locator('.life-dot').count() == data['totals']['categories']['killed']
            assert page.locator('#metrics strong').first.inner_text() == str(data['totals']['categories']['killed'])
            page.reload()
            page.wait_for_selector('.life-dot')
            assert page.locator('#causeFilter').input_value() == 'killed'
            page.select_option('#eraFilter', 'warring')
            expected = [r for r in records if r['category'] == 'killed' and r['era'] == 'warring']
            assert page.locator('.life-dot').count() == len(expected)
            page.click('#resetFilters')
            page.fill('#rulerSearch', '秦武王')
            assert page.locator('.life-dot').count() == 1
            assert page.locator('.ruler-name').inner_text() == '秦武王'
            page.locator('.life-dot').click()
            assert page.locator('#rulerDetail').is_visible()
            assert '绝脉而薨' in page.locator('.detail-source blockquote').inner_text()
            assert page.locator('.detail-source mark').count() >= 1
            with page.expect_popup() as popup_event:
                page.locator('.detail-source>a').first.click()
            popup = popup_event.value
            popup.wait_for_selector('#readerBackdrop:not(.hidden)')
            assert popup.url.endswith('#volume-3-year-307-para-1')
            assert popup.locator('#para-1').count()
            popup.close()
            page.keyboard.press('Escape')
            assert not page.locator('#rulerDetail').is_visible()
            with page.expect_download() as download_event:
                page.click('#exportCsv')
            download = download_event.value
            content = Path(download.path()).read_text(encoding='utf-8-sig')
            exported = list(csv.reader(io.StringIO(content)))
            assert len(exported) == 2 and exported[1][0] == '秦武王'
            page.fill('#rulerSearch', '不存在的君主XYZ')
            assert page.locator('.life-dot').count() == 0
            assert page.locator('.empty-row').count() == 1
            assert page.locator('#exportCsv').is_disabled()
            assert page.locator('#metrics strong').first.inner_text() == '0'
            for width in [768,390,320]:
                page.set_viewport_size({'width':width, 'height':844})
                page.goto(url + '/ruler-deaths.html')
                page.wait_for_selector('.life-dot')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), width
                assert page.locator('.life-dot').count() == len(records)
                page.screenshot(path=str(ARTIFACTS / f'viewport-{width}.png'), full_page=True)
                page.locator('#storyCards [data-ruler]').first.click()
                assert page.locator('#rulerDetail').is_visible()
                assert page.locator('#rulerDetail').evaluate('e => e.scrollWidth <= e.clientWidth')
                page.screenshot(path=str(ARTIFACTS / f'detail-{width}.png'))
                page.click('#closeDetail')
            page.goto(url + '/')
            assert page.locator('#explore a[href="ruler-deaths.html"]').count() == 1
            assert not errors, errors
            assert not failures, failures
            browser.close()
            print(f'PASS: {len(records)} original witnesses, unique rulers and reconciled counts; charts, filters, pagination, URL restore, source popup, CSV, empty state, homepage entry; desktop, tablet, 390px and 320px.')
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
