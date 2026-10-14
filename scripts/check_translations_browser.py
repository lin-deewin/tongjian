"""Real-browser upload recovery and missing-text checks on desktop and mobile."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from pathlib import Path
import json, shutil
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass
def main():
    out=ROOT/'artifacts/translations/browser';out.mkdir(exist_ok=True,parents=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT/'dist')))
    Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}'
    results=[];errors=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=shutil.which('google-chrome'),args=['--no-sandbox'])
            page=browser.new_page(viewport={'width':1440,'height':960})
            page.on('pageerror',lambda e:errors.append(str(e)))
            for size in ({'width':1440,'height':960},{'width':390,'height':844}):
                page.set_viewport_size(size)
                page.goto(url+'/reader.html#volume-28-year-48-para-1')
                page.wait_for_selector('#para-1')
                row=page.locator('.compare-row').filter(has=page.locator('#para-1'))
                assert '王政君' in row.locator('.modern-text').inner_text()
                assert 'AI补译' not in page.locator('#readerContent').inner_text()
                assert '混有白话' in page.locator('#readerContent').inner_text()
                page.screenshot(path=str(out/f'recovery-{size["width"]}.png'))
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                if size['width']==390:
                    assert row.locator('.translation-cell').bounding_box()['y']>row.locator('.original-cell').bounding_box()['y']
                else:
                    assert row.locator('.translation-cell').bounding_box()['x']>row.locator('.original-cell').bounding_box()['x']
                page.goto(url+'/reader.html#volume-29-year-39-para-7')
                page.wait_for_selector('#para-7')
                assert '译本记年：' in page.locator('#readerContent').inner_text() and '38' in page.locator('#readerContent').inner_text()
                page.goto(url+'/reader.html#volume-113-year--403-para-0')
                page.wait_for_selector('#para-0')
                missing=page.locator('.compare-row').filter(has=page.locator('#para-0'))
                assert '未提供或未能可靠对应' in missing.locator('.modern-text').inner_text()
                page.goto(url+'/reader.html#volume-28')
                page.wait_for_function('book && book.volume===28 && !readerOpen')
                page.locator('#searchScope').select_option('all')
                page.locator('#search').fill('把三辅')
                page.wait_for_function('searchComplete && searchChecked===294',timeout=60000)
                assert page.evaluate('fullSearchHits.some(y=>y._volume===28)')
                page.goto(url+'/index.html')
                assert '1727段' in page.locator('#about').inner_text()
                assert '28,857' in page.locator('body').inner_text()
                results.append(dict(width=size['width'],uploadedRecovery=True,crossYearWarning=True,missingPreserved=True,workerSearch=True,noHorizontalOverflow=True))
            assert not errors,errors
            browser.close()
    finally:server.shutdown()
    (out/'checks.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(results,ensure_ascii=False))
if __name__=='__main__':main()
