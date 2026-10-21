"""Browser checks for traditional vertical annotations; requires a local dist server."""
import os
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1440,'height':1000});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(os.environ.get('TONGJIAN_TEST_URL','http://localhost:8000')+'/reader.html#volume-1-year-403');page.locator('.compare-row').first.wait_for()
 page.evaluate("setReadingMode('vertical')")
 page.locator('[data-source-block]').first.wait_for()
 def select():
  page.locator('[data-source-block]').first.evaluate('''p=>{const w=document.createTreeWalker(p,NodeFilter.SHOW_TEXT);let n;while((n=w.nextNode())&&!n.textContent.trim()){}const r=document.createRange();r.setStart(n,0);r.setEnd(n,Math.min(8,n.length));getSelection().removeAllRanges();getSelection().addRange(r)}''')
  page.locator('[data-action="highlight"]').wait_for()
 select();page.locator('[data-action="highlight"]').click();page.locator('button[data-color="green"]').click()
 assert page.locator('#traditionalReader [data-color="green"]').count()>0
 select();page.locator('[data-action="note"]').click();page.locator('#annotationThought').fill('竖版想法');page.locator('[data-save]').click()
 page.locator('#traditionalReader .has-thought').first.click();assert page.locator('#annotationThought').input_value()=='竖版想法';page.locator('[data-cancel]').click()
 select();page.locator('[data-action="bookmark"]').click()
 page.reload();page.locator('.compare-row').first.wait_for();page.evaluate("setReadingMode('vertical')")
 page.locator('#traditionalReader .has-thought').first.wait_for()
 assert page.locator('#traditionalReader [data-color="green"]').count()>0
 page.evaluate("setReadingMode('compare');document.querySelector('.annotation-launch').click()")
 page.locator('.annotation-entry[data-type="bookmark"] a').click()
 page.locator('#traditionalReader').wait_for(state='visible');page.locator('#traditionalReader .has-bookmark').first.wait_for()
 page.set_viewport_size({'width':390,'height':844});select();assert page.locator('.annotation-popover').is_visible()
 assert not errors,errors
 print('PASS: vertical highlight, note/edit, bookmark, reload restoration, library return, mobile popup; no browser errors')
 b.close()
