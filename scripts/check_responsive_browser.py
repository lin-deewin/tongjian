#!/usr/bin/env python3
"""Responsive browser regression: horizontal labels, usable columns and gestures.

Runs an isolated local server; never contacts or publishes to production.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/responsive-20261020'
SIZES = [(320,568),(360,800),(375,667),(390,844),(393,852),(412,915),
         (430,932),(440,956),(599,844),(600,844),(601,844),(768,1024),
         (799,844),(800,844),(801,844),(844,390),(959,900),(960,900),
         (961,900),(1280,900),(1440,1000)]

class Quiet(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

# Range line boxes detect accidental wrapping; nowrap alone cannot prove the
# action still fits its parent or its neighbours.
LABEL_CHECK = r'''selectors => {
 const failures=[];
 for(const selector of selectors)for(const el of document.querySelectorAll(selector)){
  if(!el.getClientRects().length)continue;
  const rect=el.getBoundingClientRect();
  if(rect.right>innerWidth+1||rect.left< -1)failures.push([selector,'out of viewport',rect.toJSON()]);
  const walker=document.createTreeWalker(el,NodeFilter.SHOW_TEXT);let node;const tops=[];
  while(node=walker.nextNode()){
   if(!node.textContent.trim()||!node.parentElement.getClientRects().length||getComputedStyle(node.parentElement).position==='absolute')continue;
   const range=document.createRange();range.selectNodeContents(node);
   for(const box of range.getClientRects())if(box.width>0)tops.push(box.top);
  }
  if(tops.length&&Math.max(...tops)-Math.min(...tops)>12)failures.push([selector,'wrapped short label',tops]);
  if(el.scrollWidth>el.clientWidth+2)failures.push([selector,'clipped label',el.scrollWidth,el.clientWidth]);
 }
 return failures;
}'''

def check_page(page, name, sizes, records):
    print('checking',name,flush=True)
    for w,h in sizes:
        page.set_viewport_size({'width':w,'height':h})
        page.wait_for_timeout(70)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'),(name,w,'overflow')
        selectors = ['#closeReader','#prevYear','#nextYear','.reader-mobile-tools'] if name=='reading' else ['#annualFilterTrigger','#annualYearJump>summary','#prevVolume','#nextVolume'] if name=='yearbook' else ['.river-prev','.river-next','.river-era-label'] if name=='river' else ['header nav a']
        failures=page.evaluate(LABEL_CHECK,selectors)
        assert not failures,(name,w,failures)
        if name=='yearbook':
            width=page.locator('.event-title').first.evaluate('e=>e.clientWidth/parseFloat(getComputedStyle(e).fontSize)')
            assert width>=12,(name,w,'narrow title',width)
            if w<600:
                date=page.locator('.year-date').first.bounding_box();events=page.locator('.year-events').first.bounding_box()
                assert date['y']+date['height']<=events['y']+1,(w,'year sidebar not stacked')
        if name=='reading':
            columns=page.locator('.compare-row').first.evaluate("e=>getComputedStyle(e).gridTemplateColumns.split(' ').length")
            assert columns==(1 if w<960 else 2),(w,columns)
        if name=='river':
            assert page.locator('.river-stage').bounding_box()['height']>0
            assert page.locator('.river-event-panel').is_visible()
        records.append({'page':name,'width':w,'height':h,'passed':True})
        if w in [320,390,844,1440]:
            if name=='river':page.locator('.river-stage').scroll_into_view_if_needed()
            page.screenshot(path=str(OUT/f'{name}-{w}.png'))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser',choices=['chromium','webkit','firefox'],default='chromium')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT/'dist')))
    Thread(target=server.serve_forever,daemon=True).start()
    base=f'http://127.0.0.1:{server.server_port}/'
    records=[];errors=[]
    try:
        with sync_playwright() as p:
            browser=getattr(p,args.browser).launch(headless=True)
            ctx=browser.new_context(viewport={'width':390,'height':844},has_touch=True,device_scale_factor=3)
            page=ctx.new_page();page.set_default_timeout(10000);page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto(base+'reader.html#volume-1');page.locator('.year-card').first.wait_for()
            check_page(page,'yearbook',SIZES,records)
            page.set_viewport_size({'width':320,'height':568})
            page.locator('#annualFilterTrigger').click()
            for selector in ['[data-event-filter="war"]','[data-event-filter="reform"]','#recordedOnly']:
                page.locator(selector).click()
            page.locator('#annualFilterReset').click();page.keyboard.press('Escape')
            catalog=json.loads((ROOT/'dist/catalog.json').read_text())['volumes']
            longest=max(catalog,key=lambda item:len(item.get('title','')))
            page.locator('#volumeSelect').select_option(str(longest['volume']))
            page.wait_for_function('(v)=>typeof book!=="undefined"&&book?.volume===v',arg=longest['volume'])
            page.wait_for_timeout(100)
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
            assert page.locator('.annual-selected-volume').evaluate('e=>!e.getClientRects().length||e.scrollHeight<=e.clientHeight+1')
            page.locator('#volumeSelect').select_option('1')
            page.wait_for_function('typeof book!=="undefined"&&book?.volume===1')
            page.locator('#annualYearJump>summary').click()
            assert page.locator('.annual-jump-popover').bounding_box()['x']>=0
            page.locator('#jumpYearInput').fill('403');page.locator('#jumpYearForm button').click()
            page.locator('.compare-row').first.wait_for()
            check_page(page,'reading',SIZES,records)
            # Large-font two-column content must change layout, not squash text.
            page.set_viewport_size({'width':960,'height':900})
            page.locator('.reader-tools [data-reader-tool="font"]').click()
            for _ in range(9):page.locator('#larger').click()
            page.keyboard.press('Escape');page.wait_for_timeout(150)
            assert page.locator('.compare-row').first.evaluate("e=>getComputedStyle(e).gridTemplateColumns.split(' ').length")==1
            # Resize and controls preserve a visible paragraph in a long year.
            page.goto(base+'reader.html#volume-1-year-403')
            page.wait_for_function("typeof selected!=='undefined'&&selected===403&&document.querySelector('#para-8')&&document.querySelector('.reader-head-year')?.textContent==='前403年'")
            page.wait_for_timeout(150)
            anchor=page.locator('#para-8');anchor.scroll_into_view_if_needed()
            page.evaluate("window.scrollBy(0,-180)");page.wait_for_timeout(150)
            before=anchor.bounding_box()['y']
            page.locator('.reader-tools [data-reader-tool="font"]').click();page.locator('#smaller').click();page.keyboard.press('Escape');page.wait_for_timeout(150)
            assert abs(anchor.bounding_box()['y']-before)<80,('font anchor drift',before,anchor.bounding_box())
            page.evaluate('''() => {
              const top=document.querySelector('.reader-head').getBoundingClientRect().bottom+12;
              const block=[...document.querySelectorAll('.original p,.modern-text')].find(p=>p.getClientRects().length&&p.getBoundingClientRect().bottom>top);
              block.dataset.checkAnchor='true';
            }''')
            page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(200)
            visible=page.locator('[data-check-anchor]').bounding_box()
            assert visible['y']<844 and visible['y']+visible['height']>90,('rotation lost visible paragraph',visible)
            page.locator('.reader-mobile-tools').click();page.locator('.reader-tool-menu [data-reader-tool="mode"]').click()
            page.locator('[data-reading-mode="modern"]').click();page.keyboard.press('Escape')
            assert page.locator('.original-cell').first.is_hidden()
            page.locator('.reader-mobile-tools').click();page.locator('.reader-tool-menu [data-reader-tool="huNotes"]').click()
            assert page.locator('#showNotes').is_disabled();page.keyboard.press('Escape')
            page.locator('.reader-mobile-tools').click();page.locator('.reader-tool-menu [data-reader-tool="mode"]').click();page.locator('[data-reading-mode="compare"]').click();page.keyboard.press('Escape')
            # Deep canonical reader shares the same UI, including final event navigation.
            page.goto(base+'year/bce-403/?volume=1&para=30');page.locator('#para-30').wait_for()
            assert page.locator('#closeReader').is_visible()
            page.locator('#nextYear').click();page.wait_for_timeout(100)
            assert page.locator('#readerContent').inner_text()
            # Test the home page with no saved reading preferences.
            page.goto(base);page.locator('.river-event-row').first.wait_for()
            check_page(page,'river',SIZES,records)
            page.set_viewport_size({'width':390,'height':844})
            # The river was restored at the user's request; keep its original
            # controls and direct event links, rather than the rejected redesign.
            previous=page.locator('.river-chart-year').inner_text()
            page.locator('.river-next').click()
            assert page.locator('.river-chart-year').inner_text()!=previous
            page.locator('.river-prev').click()
            assert page.locator('.river-chart-year').inner_text()==previous
            page.locator('.river-zoom').select_option('1362')
            page.locator('.river-zoom').select_option('170')
            page.locator('.river-era').select_option(index=0)
            page.locator('.river-event-row').first.wait_for()
            assert page.locator('.river-expand,.river-more,.river-selection').count()==0
            state=page.evaluate('sessionStorage.getItem("tongjian-river")')
            page.locator('.river-event-row').first.click()
            page.locator('#readerBackdrop:not(.hidden)').wait_for()
            page.go_back();page.locator('.river-position').wait_for()
            assert page.evaluate('sessionStorage.getItem("tongjian-river")')==state
            # Shared static reading, profile and wide article-table surfaces.
            for path in ['volume/1/','people/yue-yi/','history/xiao-he-guanzhong/','truth.html','research/01-judging-talent.html']:
                page.goto(base+path);check_page(page,'static-'+path.replace('/','-'),[(320,568),(390,844),(844,390),(1440,1000)],records)
            page.goto(base+'reader.html#person-yue-yi');page.locator('.person-identity').wait_for()
            check_page(page,'person-profile',[(320,568),(390,844),(844,390),(1440,1000)],records)
            # Fine-pointer desktop uses the same content with parallel columns.
            desk=browser.new_context(viewport={'width':1440,'height':1000},has_touch=False)
            desktop=desk.new_page();desktop.on('pageerror',lambda e:errors.append(str(e)))
            desktop.goto(base+'reader.html#volume-1-year-403');desktop.locator('.compare-row').first.wait_for()
            check_page(desktop,'reading',[(1280,900),(1440,1000)],records)
            desktop.screenshot(path=str(OUT/f'desktop-mouse-{args.browser}.png'))
            desk.close()
            assert not errors,errors
            browser.close()
        report={'browser':args.browser,'engineSimulation':True,'physicalDevicesTested':False,'checks':records,'pageErrors':errors,'status':'passed'}
        (OUT/f'browser-{args.browser}.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
        print(f'PASS {args.browser}: {len(records)} layouts; horizontal labels, readable columns, font/resize anchors, controls, restored river controls/navigation; no page errors.')
    finally:
        server.shutdown()

if __name__=='__main__':
    main()
