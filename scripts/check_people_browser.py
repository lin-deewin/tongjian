"""Real Chromium checks for people navigation, dates, source anchors and phone layout."""
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
import tempfile
import shutil
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass
server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT / 'dist')))
Thread(target=server.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{server.server_port}/'

def scroll_y(page):
    return page.evaluate('scrollY')

try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=shutil.which('google-chrome') or shutil.which('google-chrome-stable'), headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width':1280, 'height':900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(url + '#volume-1')
        page.wait_for_selector('[data-event-filter="person"]')
        assert not page.locator('#volumePeople').is_visible()
        page.click('[data-event-filter="person"]')
        page.wait_for_selector('#volumePeople:not(.hidden)')
        assert page.locator('#volumePeople [data-person]').count() == 5
        assert page.locator('#volumePeople').bounding_box()['y'] > page.locator('.event-filter-bar').bounding_box()['y']
        page.locator('#volumePeople [data-person="zhi-bo"]').click()
        page.wait_for_selector('#peopleScope')
        page.click('#returnFromPeople')
        page.wait_for_selector('#volumePeople:not(.hidden)')
        assert page.url.endswith('#volume-1')
        page.select_option('#volumeSelect', '2')
        page.wait_for_function('document.querySelector("#volumePeople [data-person=shang-yang]")')
        assert page.locator('#volumePeople [data-person]').count() == 3
        assert page.locator('#volumePeople [data-person="shang-yang"]').count() == 1
        assert page.locator('#volumePeople [data-person="wei-wen-hou"]').count() == 0
        page.select_option('#volumeSelect', '3')
        page.wait_for_function('document.querySelector("#volumePeople").textContent.includes("尚在整理")')
        page.click('[data-event-filter="all"]')
        assert not page.locator('#volumePeople').is_visible()
        page.goto(url + '#volume-1-year-403')
        page.wait_for_selector('.person-name')
        assert page.evaluate('timelineVisible({year:-100,sources:[{year:-100}]},-99,false)') is False
        assert page.evaluate('timelineVisible({year:-100,sources:[{year:-100}]},-101,false)') is True
        assert page.evaluate('timelineVisible({year:1,sources:[{year:1}]},-1,false)') is True
        assert page.locator('.paragraph-people').count() > 0
        page.locator('.person-name').filter(has_text='吴起').first.scroll_into_view_if_needed()
        original_scroll = scroll_y(page)
        page.locator('.person-name').filter(has_text='吴起').first.click()
        page.wait_for_selector('#peopleScope')
        assert page.title().startswith('吴起')
        assert page.locator('.person-timeline li').count() == 3
        assert not page.locator('[data-source-year="381"]').count()
        page.check('#peopleFuture')
        assert page.locator('.person-timeline li').count() == 8
        page.select_option('#peopleScope', 'all')
        assert page.locator('.person-timeline li').count() == 9
        page.select_option('#peopleCategory', '战争')
        assert page.locator('.person-timeline li').count() == 1
        page.select_option('#peopleCategory', 'all')
        source = page.locator('[data-source-year="381"]')
        source.scroll_into_view_if_needed()
        profile_scroll = scroll_y(page)
        axis_scroll = page.locator('#timeline-dated').evaluate('e=>e.scrollLeft')
        source.click()
        page.wait_for_selector('#readerBackdrop:not(.hidden)')
        assert page.url.endswith('#volume-1-year-381-para-0')
        assert page.locator('#para-0').locator('..').count()
        assert page.locator('#closeReader').inner_text() == '← 返回吴起时间轴'
        page.click('#closeReader')
        page.wait_for_selector('#peopleScope')
        assert abs(scroll_y(page)-profile_scroll) < 5
        assert abs(page.locator('#timeline-dated').evaluate('e=>e.scrollLeft')-axis_scroll) < 5
        page.click('#returnFromPeople')
        page.wait_for_selector('#readerBackdrop:not(.hidden)')
        assert page.url.endswith('#volume-1-year-403')
        assert abs(scroll_y(page)-original_scroll) < 5
        # Browser Back restores the reading origin, not just its year.
        page.locator('.person-name').filter(has_text='吴起').first.click()
        page.wait_for_selector('#peopleScope')
        page.go_back()
        page.wait_for_selector('#readerBackdrop:not(.hidden)')
        assert abs(scroll_y(page)-original_scroll) < 5
        page.goto(url + '#person-shang-yang')
        page.reload()
        page.wait_for_selector('#peopleScope')
        assert page.locator('.person-timeline li').count() == 12
        assert page.locator('.timeline-date').all_text_contents()[0].startswith('前361年')
        page.select_option('#peopleScope', 'all')
        assert page.locator('.person-timeline li').count() == 13
        # Independent source deep links survive reload and focus the cited row.
        page.locator('[data-source-year="338"]').first.click()
        page.wait_for_selector('#readerBackdrop:not(.hidden)')
        page.reload()
        page.wait_for_selector('.compare-row.active')
        assert page.locator('.compare-row.active #para-0').count() == 1
        # Two ambiguous historical labels are scoped to reviewed passages.
        page.goto(url + '#volume-2-year-353')
        page.wait_for_selector('.person-name[data-person="sun-bin"]')
        assert page.locator('.person-name').filter(has_text='孙子').count() > 0
        page.goto(url + '#volume-1-year-403')
        page.wait_for_selector('.person-name[data-person="zhi-bo"]')
        assert page.locator('#para-11 .person-name[data-person="zhi-bo"]').filter(has_text='智襄子').count() == 1
        assert page.locator('.person-name[data-person="zhao-xiang-zi"]').filter(has_text='智襄子').count() == 0
        page.goto(url + '#people')
        page.wait_for_selector('#peopleSearch')
        page.fill('#peopleSearch', '卫鞅')
        assert page.locator('.person-card').count() == 1
        page.locator('#peopleDirectory [data-person="shang-yang"]').click()
        page.wait_for_selector('#peopleScope')
        if page.locator('#peopleFuture').count():
            page.check('#peopleFuture')
        page.evaluate('scrollTo(0,0)')
        artifact = Path(tempfile.gettempdir()) / 'tongjian-people-qa'
        artifact.mkdir(exist_ok=True)
        page.screenshot(path=str(artifact/'desktop.png'))
        page.set_viewport_size({'width':390, 'height':844})
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        assert page.locator('#timeline-dated').evaluate('e=>e.scrollWidth>e.clientWidth')
        cards=page.locator('#timeline-dated li')
        assert cards.nth(1).bounding_box()['x'] > cards.nth(0).bounding_box()['x']
        page.click('[data-timeline-id="dated"][data-timeline-step="1"]')
        page.wait_for_function('document.querySelector("#timeline-dated").scrollLeft>50')
        page.screenshot(path=str(artifact/'mobile.png'))
        # Ordinary reader navigation and modes still work on a phone.
        page.goto(url + '#volume-1-year-403')
        page.wait_for_selector('.person-name')
        page.click('[data-reading-mode="modern"]')
        page.locator('.modern-text .person-name').filter(has_text='吴起').first.click()
        page.wait_for_selector('#peopleScope')
        page.click('#returnFromPeople')
        page.wait_for_selector('#readerBackdrop:not(.hidden)')
        assert page.locator('#readerScroll').evaluate("e=>e.classList.contains('mode-modern')")
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
        assert not errors, errors
        print('PASS: inline names, scoped aliases, date filters, unknown dates, source links/reload, return scroll, browser Back, directory search, mobile layout and reading mode')
        print('Screenshots:', artifact)
        browser.close()
finally:
    server.shutdown()
