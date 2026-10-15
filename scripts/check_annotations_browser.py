"""Real-browser checks. Start the dist HTTP server on port 8000 first."""
from pathlib import Path
Path('artifacts/bookmarks').mkdir(parents=True, exist_ok=True)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1440,'height':1000});errors=[]
 page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto('http://localhost:8000/reader.html#volume-1-year-403');page.locator('.compare-row').first.wait_for()
 def open_library():
  if page.viewport_size['width']<=800:
   page.locator('.reader-mobile-tools').click()
   page.locator('.reader-tool-menu [data-reader-tool="notes"]').click()
  else:
   page.locator('.reader-tools [data-reader-tool="notes"]').click()
 def select(selector):
  page.locator(selector).first.scroll_into_view_if_needed()
  page.locator(selector).first.evaluate('''p=>{const w=document.createTreeWalker(p,NodeFilter.SHOW_TEXT);const n=w.nextNode();const r=document.createRange();r.setStart(n,0);r.setEnd(n,Math.min(12,n.length));const s=getSelection();s.removeAllRanges();s.addRange(r);document.dispatchEvent(new Event('selectionchange'));}''')
  page.locator('[data-action="highlight"]').wait_for()
 select('.compare-row .original p')
 page.screenshot(path='artifacts/bookmarks/selection-desktop.png')
 page.locator('[data-action="highlight"]').click();page.locator('button[data-color="green"]').click()
 assert page.locator('.reader-annotation[data-color="green"]').count()>0
 select('.compare-row .modern-text');page.locator('[data-action="note"]').click();page.locator('#annotationThought').fill('读史时记下的一个想法。');page.locator('[data-save]').click()
 assert page.locator('.has-thought').count()>0
 page.locator('.has-thought').first.click();assert page.locator('#annotationThought').input_value()=='读史时记下的一个想法。';page.locator('[data-cancel]').click()
 page.reload();page.locator('.has-thought').first.wait_for();assert page.locator('.reader-annotation[data-color="green"]').count()>0
 select('.compare-row .modern-text');page.locator('[data-action="bookmark"]').click()
 open_library();assert page.locator('.annotation-entry').count()==3
 for kind in ['bookmark','note','highlight']:
  page.locator('[data-library-type="'+kind+'"]').click()
  assert page.locator('.annotation-entry:visible').count()==1
  assert page.locator('.annotation-entry:visible').get_attribute('data-type')==kind
 page.locator('[data-library-type="note"]').click()
 page.locator('.annotation-search').fill('读史时记下')
 assert page.locator('.annotation-entry:visible').count()==1
 page.locator('.annotation-search').fill('完全不存在的摘记')
 assert page.locator('.annotation-empty').is_visible()
 page.locator('.annotation-search').fill('')
 assert page.locator('.annotation-entry:visible').count()==1

 page.screenshot(path='artifacts/bookmarks/notes-desktop.png');page.locator('[data-close]').click()
 page.set_viewport_size({'width':390,'height':844});select('.compare-row .modern-text')
 page.screenshot(path='artifacts/bookmarks/selection-mobile.png');page.locator('[data-action="note"]').click();page.screenshot(path='artifacts/bookmarks/thought-mobile.png')
 assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
 page.locator('[data-cancel]').click();open_library();page.locator('.annotation-entry:visible [data-delete]').first.click();assert page.locator('.annotation-entry').count()==2
 assert not errors,errors
 print('PASS: original/translation selections, color palette, notes/edit/dashed marks, bookmarks, persistence, deletion, desktop/mobile; no browser errors')
 b.close()
