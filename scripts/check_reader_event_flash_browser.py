"""Verify transient event-anchor borders in the real reader, including repeat navigation."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-url',default='http://localhost:3003/tongjian/')
base=parser.parse_args().base_url.rstrip('/')+'/'
out=Path(__file__).resolve().parents[1]/'artifacts/reader-event-flash'
out.mkdir(parents=True,exist_ok=True)

with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 page=browser.new_page(viewport={'width':1200,'height':800})
 page.set_default_timeout(7000)
 errors=[]
 page.on('pageerror',lambda error:errors.append(str(error)))
 page.add_init_script("""window.flashEvents=[];
 for(const type of ['animationstart','animationiteration','animationend']){
  document.addEventListener(type,e=>{
   if(e.animationName.startsWith('reader-target-border-'))window.flashEvents.push({type,name:e.animationName,pseudo:e.pseudoElement});
  });
 }""")
 for width,height,anchor in [(1200,800,0),(390,844,1)]:
  page.set_viewport_size({'width':width,'height':height})
  page.goto(base+'reader.html#volume-2')
  event=page.locator(f'.event-button[data-read="368"][data-anchor="{anchor}"]')
  event.wait_for();page.evaluate('window.flashEvents=[]');event.click()
  page.wait_for_url(f'**#volume-2-year-368-para-{anchor}')
  row=page.locator(f'#para-{anchor}').locator('xpath=ancestor::*[contains(concat(" ",normalize-space(@class)," ")," compare-row ")]')
  page.wait_for_function('window.flashEvents.some(e=>e.type==="animationstart")')
  frame=row.evaluate("""e=>{const s=getComputedStyle(e,'::after');return {
   count:s.animationIterationCount,duration:s.animationDuration,color:s.borderTopColor,
   widths:[s.borderTopWidth,s.borderRightWidth,s.borderBottomWidth,s.borderLeftWidth],
   inset:[s.top,s.right,s.bottom,s.left],pointer:s.pointerEvents
  }}""")
  assert frame['count']=='1' and frame['color']=='rgb(229, 138, 50)' and frame['duration']=='0.8s',frame
  assert frame['widths']==['2px']*4 and frame['inset']==['0px']*4,frame
  assert frame['pointer']=='none'
  target=page.locator(f'#para-{anchor}')
  assert abs(target.bounding_box()['y']-target.evaluate('e=>parseFloat(getComputedStyle(e).scrollMarginTop)'))<1
  before=row.bounding_box()
  page.wait_for_function("getComputedStyle(document.querySelector('.event-target-flash'),'::after').opacity==='1'")
  page.screenshot(path=str(out/('desktop.png' if width==1200 else 'mobile.png')))
  page.wait_for_function('window.flashEvents.some(e=>e.type==="animationend")')
  assert row.evaluate('e=>!e.classList.contains("event-target-flash")&&!e.classList.contains("active")')
  assert row.evaluate("e=>getComputedStyle(e,'::after').content")=='none'
  after=row.bounding_box()
  assert all(abs(before[k]-after[k])<.1 for k in ['x','y','width','height']),(before,after)
  events=page.evaluate('window.flashEvents')
  assert [e['type'] for e in events]==['animationstart','animationend'],events
  assert all(e['pseudo']=='::after' for e in events),events
  page.screenshot(path=str(out/('desktop-after.png' if width==1200 else 'mobile-after.png')))
  # Re-entering the same event must start a fresh single-pulse effect.
  page.locator('#closeReader').click();page.wait_for_url('**#volume-2')
  page.evaluate('window.flashEvents=[]')
  page.locator(f'.event-button[data-read="368"][data-anchor="{anchor}"]').click()
  page.wait_for_function('window.flashEvents.some(e=>e.type==="animationend")')
  assert len(page.evaluate('window.flashEvents.filter(e=>e.type==="animationiteration")'))==0
  assert page.locator('.event-target-flash').count()==0
 # The final event must align below the sticky header even at the document end.
 for width,height in [(1200,800),(390,844)]:
  page.set_viewport_size({'width':width,'height':height})
  page.goto(base+'reader.html#volume-1')
  page.locator('.event-button[data-read="403"][data-anchor="30"]').click()
  page.wait_for_function("document.querySelector('#para-30')?.getBoundingClientRect().top<150")
  target=page.locator('#para-30')
  assert '燕愍公' in target.inner_text()
  top=target.bounding_box()['y']
  margin=target.evaluate('e=>parseFloat(getComputedStyle(e).scrollMarginTop)')
  assert abs(top-margin)<1,(width,top,margin)
  assert page.locator('#readerContent').evaluate("e=>parseFloat(e.style.getPropertyValue('--reader-anchor-tail'))")>0
  page.wait_for_function("!document.querySelector('.event-target-flash')")
  assert abs(target.bounding_box()['y']-top)<1
  page.locator('#closeReader').click();page.locator('#volumeIntro').click()
  assert page.locator('#readerContent').evaluate("e=>e.style.getPropertyValue('--reader-anchor-tail')")=='0px'
 page.goto(base+'reader.html#volume-1-year-403-para-30')
 page.wait_for_function("document.querySelector('#para-30')?.getBoundingClientRect().top<150")
 margin=page.locator('#para-30').evaluate('e=>parseFloat(getComputedStyle(e).scrollMarginTop)')
 assert abs(page.locator('#para-30').bounding_box()['y']-margin)<1
 assert page.locator('#para-30').bounding_box()['y']>=page.locator('.reader-head').bounding_box()['height']
 # Deep links and reduced-motion preferences share the same cleanup lifecycle.
 page.emulate_media(reduced_motion='reduce')
 page.goto(base+'year/bce-368/#volume-2-year-368-para-0')
 page.wait_for_function('window.flashEvents.some(e=>e.type==="animationstart")')
 assert page.locator('.event-target-flash').evaluate("e=>getComputedStyle(e,'::after').animationName")=='reader-target-border-still'
 page.wait_for_function('window.flashEvents.some(e=>e.type==="animationend")')
 assert not page.evaluate('window.flashEvents.some(e=>e.type==="animationiteration")')
 assert page.locator('.event-target-flash').count()==0
 # Ordinary year navigation does not flash or leave an active target behind.
 page.locator('#nextYear').click()
 assert page.locator('.event-target-flash').count()==0
 assert not errors,errors
 browser.close()
print('PASS: event anchors flash all four borders once in orange, clear without layout changes, replay on re-entry, and support mobile, annual deep links and reduced motion; no JS errors.')
