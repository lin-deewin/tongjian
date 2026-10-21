"""Bracket note typography must not hide previously visible source text."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
Path('artifacts/reader-vertical').mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 b=p.chromium.launch(headless=True);page=b.new_page(viewport={'width':1440,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(os.environ.get('TONGJIAN_TEST_URL','http://localhost:8000')+'/reader.html#volume-1-year-403');page.locator('.compare-row').first.wait_for();page.evaluate("setReadingMode('vertical')")
 note=page.locator('#traditionalReader .bracket-note').filter(has_text='章：十二行本莫下有敢字').first;note.wait_for()
 page.evaluate('document.fonts.ready')
 note.evaluate("n=>n.id='bracket-font-check'")
 client=page.context.new_cdp_session(page);client.send('DOM.enable');client.send('CSS.enable')
 root=client.send('DOM.getDocument')['root']['nodeId']
 node=client.send('DOM.querySelector',{'nodeId':root,'selector':'#bracket-font-check'})['nodeId']
 fonts=client.send('CSS.getPlatformFontsForNode',{'nodeId':node})['fonts']
 assert any(f['isCustomFont'] and 'UKai' in f['postScriptName'] for f in fonts),fonts
 print('Rendered bracket font:',fonts)
 for width in [1440,390]:
  page.set_viewport_size({'width':width,'height':1000})
  for enabled in [False,True,False]:
   page.evaluate("enabled=>{document.querySelector('#showNotes').checked=enabled;document.querySelector('#showNotes').dispatchEvent(new Event('change'));}",enabled)
   assert note.is_visible(),(width,enabled)
   assert note.text_content()=='【章：十二行本莫下有敢字；乙十一行本同；孔本同。】'
   assert note.evaluate("n=>parseFloat(getComputedStyle(n).fontSize)")==page.evaluate("readingSize * 0.7")
  note.scroll_into_view_if_needed();page.screenshot(path=f'artifacts/reader-vertical/brackets-visible-{width}.png')
 assert not errors,errors
 print('PASS: brackets and full text remain visible with notes off/on/off, desktop/mobile; relative note sizing retained; no browser errors')
 b.close()
