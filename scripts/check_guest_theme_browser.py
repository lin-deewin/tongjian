"""Theme choices survive navigation but do not leak to a new guest tab."""
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser=p.chromium.launch(headless=True)
    context=browser.new_context()
    page=context.new_page()
    root='http://localhost:8011'
    page.goto(root+'/reader.html#volume-1-year-403')
    page.evaluate("localStorage.setItem('tongjian-theme','night')")
    page.reload()
    page.locator('.reader-tools').wait_for()
    assert page.locator('html').get_attribute('data-theme')=='light'
    page.locator('[data-reader-tool="theme"]').click()
    page.locator('[data-choose-theme="gold"]').click()
    assert page.locator('html').get_attribute('data-theme')=='gold'
    page.reload()
    page.locator('.reader-tools').wait_for()
    assert page.locator('html').get_attribute('data-theme')=='gold'
    page.goto(root+'/year/bce-403/')
    assert page.locator('html').get_attribute('data-theme')=='gold'
    other=context.new_page()
    other.goto(root+'/reader.html#volume-1-year-403')
    other.locator('.reader-tools').wait_for()
    assert other.locator('html').get_attribute('data-theme')=='light'
    other.evaluate("localStorage.setItem('tongjian-theme','night')")
    page.wait_for_timeout(100)
    assert page.locator('html').get_attribute('data-theme')=='gold'
    page.close()
    fresh=context.new_page()
    fresh.goto(root+'/year/bce-403/')
    assert fresh.locator('html').get_attribute('data-theme')=='light'
    browser.close()
print('PASS: legacy theme ignored; refresh/navigation preserved; new guest tab defaults to light; cross-tab localStorage ignored.')
