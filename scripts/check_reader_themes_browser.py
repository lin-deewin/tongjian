"""Verify reader palettes, theme persistence and synchronization on the local server."""
from pathlib import Path
from playwright.sync_api import sync_playwright
Path('artifacts/reader-themes').mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True);context=browser.new_context(viewport={'width':1440,'height':1000});page=context.new_page();errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 url='http://localhost:8000/reader.html#volume-1-year-402'
 page.goto(url);page.locator('.reader-tools [data-reader-tool="theme"]').click()
 assert page.locator('#readerToolPanel .theme-select option').count()==4
 for name,bg,ink in [('night','rgb(28, 28, 30)','rgb(199, 199, 204)'),('white','rgb(255, 255, 255)','rgb(32, 38, 48)')]:
  page.locator('[data-choose-theme="'+name+'"]').click()
  assert page.url==url
  assert page.locator('html').get_attribute('data-theme')==name
  assert page.locator('.reader').evaluate('e=>getComputedStyle(e).backgroundColor')==bg
  assert page.locator('.modern-text').first.evaluate('e=>getComputedStyle(e).color')==ink
  page.keyboard.press('Escape');page.screenshot(animations='disabled',path=f'artifacts/reader-themes/{name}-desktop.png')
  page.locator('.reader-tools [data-reader-tool="font"]').click();page.screenshot(animations='disabled',path=f'artifacts/reader-themes/{name}-settings.png');page.keyboard.press('Escape')
  page.locator('.reader-tools [data-reader-tool="notes"]').click();page.screenshot(animations='disabled',path=f'artifacts/reader-themes/{name}-notes.png');page.locator('.annotation-dialog [data-close]').click()
  page.reload();page.locator('.compare-row').first.wait_for();assert page.locator('html').get_attribute('data-theme')==name
  page.set_viewport_size({'width':390,'height':844});page.screenshot(animations='disabled',path=f'artifacts/reader-themes/{name}-mobile.png');assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
  page.locator('.reader-mobile-tools').click();page.locator('.reader-tool-menu [data-reader-tool="theme"]').click();assert page.locator('#readerToolPanel .theme-select').input_value()==name
  page.keyboard.press('Escape');page.set_viewport_size({'width':1440,'height':1000});page.locator('.reader-tools [data-reader-tool="theme"]').click()
 second=context.new_page();second.goto(url);second.locator('.compare-row').first.wait_for();assert second.locator('html').get_attribute('data-theme')=='white'
 page.locator('[data-choose-theme="night"]').click();second.wait_for_function("document.documentElement.dataset.theme==='night'")
 page.locator('[data-choose-theme="gold"]').click();assert page.locator('#readerScroll').evaluate('e=>getComputedStyle(e).backgroundColor')=='rgb(233, 223, 202)'
 page.locator('[data-choose-theme="light"]').click();page.keyboard.press('Escape');page.locator('#closeReader').click();assert page.locator('#annualPage .theme-select').count()==0
 assert page.locator('body>header .theme-select').input_value()=='light'
 assert not errors,errors
 print('PASS: night/white palette, desktop/mobile/settings/notes, persistence, cross-tab sync, existing themes and yearbook selector; no browser errors/overflow')
 browser.close()
