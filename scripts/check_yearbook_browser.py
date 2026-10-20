"""Browser regression checks for yearbook navigation, inline filtering and reader integration."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--base-url',default='http://localhost:3003/tongjian/')
base=parser.parse_args().base_url.rstrip('/')+'/reader.html'
out=Path(__file__).resolve().parents[1]/'artifacts/yearbook-redesign';out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True)
 page=browser.new_page(viewport={'width':1200,'height':800})
 page.set_default_timeout(10000)
 errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
 page.goto(base+'#volume-1');page.locator('.year-card').first.wait_for()
 assert page.locator('.year-card').count()==35
 assert page.locator('.year-card.empty').count()==5
 assert page.locator('#volumeSelect option').count()==294
 assert page.locator('#annualFilterDrawer,#annualPage .intro,#annualPage .volume-banner,#volumeRange,#recordedCount').count()==0
 assert '前403年—前369年' in page.locator('#volumeSelect option[value="1"]').text_content()
 assert '公元958年—公元959年' in page.locator('#volumeSelect option[value="294"]').text_content()
 for width,height in [(1440,1000),(1200,800),(900,844),(601,844),(600,844),(390,844),(360,800),(320,700)]:
  page.set_viewport_size({'width':width,'height':height})
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
  page.evaluate('document.activeElement.blur()')
  if width in [1440,1200,390]:page.screenshot(path=str(out/('desktop-wide.png' if width==1440 else 'desktop.png' if width==1200 else 'mobile.png')))
  stable_selectors=['.annual-toolbar','.annual-search','#annualYearJump','#annualFilterTrigger','#periods','#mobilePeriod','.year-card']
  before={selector:page.locator(selector).first.bounding_box() for selector in stable_selectors}
  scroll=page.evaluate('scrollY')
  page.locator('#annualFilterTrigger').click()
  page.wait_for_function("getComputedStyle(document.querySelector('#annualFilterOptions')).opacity==='1'")
  for selector,rect in before.items():
   after=page.locator(selector).first.bounding_box()
   assert (rect is None)==(after is None),(width,selector,rect,after)
   if rect is not None and width>=960:assert all(abs(rect[k]-after[k])<.1 for k in ['x','y','width','height']),(width,selector,rect,after)
  trigger=page.locator('#annualFilterTrigger').bounding_box();options=page.locator('.annual-filter-options').bounding_box()
  if width>=960:
   assert abs(trigger['y']+trigger['height']/2-options['y']-options['height']/2)<5,(width,trigger,options)
   assert options['x']>=trigger['x']+trigger['width']
  else:
   assert options['y']>=trigger['y']+trigger['height'],(width,'filters should reflow below their trigger')
   assert options['x']>=0 and options['x']+options['width']<=width
  assert page.evaluate('getComputedStyle(document.documentElement).overflow')!='hidden'
  assert page.evaluate('scrollY')==scroll
  assert page.locator('#annualFilterTrigger').get_attribute('aria-expanded')=='true'
  page.keyboard.press('Tab')
  assert page.evaluate("document.querySelector('#annualFilterOptions').contains(document.activeElement)")
  if width in [1200,390]:page.screenshot(path=str(out/('inline-filters-desktop.png' if width==1200 else 'inline-filters-mobile.png')))
  page.keyboard.press('Escape');assert page.locator('#annualFilterOptions').is_hidden()
  assert page.evaluate('document.activeElement.id')=='annualFilterTrigger'
  page.keyboard.press('Tab');assert not page.evaluate("document.querySelector('#annualFilterOptions').contains(document.activeElement)")
  assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width
  print('layout',width,'inline filter y',round(options['y']),'width',round(options['width']),flush=True)
 page.set_viewport_size({'width':390,'height':844})
 page.locator('.annual-site-toggle').click()
 for selector in ['[data-account-link]','.theme-select','#openPeople','#about']:assert page.locator('body>header '+selector).is_visible()
 page.locator('body>header .theme-select').select_option('night');page.keyboard.press('Escape')
 page.locator('#annualFilterTrigger').click()
 page.locator('[data-event-filter="person"]').click()
 assert page.locator('[data-event-filter="person"]').get_attribute('aria-pressed')=='true'
 assert page.locator('#annualFilterTrigger').get_attribute('aria-expanded')=='true'
 page.locator('#recordedOnly').check()
 page.locator('#annualFilterReset').click();assert page.locator('.year-card').count()==35
 page.locator('#recordedOnly').check();assert page.locator('.year-card').count()==30
 assert page.locator('#annualFilterResults').text_content()=='30 年'
 page.locator('#annualFilterReset').click();page.locator('#annualFilterTrigger').click()
 page.locator('.annual-site-toggle').click();page.locator('body>header .theme-select').select_option('light');page.locator('.annual-site-toggle').click()
 page.locator('#mobilePeriod').select_option('安王');assert page.locator('.year-card').count()==26
 page.locator('#search').fill('秦');page.locator('#annualFilterTrigger').click()
 page.locator('[data-event-filter="war"]').click();page.locator('#recordedOnly').check();page.locator('#annualFilterReset').click()
 assert page.locator('#search').input_value()=='秦'
 assert page.locator('#mobilePeriod').input_value()=='安王'
 page.locator('#search').click();assert page.locator('#annualFilterTrigger').get_attribute('aria-expanded')=='true'
 page.locator('#annualFilterTrigger').click()
 page.locator('#search').fill('无匹配的年表词语');assert page.locator('.no-result').is_visible()
 page.locator('#search').fill('');page.locator('#mobilePeriod').select_option('all')
 page.locator('#nextVolume').click();page.wait_for_url('**#volume-2');assert page.locator('#volumeSelect').input_value()=='2'
 page.locator('#prevVolume').click();page.wait_for_url('**#volume-1');assert page.locator('#prevVolume').is_disabled()
 page.locator('#volumeSelect').select_option('294');page.wait_for_url('**#volume-294')
 assert page.locator('#nextVolume').is_disabled()
 assert page.locator('.annual-selected-volume').is_visible()
 assert page.locator('#annualSelectedVolumeYears').text_content()=='公元958年—公元959年'
 page.screenshot(path=str(out/'last-volume-mobile.png'))
 page.locator('#volumeSelect').select_option('35');page.wait_for_url('**#volume-35')
 assert '前2年—公元2年' in page.locator('#volumeSelect option:checked').text_content()
 page.go_back();page.wait_for_function("document.querySelector('#volumeSelect').value==='294'")
 page.go_forward();page.wait_for_function("document.querySelector('#volumeSelect').value==='35'")
 page.locator('#volumeSelect').select_option('1');page.wait_for_url('**#volume-1')
 page.locator('#searchScope').select_option('all');page.locator('#search').fill('朱温')
 page.wait_for_function("document.querySelector('.year-summary')?.textContent.includes('294 / 294')",timeout=60000)
 assert page.locator('.year-card').count()>0
 assert '朱温' in page.locator('#chronicle').inner_text()
 page.screenshot(path=str(out/'full-book-search-mobile.png'))
 page.locator('#searchScope').select_option('current');page.locator('#search').fill('')
 # Original event anchor, reading tools, same-page history and return position.
 page.set_viewport_size({'width':1200,'height':800})
 page.locator('#annualFilterTrigger').click();page.locator('[data-event-filter="all"]').click();page.locator('#annualFilterTrigger').click()
 event=page.locator('.event-button[data-read="403"][data-anchor="8"]')
 event.scroll_into_view_if_needed();before=page.evaluate('scrollY');event.click()
 page.wait_for_url('**#volume-1-year-403-para-8')
 assert page.locator('#para-8').count()==1
 assert page.locator('.compare-row.active #para-8').count()==1
 row=page.locator('.compare-row').first
 original=row.locator('.original-cell').bounding_box();modern=row.locator('.translation-cell').bounding_box()
 assert abs(original['y']-modern['y'])<2 and modern['x']>original['x']
 page.locator('.reader-tools [data-reader-tool="mode"]').click()
 page.locator('[data-reading-mode="modern"]').click()
 assert 'mode-modern' in page.locator('#readerScroll').get_attribute('class')
 page.locator('[data-reading-mode="compare"]').click();page.locator('[data-close-tool]').click()
 page.locator('.reader-tools [data-reader-tool="font"]').click()
 size=int(page.locator('.tool-font-value').text_content());page.locator('#larger').click()
 assert int(page.locator('.tool-font-value').text_content())==size+1
 assert not page.locator('#showNotes').is_visible()
 page.locator('#smaller').click();page.locator('[data-close-tool]').click()
 page.locator('.reader-tools [data-reader-tool="huNotes"]').click()
 assert page.locator('#readerToolPanel h2').text_content()=='胡注与校勘'
 page.locator('#showNotes').check();assert not page.locator('.original.hide-notes').count()
 page.locator('[data-close-tool]').click()
 page.set_viewport_size({'width':390,'height':844})
 original=row.locator('.original-cell').bounding_box();modern=row.locator('.translation-cell').bounding_box()
 assert abs(original['x']-modern['x'])<2 and modern['y']>original['y']
 assert not page.locator('.annual-site-toggle').is_visible()
 assert page.locator('#readerBackdrop').is_visible()
 page.screenshot(path=str(out/'reading-mobile.png'))
 page.set_viewport_size({'width':1200,'height':800});page.locator('#closeReader').click()
 page.wait_for_url('**#volume-1');assert abs(page.evaluate('scrollY')-before)<3
 page.locator('#volumeIntro').click();page.wait_for_url('**#volume-1-intro');assert page.locator('#readerPosition').text_content()=='卷首说明'
 page.locator('#closeReader').click();page.wait_for_url('**#volume-1')
 # Year jump retains BCE/CE semantics and existing adjacent-volume continuation.
 page.locator('#annualYearJump summary').click();page.locator('#jumpYearEra').select_option('ce');page.locator('#jumpYearInput').fill('755');page.locator('#jumpYearForm button').click()
 page.wait_for_url('**#volume-217-year--755');assert page.locator('#annualYearJump').evaluate('(e)=>!e.open')
 page.goto(base+'#volume-200-year--662');page.locator('#readerPosition').filter(has_text='卷 200').wait_for()
 assert page.locator('#nextYear').text_content()=='本年续篇 →'
 page.locator('#nextYear').click();page.wait_for_url('**#volume-201-year--662')
 page.goto(base+'#volume-1-year-402');page.locator('#readerBackdrop:not(.hidden)').wait_for()
 page.locator('.reader-tools [data-reader-tool="catalog"]').click()
 assert page.locator('.tool-volume-slot #volumeSelect').is_visible()
 page.locator('#volumeSelect').select_option('2');page.wait_for_url('**#volume-2')
 assert page.locator('.annual-volume-field #volumeSelect').is_visible()
 page.goto(base.rsplit('reader.html',1)[0]+'year/bce-403/')
 page.locator('#readerBackdrop:not(.hidden)').wait_for()
 assert page.locator('#readerContent #para-8').count()==1
 page.locator('#closeReader').click()
 assert page.locator('#annualFilterTrigger').is_visible()
 page.goto(base+'#volume-1');page.locator('.year-card').first.wait_for()
 page.emulate_media(reduced_motion='reduce');page.locator('#annualFilterTrigger').click()
 page.wait_for_function("document.querySelector('#annualFilterOptions').classList.contains('is-open')")
 page.locator('#annualFilterTrigger').click();assert page.locator('#annualFilterOptions').is_hidden()
 assert not errors,errors
 print('PASS: layouts/inline filters/accessibility, mobile original navigation and themes, filtering/reset, 294-volume navigation and dates, history, full-book search, real anchors, desktop/mobile comparison, modes/font/notes, return position, intro, CE jump and same-year continuation; no JS errors.',flush=True)
 browser.close()
