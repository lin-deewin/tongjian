// Logic and generated-markup checks in a small DOM harness; not browser visual QA.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const path=require('path');const root=path.resolve(__dirname,'../dist');
const elements=new Map(),listeners=new Map();
function element(key){if(!elements.has(key))elements.set(key,{innerHTML:'',textContent:'',value:'',checked:false,disabled:false,style:{setProperty(){}},classList:{set:new Set(),add(x){this.set.add(x)},remove(x){this.set.delete(x)},contains(x){return this.set.has(x)},toggle(x,v){if(v===undefined)v=!this.set.has(x);if(v)this.set.add(x);else this.set.delete(x)}},focus(){},getBoundingClientRect(){return {top:0}},closest(){return element('label')},scrollIntoView(){}});return elements.get(key);}
element('#searchScope').value='current';
element('.theme-select').options=[{value:'light'},{value:'dark'},{value:'warm'}];
const location={hash:'',pathname:'/',search:''};const history={pushState(_a,_b,url){location.hash=url.includes('#')?'#'+url.split('#')[1]:''}};
const context=vm.createContext({console,setTimeout,clearTimeout,location,history,document:{querySelector:element,querySelectorAll:()=>[],addEventListener(type,handler){listeners.set(type,handler)},body:element('body'),documentElement:{dataset:{},style:{setProperty(){}},scrollHeight:1000},activeElement:element('active')},window:{scrollY:0,innerHeight:700,scrollTo(){},addEventListener(){}},requestAnimationFrame:f=>f(),fetch:async name=>({ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,name),'utf8'))})});
vm.runInContext(fs.readFileSync(path.join(root,'app.js'),'utf8'),context);
const run=code=>vm.runInContext(code,context);
(async()=>{
 await new Promise(setImmediate);assert.equal(run('book.volume'),1);
 assert.equal(run('cn(59)'), '五十九');assert.equal(run('reign({dynasty:"秦",king:"始皇帝",reign:16})'),'秦始皇帝十六年');
 await run('changeVolume(2)');assert.equal(element('#yearCount').textContent,48);assert.equal(location.hash,'#volume-2');assert(element('#chronicle').innerHTML.includes('已逐条重写'));assert(element('#chronicle').innerHTML.includes('齐伐魏，夺取观津'));
 await run('openYear(2,368)');await run('stepYear(-1)');assert.equal(run('book.volume'),1);assert.equal(run('selected'),369);await run('stepYear(1)');assert.equal(run('book.volume'),2);assert.equal(run('selected'),368);
 let checked=0;
 for(let v=1;v<=294;v++){
  await run(`changeVolume(${v})`);const ys=run('book.years.map(y=>y.year)');
  for(const y of ys){run(`readYear(${y})`);const markup=element('#readerContent').innerHTML;const ids=[...markup.matchAll(/id="para-(\d+)"/g)].map(m=>+m[1]);const ps=run('book.years[readingIndex].paragraphs.length');assert.equal(ids.length,ps,`paragraph coverage v${v} ${y}`);assert.equal(new Set(ids).size,ids.length);for(const anchor of run('book.years[readingIndex].anchors'))assert(ids.includes(anchor));assert(!markup.includes('undefined'));checked++;}
 }
 assert(checked>=1362);assert.equal(run('booksCache.size')<=5,true);assert(element('#nextYear').disabled);assert.equal(run('selected'),-959);
 await run('openYear(200,-662)');assert.equal(element('#nextYear').textContent,'本年续篇 →');await run('stepYear(1)');assert.equal(run('book.volume'),201);assert.equal(run('selected'),-662);assert(element('#readerContent').innerHTML.includes('本年记事分见'));
 const boundary=JSON.parse(fs.readFileSync(path.join(root,'catalog.json'),'utf8')).volumes.find(v=>v.start>0&&v.end<0);assert(boundary);await run(`openYear(${boundary.volume},1)`);await run('stepYear(1)');assert.equal(run('selected'),-1);assert(!element('#readerContent').innerHTML.includes('公元前 -'));
 const catalogData=JSON.parse(fs.readFileSync(path.join(root,'catalog.json'),'utf8'));const workers=[];
 const workerContext=vm.createContext({self:{postMessage(message){workers.push(JSON.parse(JSON.stringify(message)))}},fetch:async name=>({ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,name),'utf8'))})});vm.runInContext(fs.readFileSync(path.join(root,'search-worker.js'),'utf8'),workerContext);
 await vm.runInContext(`self.onmessage({data:{type:'search',id:1,q:'朱温',volumes:${JSON.stringify(catalogData.volumes.map(v=>v.volume))}}})`,workerContext);const search=workers.at(-1);assert(search.complete);assert.equal(search.checked,294);assert(!search.error);assert(search.hits.some(y=>y._volume>=250));assert(!search.hits.some(y=>'text' in y));
 run('fullSearchHits='+JSON.stringify(search.hits)+';searchChecked=294;searchComplete=true');element('#searchScope').value='all';element('#search').value='朱温';run('render()');assert(element('#chronicle').innerHTML.includes('294 / 294'));element('#searchScope').value='current';element('#search').value='';
 location.hash='#year-403';await run('routeFromHash()');assert.equal(run('book.volume'),1);assert.equal(run('selected'),403);
 location.hash='#volume-6-year-231';await run('routeFromHash()');assert.equal(run('book.volume'),6);assert(element('#readerContent').innerHTML.includes('十六年'));assert(element('#readerContent').innerHTML.includes('年头写作'));
 location.hash='#volume-10-intro';await run('routeFromHash()');assert.equal(run('book.volume'),10);assert.equal(run('readingIndex'),-1);await run('stepYear(1)');assert.equal(run('selected'),204);
 await run('changeVolume(1)');run('period="安王";window.scrollY=300');await run('openYear(1,401)');run('closeReader()');await run('routeFromHash()');assert.equal(run('period'),'安王');assert.equal(run('yearbookScroll'),300);
 // Exercise the actual delegated click listener, including nested button content.
 await run('changeVolume(1)');run('period="all"');
 for(const type of ['major','war','power','reform','person','all']){
  const button={dataset:{eventFilter:type}};
  listeners.get('click')({target:{closest(selector){return selector==='button'?button:null;}}});
  assert.equal(run('eventFilter'),type,'Click selects '+type);
  assert.equal(run('filtered().every(y=>eventFilter==="all"||eventIndices(y).length>0)'),true);
 }
 // Category filtering retains original title indices and reading anchors.
 await run('changeVolume(1)');run('period="all"');
 assert(run('filtered().some(y=>!y.recorded)'), 'All keeps unrecorded years');
 for(const [title,type] of [['晋阳之战','war'],['三晋获封诸侯','power'],['吴起变法','reform'],['魏文侯用人','person'],['彗星出现','major']])assert(run(`eventCategories(${JSON.stringify(title)}).includes(${JSON.stringify(type)})`));
 run('eventFilter="war";render()');
 assert(run('filtered().length>0'));assert(run('filtered().every(y=>eventIndices(y).every(i=>eventCategories(y.titles[i]).includes("war")))'));
 const warMarkup=element('#chronicle').innerHTML;assert(warMarkup.includes('data-anchor="8"'));assert(!warMarkup.includes('司马光论礼、分与名'));assert(!run('filtered().some(y=>!y.recorded)'));
 await run('openYear(1,403,8)');await run('stepYear(1)');run('closeReader()');assert.equal(run('eventFilter'),'war');assert(element('#chronicle').innerHTML.includes('tag-war'));
 run('eventFilter="all";render()');assert(run('filtered().some(y=>!y.recorded)'));
 run('eventFilter="reform";render()');assert(run('filtered().every(y=>eventIndices(y).length>0)'));
 await run('changeVolume(2)');assert(run('filtered().length>0'));assert(element('#chronicle').innerHTML.includes('tag-reform'));
 element('#search').value='不存在的记事词';run('render()');assert.equal(run('filtered().length'),0);
 element('#search').value='';element('#searchScope').value='all';element('#search').value='朱温';run('fullSearchHits='+JSON.stringify(search.hits)+';eventFilter="war";render()');assert(run('filtered().every(y=>eventIndices(y).length>0)'));
 run('eventFilter="all"');element('#searchScope').value='current';element('#search').value='';
 assert(element('#dynastyTabs').innerHTML.includes('data-dynasty="唐"'));
 console.log('PASS: '+checked+' annual volume entries across 294 volumes; all paragraph IDs and event anchors; BCE/CE transition; same-year continuation; bounded cache; whole-book worker search; legacy/deep links; intro; return state.');
})().catch(e=>{console.error(e);process.exitCode=1});
