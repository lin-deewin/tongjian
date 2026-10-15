"""Check reader tool panels against the local dist server on port 8000."""
from pathlib import Path
from playwright.sync_api import sync_playwright
Path('artifacts/reader-tools').mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 page=browser.new_page(viewport={'width':1440,'height':1000});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://localhost:8000/reader.html#volume-1-year-402')
 page.locator('.tools-reading').wait_for()
 assert not page.locator('.reader-toolbar').is_visible()
 assert page.locator('.reader-tools>button').count()==5
 page.screenshot(path='artifacts/reader-tools/desktop.png')
 page.locator('.reader-tools [data-reader-tool="catalog"]').click()
 assert page.locator('#readerToolPanel #volumeSelect').count()==1
 assert page.locator('#volumeSelect option').count()==294
 assert page.locator('#volumeSelect optgroup').count()>1
 page.screenshot(path='artifacts/reader-tools/catalog-desktop.png')
 page.locator('#volumeSelect').select_option('2')
 page.wait_for_url('**/reader.html#volume-2')
 assert page.locator('#annualPage #volumeSelect').is_visible()
 assert not page.locator('#readerToolPanel').is_visible()
 page.goto('http://localhost:8000/reader.html#volume-1-year-402')
 page.locator('.reader-tools [data-reader-tool="catalog"]').click()
 page.locator('#readerYear').select_option('403')
 page.wait_for_url('**/reader.html#volume-1-year-403')
 page.locator('.reader-tools [data-reader-tool="catalog"]').click()
 page.locator('.tool-catalog-events details[open] .tool-read-event').first.click()
 page.wait_for_url('**/reader.html#*-para-*')
 page.locator('.reader-tools [data-reader-tool="mode"]').click()
 page.locator('[data-reading-mode="modern"]').click()
 assert page.locator('#readerScroll').evaluate("e=>e.classList.contains('mode-modern')")
 page.locator('[data-reading-mode="compare"]').click()
 page.keyboard.press('Escape')
 assert page.locator('#readerBackdrop').is_visible()
 page.locator('.reader-tools [data-reader-tool="font"]').click()
 page.locator('#larger').click()
 assert page.locator('.tool-font-value').inner_text()=='20'
 page.locator('#showNotes').check()
 assert page.locator('.original.hide-notes').count()==0
 page.locator('[data-close-tool]').click()
 page.locator('.reader-tools [data-reader-tool="theme"]').click()
 page.locator('[data-choose-theme="gold"]').click()
 assert page.locator('html').get_attribute('data-theme')=='gold'
 page.locator('[data-choose-theme="light"]').click()
 page.keyboard.press('Escape')
 page.locator('.reader-tools [data-reader-tool="notes"]').click()
 assert page.locator('.annotation-dialog').is_visible()
 page.locator('.annotation-dialog [data-close]').click()
 page.set_viewport_size({'width':390,'height':844})
 assert page.locator('.reader-mobile-tools').bounding_box()['height']<50
 page.locator('.reader-mobile-tools').click()
 page.screenshot(path='artifacts/reader-tools/mobile-menu.png')
 page.locator('.reader-tool-menu [data-reader-tool="mode"]').click()
 page.screenshot(path='artifacts/reader-tools/mobile-mode.png')
 page.locator('[data-reading-mode="modern"]').click()
 page.locator('[data-close-tool]').click()
 page.locator('.reader-mobile-tools').click()
 page.locator('.reader-tool-menu [data-reader-tool="mode"]').click()
 page.locator('[data-reading-mode="compare"]').click()
 page.locator('[data-close-tool]').click()
 page.screenshot(path='artifacts/reader-tools/mobile-reading.png')
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.locator('#nextYear').click();page.wait_for_url('**/reader.html#volume-1-year-402')
 page.locator('.reader-mobile-tools').click()
 page.locator('.reader-tool-menu [data-reader-tool="catalog"]').click()
 page.screenshot(path='artifacts/reader-tools/catalog-mobile.png')
 page.keyboard.press('Escape')
 assert not page.locator('#readerToolPanel').is_visible()
 page.locator('#closeReader').click()
 assert page.locator('#annualPage #volumeSelect').is_visible()
 assert not errors,errors
 print('PASS: reused grouped 294-volume selector, years/events, mode/font/notes/theme, Escape, mobile menu, previous/next, return to yearbook; no errors/overflow')
 browser.close()
