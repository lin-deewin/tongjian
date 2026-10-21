"""Check vertical annotations inside Hu notes, including legacy offset restoration."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path('artifacts/reader-vertical/note-selection')
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={'width': 1440, 'height': 1000})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(os.environ.get('TONGJIAN_TEST_URL', 'http://localhost:8000') + '/reader.html#volume-1-year-403')
    page.locator('.compare-row').first.wait_for()
    page.evaluate("setReadingMode('vertical')")
    note = page.locator('#traditionalReader .note').filter(has_text='名午，考王之子').first
    note.wait_for()
    page.evaluate('document.fonts.ready')
    original = page.locator('#traditionalReader article').text_content()

    def select_note():
        note.scroll_into_view_if_needed()
        page.wait_for_timeout(200)  # Let the scroll event finish before selecting.
        note.evaluate('''p=>{const r=document.createRange();r.selectNodeContents(p);
            getSelection().removeAllRanges();getSelection().addRange(r)}''')
        page.locator('[data-action=highlight]').wait_for()

    select_note()
    page.screenshot(path=str(out / 'desktop-popup.png'))
    page.locator('[data-action=highlight]').click()
    page.locator('button[data-color=green]').click()
    assert note.locator('[data-color=green]').count() > 0
    select_note()
    page.locator('[data-action=note]').click()
    page.locator('#annotationThought').fill('胡注也可记录想法')
    page.locator('[data-save]').click()
    assert note.locator('.has-thought').count() > 0
    select_note()
    page.locator('[data-action=bookmark]').click()
    assert note.locator('.has-bookmark').count() > 0
    assert page.locator('#traditionalReader article').text_content() == original
    page.evaluate("document.querySelector('#showNotes').dispatchEvent(new Event('change',{bubbles:true}))")
    page.reload()
    note.wait_for()
    for selector in ['[data-color=green]', '.has-thought', '.has-bookmark']:
        assert note.locator(selector).count() > 0
    page.evaluate("setReadingMode('compare');document.querySelector('.annotation-launch').click()")
    page.locator('.annotation-entry[data-type=bookmark] a').first.click()
    page.locator('#traditionalReader').wait_for()
    note.wait_for()
    assert note.locator('.has-bookmark').count() > 0
    page.set_viewport_size({'width': 390, 'height': 844})
    select_note()
    page.screenshot(path=str(out / 'mobile-popup.png'))
    assert page.locator('.annotation-popover').is_visible()
    page.evaluate('''()=>{
        getSelection().removeAllRanges();
        const p=document.querySelector('[data-source-block="2"]');
        const w=document.createTreeWalker(p,NodeFilter.SHOW_TEXT,{
            acceptNode:n=>n.parentElement.closest('.note')?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT});
        let n,text='';while(n=w.nextNode())text+=n.textContent;
        const start=text.indexOf('威烈王');
        const entries=JSON.parse(localStorage.getItem('tongjian-annotations-v2'));
        entries.push({id:'legacy-vertical-test',type:'highlight',color:'pink',volume:1,year:403,text:'威烈王',
            segments:[{target:'traditional-2',anchor:0,source:text,start,end:start+3}]});
        localStorage.setItem('tongjian-annotations-v2',JSON.stringify(entries));
    }''')
    page.reload()
    legacy = page.locator('#traditionalReader [data-annotation-ids~=legacy-vertical-test]')
    legacy.wait_for(state='attached')
    assert legacy.text_content() == '威烈王'
    assert not errors, errors
    print('PASS: Hu note popup, highlight/thought/bookmark, reload, library return, mobile, legacy offsets, unchanged source text')
    browser.close()
