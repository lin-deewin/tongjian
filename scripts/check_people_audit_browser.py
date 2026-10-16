"""Browser regressions for audited profiles; not certification of all historical judgments."""
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import shutil
from threading import Thread

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts/people-audit'
OUT.mkdir(parents=True, exist_ok=True)
profiles = json.loads((ROOT / 'scripts/people/reviewed.json').read_text())['people']
by_name = {p['name']: p for p in profiles}


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(ROOT / 'dist')))
Thread(target=server.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{server.server_port}/reader.html'
errors = []
try:
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(executable_path=shutil.which('google-chrome-stable'), headless=True, args=['--no-sandbox'])
        page = browser.new_page(viewport={'width': 1440, 'height': 1000})
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(url + '#people')
        page.wait_for_selector('#peopleSearch')
        assert page.locator('#peopleDirectory .person-card').count() == len(profiles)
        # Request every published JSON from the same browser origin, with bounded concurrency.
        totals = page.evaluate('''async () => {
            const index = await (await fetch('people-index.json')).json();
            let events = 0;
            for (let start = 0; start < index.people.length; start += 16) {
                const batch = await Promise.all(index.people.slice(start, start + 16).map(async p => {
                    const response = await fetch('people/' + p.id + '.json');
                    if (!response.ok) throw Error(p.id + ': ' + response.status);
                    const data = await response.json();
                    if (data.id !== p.id || data.name !== p.name) throw Error('Profile identity mismatch');
                    return data.events.length;
                }));
                events += batch.reduce((a, b) => a + b, 0);
            }
            return {profiles: index.people.length, events};
        }''')
        assert totals['events'] == sum(len(p['events']) for p in profiles)
        samples = ['萧何', '张衡', '张衡（隋）', '刘弘', '刘弘基', '刘知远', '汉顺帝', '王衍（西晋）', '王褒（梁北周）']
        for name in samples:
            person = by_name[name]
            page.goto(url + '#person-' + person['id'])
            page.wait_for_function('(name) => document.title.startsWith(name)', arg=name)
            page.select_option('#peopleScope', 'all')
            assert page.locator('.person-timeline > li').count() == len(person['events']), name
            page.select_option('#peopleCategory', '去世')
            assert page.locator('.person-timeline > li').count() == sum(e['category'] == '去世' for e in person['events']), name
            page.select_option('#peopleCategory', 'all')
        page.get_by_role('heading', name='萧绎任王褒为吏部尚书', exact=True).locator('a').click()
        page.wait_for_selector('.compare-row.active #para-0')
        assert page.url.endswith('#volume-164-year--552-para-0')
        assert '以南平内史王褒为吏部尚书' in page.locator('#para-0').inner_text()
        page.locator('#closeReader').click()
        page.wait_for_selector('#peopleScope')
        assert page.title().startswith('王褒（梁北周）')
        page.evaluate('window.scrollTo(0, 0)')
        page.screenshot(path=str(OUT / 'desktop.png'))
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        page.screenshot(path=str(OUT / 'mobile.png'))
        assert not errors, errors
        browser.close()
finally:
    server.shutdown()
(OUT / 'validation.json').write_text(json.dumps(dict(status='PASS', assetChecks=totals, renderedProfiles=samples, pageErrors=errors, sourceReturn='volume164:-552:0', phoneWidth=390), ensure_ascii=False, indent=2) + '\n')
print(f'PASS: all {totals["profiles"]} profile assets, {len(samples)} rendered profiles, filters, corrected source/return and mobile layout')
