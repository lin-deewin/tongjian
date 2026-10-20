#!/usr/bin/env python3
"""Local Chromium river sample; desktop CPU throttling is not a real phone."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/responsive-20261020'
class Quiet(SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

server=ThreadingHTTPServer(('127.0.0.1',0),partial(Quiet,directory=str(ROOT/'dist')))
Thread(target=server.serve_forever,daemon=True).start()
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline-dir',type=Path,help='Optional saved index.html, river.js and river.css for a before comparison')
args=parser.parse_args()
if args.baseline_dir and not all((args.baseline_dir/name).is_file() for name in ['index.html','river.js','river.css']):
    raise ValueError('Baseline must contain index.html, river.js and river.css')
OUT.mkdir(parents=True,exist_ok=True)
results=[]
try:
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        for variant in (['before','after'] if args.baseline_dir else ['after']):
            ctx=browser.new_context(viewport={'width':390,'height':844},has_touch=True,device_scale_factor=3)
            page=ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            if variant=='before':
                def original(route):
                    name=Path(urlsplit(route.request.url).path).name or 'index.html'
                    path=args.baseline_dir/name
                    if name in ['index.html','river.js','river.css'] and path.is_file():
                        route.fulfill(path=str(path),content_type='text/html' if name.endswith('.html') else 'text/css' if name.endswith('.css') else 'application/javascript')
                    else:route.continue_()
                page.route('**/*',original)
            page.add_init_script('''(() => {
              window.riverSample={};const fetchOriginal=window.fetch;
              window.fetch=async function(...args){
                const response=await fetchOriginal.apply(this,args);
                if(String(args[0]).includes('river-data.json')){
                  const json=response.json.bind(response);
                  response.json=async()=>{
                    const text=await response.text(),start=performance.now(),value=JSON.parse(text);
                    window.riverSample.parseMs=performance.now()-start;window.riverSample.eventBytes=new TextEncoder().encode(text).length;
                    return value;
                  };
                }
                return response;
              };
            })();''')
            cdp=ctx.new_cdp_session(page);cdp.send('Emulation.setCPUThrottlingRate',{'rate':4})
            page.goto(f'http://127.0.0.1:{server.server_port}/');page.locator('.river-event-row').first.wait_for()
            page.locator('.river-stage').scroll_into_view_if_needed()
            sample=page.evaluate('''async()=>{
              const frames=[];let last=performance.now();
              await new Promise(resolve=>{function tick(now){frames.push(now-last);last=now;if(frames.length<90)requestAnimationFrame(tick);else resolve();}requestAnimationFrame(tick);});
              const values=frames.slice(1).sort((a,b)=>a-b),canvas=document.querySelector('canvas');
              return {...window.riverSample,rafCallbackMedianMs:values[Math.floor(values.length*.5)],rafCallbackP95Ms:values[Math.floor(values.length*.95)],canvasPixels:canvas.width*canvas.height,cssCanvasHeight:canvas.clientHeight};
            }''')
            assert not errors,errors
            results.append({'variant':variant,'cpuThrottle':4,'viewport':[390,844],'hasTouch':True,'deviceScaleFactor':3,**sample})
            ctx.close()
        browser.close()
    (OUT/'performance.json').write_text(json.dumps({'scope':'Local desktop Chromium at 4x CPU slowdown; rAF callback intervals measure main-thread availability, not rendered animation FPS; no mobile hardware or public-network performance claim','samples':results},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(results,ensure_ascii=False,indent=2))
finally:server.shutdown()
