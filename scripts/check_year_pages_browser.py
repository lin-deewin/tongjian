import threading,json
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from functools import partial
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
class Quiet(SimpleHTTPRequestHandler):
 def log_message(self,*args): pass
server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(root/'dist')))
threading.Thread(target=server.serve_forever,daemon=True).start()
base=f'http://127.0.0.1:{server.server_port}'
catalog=json.loads((root/'dist/catalog.json').read_text())
cross=next(int(y) for y,vs in catalog['yearVolumes'].items() if len(vs)>1)
paths=['/year/','/year/bce-403/','/year/ce-1/','/year/ce-959/',f'/year/{"bce" if cross>0 else "ce"}-{abs(cross)}/']
(root/'artifacts/seo/year-pages').mkdir(parents=True,exist_ok=True)
results=[]
with sync_playwright() as p:
 b=p.chromium.launch(headless=True)
 for width in [1440,390]:
  ctx=b.new_context(java_script_enabled=False,viewport={'width':width,'height':900})
  page=ctx.new_page()
  for path in paths:
   response=page.goto(base+path)
   assert response.status==200
   assert page.locator('h1:visible').is_visible()
   assert page.locator('main:visible').inner_text().strip()
   assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),path
   if path!='/year/':
    assert page.locator('.source-original').count()>0
   results.append({'path':path,'width':width,'noJavaScript':True,'status':'passed'})
  page.goto(base+'/year/bce-403/')
  page.screenshot(path=str(root/f'artifacts/seo/year-pages/nojs-{width}.png'),full_page=False)
  ctx.close()
 ctx=b.new_context();page=ctx.new_page()
 page.goto(base+'/year/bce-403/')
 page.locator('#readerBackdrop:not(.hidden)').wait_for()
 page.locator('[data-reader-tool="mode"]').click()
 page.locator('[data-tool-section="mode"] [data-reading-mode="original"]').click()
 assert 'mode-original' in page.locator('#readerScroll').get_attribute('class')
 page.goto(base+'/reader.html#volume-1-year-403')
 link=page.get_by_role('link',name='本年独立阅读页 ↗')
 link.wait_for();link.click()
 assert '/year/bce-403/' in page.url
 page.locator('#readerBackdrop:not(.hidden)').wait_for()
 assert page.locator('#readerContent #para-0').count()==1
 results.append({'readerToYear':'passed','readingControls':'passed'})
 b.close()
server.shutdown()
(root/'artifacts/seo/year-pages/browser.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(results,ensure_ascii=False))
