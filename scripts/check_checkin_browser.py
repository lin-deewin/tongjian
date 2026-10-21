"""Year check-ins in the real reader; account APIs exercised separately by Django."""
from pathlib import Path
from playwright.sync_api import sync_playwright

Path('artifacts/checkin').mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context(viewport={'width':1440,'height':1000})
    state={'user':None,'fail':False,'entries':{'a':[],'b':[]},'days':{'a':[],'b':[]}}
    def api(route):
        path=route.request.url.split('/api/v1/')[1];user=state['user']
        if path=='session/':
            route.fulfill(json={'authenticated':bool(user),'user_id':user,'csrf_token':'test'});return
        if not user:route.fulfill(status=401,json={});return
        if state['fail']:route.fulfill(status=503,json={});return
        if path=='me/reading-days/':
            if route.request.method=='POST':state['days'][user]=sorted(set(state['days'][user]+route.request.post_data_json['days']))
            route.fulfill(json={'user_id':user,'days':state['days'][user]});return
        if path=='me/reading-checkins/':
            if route.request.method=='POST':
                data=route.request.post_data_json
                assert data['user_id']==user
                records={e['id']:e for e in state['entries'][user]}
                for e in data['entries']:records.setdefault(e['id'],e)
                state['entries'][user]=list(records.values())
            scores=[len({e['year'] for e in items}) for items in state['entries'].values() if items]
            score=len({e['year'] for e in state['entries'][user]})
            route.fulfill(json={'user_id':user,'entries':state['entries'][user],'unique_years':score,'rank':1+sum(s>score for s in scores) if score else None,'participants':len(scores)});return
        route.fulfill(status=404,json={})
    context.route('**/api/v1/**',api)
    page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
    url='http://localhost:8011/reader.html#volume-1-year-403'
    page.goto(url)
    button=page.locator('.reading-checkin>button').first
    page.locator('#readerContent .reader-inner').wait_for()
    assert not button.is_visible()
    page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)')
    page.mouse.wheel(0,300)
    button.wait_for(state='visible')
    assert page.evaluate("localStorage.getItem('tongjian-reading-checkins-v2')")==None
    page.evaluate("localStorage.setItem('tongjian-reading-days-v1',JSON.stringify(['2026-01-01']))")
    page.evaluate('window.scrollTo(0,0)')
    page.wait_for_function("document.querySelector('.reading-checkin').hidden")
    page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)');page.mouse.wheel(0,300)
    button.wait_for(state='visible')
    page.screenshot(animations='disabled',path='artifacts/checkin-redesign/invitation-desktop.png')
    button.click()
    page.locator('#nextYear').click()
    page.wait_for_url('**year-402')
    page.locator('#prevYear').click()
    page.wait_for_url('**year-403')
    page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)');page.mouse.wheel(0,300)
    button.wait_for(state='visible');button.click()
    assert page.locator('[data-stat=visits]').inner_text()=='2'
    assert page.locator('[data-stat=years]').inner_text()=='1'
    assert button.is_enabled()
    assert '重读' in page.locator('.checkin-message').inner_text()
    page.locator('#nextYear').click()
    page.wait_for_url('**year-402')
    page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)')
    page.mouse.wheel(0,300)
    button.wait_for(state='visible')
    button.click()
    assert page.locator('[data-stat=visits]').inner_text()=='3'
    assert page.locator('[data-stat=years]').inner_text()=='2'
    page.reload();page.locator('#readerContent .reader-inner').wait_for();page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)');page.mouse.wheel(0,300);button.wait_for(state='visible')
    assert page.locator('[data-stat=visits]').inner_text()=='3'
    state['user']='a';page.evaluate("window.dispatchEvent(new Event('tongjian-session'))")
    page.wait_for_function("document.querySelector('.checkin-ranking').textContent.includes('第 1 名')")
    assert len(state['entries']['a'])==3
    assert state['days']['a']==['2026-01-01']
    assert page.evaluate("JSON.parse(localStorage.getItem('tongjian-reading-checkins-v2')).length")==0
    state['fail']=True;button.click()
    page.wait_for_function("document.querySelector('.reading-checkin small').textContent.includes('同步后')")
    assert '第 1 名' not in page.locator('.checkin-ranking').inner_text()
    state['fail']=False;page.get_by_role('button',name='重试同步',exact=True).click()
    page.wait_for_function("document.querySelector('.checkin-ranking').textContent.includes('第 1 名')")
    assert len(state['entries']['a'])==4
    page.evaluate('localStorage.clear()');page.reload();page.locator('#readerContent .reader-inner').wait_for();page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)');page.mouse.wheel(0,300);button.wait_for(state='visible')
    page.wait_for_function("document.querySelector('[data-stat=visits]').textContent==='4'")
    page.screenshot(animations='disabled',path='artifacts/checkin/year-desktop.png',full_page=True)
    page.set_viewport_size({'width':390,'height':844});page.wait_for_timeout(350);page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)');page.mouse.wheel(0,300);button.wait_for(state='visible')
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
    page.screenshot(animations='disabled',path='artifacts/checkin-redesign/invitation-mobile.png')
    button.click()
    page.wait_for_function("document.querySelector('.reading-checkin').classList.contains('checkin-complete')")
    page.wait_for_function("document.querySelector('.checkin-ranking').textContent.includes('第 1 名')")
    page.screenshot(animations='disabled',path='artifacts/checkin-redesign/success-mobile.png')
    card=page.locator('.reading-checkin').bounding_box()
    nav=page.locator('.reader-nav').bounding_box()
    assert card['y']+card['height'] <= nav['y']
    assert card['x'] >= 0 and card['x']+card['width'] <= 390
    page.evaluate("document.documentElement.dataset.theme='night'")
    page.screenshot(animations='disabled',path='artifacts/checkin-redesign/success-mobile-night.png')
    page.evaluate("document.documentElement.dataset.theme='light'")
    button.click()
    page.wait_for_url('**year-401')
    assert len(state['entries']['a'])==5
    assert not page.locator('.reading-checkin').is_visible()
    page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)');page.mouse.wheel(0,300)
    button.wait_for(state='visible')
    page.get_by_role('button',name='收起打卡提示').click()
    assert not page.locator('.reading-checkin').is_visible()
    state['user']=None;page.evaluate("window.dispatchEvent(new Event('tongjian-session'))")
    page.wait_for_function("document.querySelector('.checkin-ranking').textContent.includes('登录后')")
    assert page.locator('[data-stat=visits]').inner_text()=='0'
    state['user']='b';page.evaluate("window.dispatchEvent(new Event('tongjian-session'))")
    page.wait_for_function("document.querySelector('.checkin-ranking').textContent.includes('旅程')")
    assert page.locator('[data-stat=visits]').inner_text()=='0'
    page.goto('http://localhost:8011/reader.html#volume-1-year-395')
    page.locator('.empty-reading').wait_for()
    page.evaluate('window.scrollTo(0,document.documentElement.scrollHeight)');page.mouse.wheel(0,300)
    page.wait_for_timeout(200)
    assert not page.locator('.reading-checkin').is_visible()
    assert button.is_disabled()
    # Even a programmatic click must not save an empty year.
    page.evaluate("document.querySelector('.checkin-primary').dispatchEvent(new MouseEvent('click'))")
    assert page.evaluate("JSON.parse(localStorage.getItem('tongjian-reading-checkins-v2:account:b')||'[]').length")==0
    page.goto('http://localhost:8011/reader.html#volume-1-intro')
    assert not page.locator('.reading-checkin').is_visible()
    assert not errors,errors
    browser.close()
print('PASS: repeat/year counts, guest/account merge, legacy days, failure/retry, restore, account isolation, intro, mobile.')
