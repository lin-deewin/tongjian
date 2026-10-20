// Logic and generated-markup checks in a small DOM harness; not browser visual QA.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),crypto=require('crypto').webcrypto;
const path=require('path');const root=path.resolve(__dirname,'../dist');
const elements=new Map(),listeners=new Map();
function element(key){if(!elements.has(key))elements.set(key,{innerHTML:'',textContent:'',value:'',checked:false,disabled:false,style:{setProperty(){}},classList:{set:new Set(),add(...xs){xs.forEach(x=>this.set.add(x))},remove(...xs){xs.forEach(x=>this.set.delete(x))},contains(x){return this.set.has(x)},toggle(x,v){if(v===undefined)v=!this.set.has(x);if(v)this.set.add(x);else this.set.delete(x)}},focus(){},addEventListener(){},removeEventListener(){},getBoundingClientRect(){return {top:0}},closest(){return element('label')},scrollIntoView(){}});return elements.get(key);}
element('#searchScope').value='current';
element('.theme-select').options=[{value:'light'},{value:'dark'},{value:'warm'}];
const location={hash:'',pathname:'/',search:''};const history={pushState(_a,_b,url){location.hash=url.includes('#')?'#'+url.split('#')[1]:''}};
const context=vm.createContext({console,URLSearchParams,setTimeout,clearTimeout,location,history,crypto:process.env.READER_NO_WEBCRYPTO?undefined:crypto,TextEncoder,document:{querySelector:element,querySelectorAll:()=>[],addEventListener(type,handler){const previous=listeners.get(type);listeners.set(type,previous?(event=>{previous(event);handler(event)}):handler)},body:element('body'),documentElement:{dataset:{},style:{setProperty(){}},scrollHeight:1000},activeElement:element('active')},window:{scrollY:0,innerHeight:700,scrollTo(){},addEventListener(){}},requestAnimationFrame:f=>f(),fetch:async name=>{const raw=fs.readFileSync(path.join(root,name.split('?')[0]),'utf8');return {ok:true,text:async()=>raw,json:async()=>JSON.parse(raw)}}});
vm.runInContext(fs.readFileSync(path.join(root,'people.js'),'utf8'),context);
vm.runInContext(fs.readFileSync(path.join(root,'app.js'),'utf8'),context);
const run=code=>vm.runInContext(code,context);
for(const input of ['', 'abc', '晋国（首府新田〔山西省侯马市〕）', 'a'.repeat(100000)]){
 context.digestInput=input;
 assert.equal(run('sha256Fallback(digestInput)'),require('crypto').createHash('sha256').update(input).digest('hex'));
}

(async()=>{
 await new Promise(resolve=>setTimeout(resolve,100));assert.equal(run('book.volume'),1);
 assert.equal(run('cn(59)'), '五十九');assert.equal(run('reign({dynasty:"秦",king:"始皇帝",reign:16})'),'秦始皇帝十六年');
 await run('changeVolume(2)');assert.equal(run('book.years.length'),48);assert.equal(element('#volumeCount').textContent,'第 2 / 294 卷');assert.equal(element('#mobilePeriod').value,'all');assert.equal(location.hash,'#volume-2');assert(!element('#chronicle').innerHTML.includes('事件提要 · 已逐条重写'));assert(element('#chronicle').innerHTML.includes('齐伐魏，夺取观津'));
 await run('openYear(2,368)');await run('stepYear(-1)');assert.equal(run('book.volume'),1);assert.equal(run('selected'),369);await run('stepYear(1)');assert.equal(run('book.volume'),2);assert.equal(run('selected'),368);
 let checked=0;
 for(let v=1;v<=294;v++){
  await run(`changeVolume(${v})`);const ys=run('book.years.map(y=>y.year)');
  for(const y of ys){run(`readYear(${y})`);const markup=element('#readerContent').innerHTML;const ids=[...markup.matchAll(/id="para-(\d+)"/g)].map(m=>+m[1]);const ps=run('book.years[readingIndex].paragraphs.length');assert.equal(ids.length,ps,`paragraph coverage v${v} ${y}`);assert.equal(new Set(ids).size,ids.length);for(const anchor of run('book.years[readingIndex].anchors'))assert(ids.includes(anchor));assert(!markup.includes('undefined'));assert.equal((markup.match(/<figure class="translation-illustration">/g)||[]).length,run('book.years[readingIndex].yearIllustrations?.length||0'),`illustration coverage v${v} ${y}`);checked++;}
 }
 assert(checked>=1362);assert.equal(run('booksCache.size')<=5,true);assert(element('#nextYear').disabled);assert.equal(run('selected'),-959);
 await run('openYear(200,-662)');assert.equal(element('#nextYear').textContent,'本年续篇 →');await run('stepYear(1)');assert.equal(run('book.volume'),201);assert.equal(run('selected'),-662);assert(element('#readerContent').innerHTML.includes('本年记事分见'));
 const boundary=JSON.parse(fs.readFileSync(path.join(root,'catalog.json'),'utf8')).volumes.find(v=>v.start>0&&v.end<0);assert(boundary);await run(`openYear(${boundary.volume},1)`);await run('stepYear(1)');assert.equal(run('selected'),-1);assert(!element('#readerContent').innerHTML.includes('公元前 -'));
 const catalogData=JSON.parse(fs.readFileSync(path.join(root,'catalog.json'),'utf8'));const workers=[];
 const workerContext=vm.createContext({self:{postMessage(message){workers.push(JSON.parse(JSON.stringify(message)))}},fetch:async name=>({ok:true,json:async()=>JSON.parse(fs.readFileSync(path.join(root,name.split('?')[0]),'utf8'))})});vm.runInContext(fs.readFileSync(path.join(root,'search-worker.js'),'utf8'),workerContext);
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
 assert(element('#volumeSelect').innerHTML.includes('<optgroup label="唐">'));
 assert(element('#volumeSelect').innerHTML.includes('前403年—前369年'));
 assert(element('#volumeSelect').innerHTML.includes('公元958年—公元959年'));
 await run('changeVolume(1)');assert(element('#prevVolume').disabled);assert(!element('#nextVolume').disabled);
 element('#recordedOnly').checked=true;run('render()');assert.equal(element('#annualFilterResults').textContent,'30 年');
 run('period="安王";eventFilter="war";render()');assert.equal(element('#mobilePeriod').value,'安王');
 element('#annualFilterReset').onclick();assert.equal(run('period'),'安王');assert.equal(run('eventFilter'),'all');assert(!element('#recordedOnly').checked);
 await run('changeVolume(294)');assert(!element('#prevVolume').disabled);assert(element('#nextVolume').disabled);
 // Age estimates use BC-positive keys and must skip year zero and posthumous records.
 assert.equal(run('personEventAge({year:-208},{birthYear:-161,deathYear:-223,birthSource:"reviewed",birthStatus:"confirmed"})'),47);
 assert.equal(run('personEventAge({year:-1},{birthYear:1,birthSource:"reviewed",birthStatus:"confirmed"})'),1);
 assert.equal(run('personEventAge({year:-25},{birthYear:5,birthSource:"reviewed",birthStatus:"confirmed"})'),29);
 assert.equal(run('personEventAge({year:400},{birthYear:403,birthSource:"reviewed",birthStatus:"confirmed"})'),3);
 assert.equal(run('personEventAge({year:-161},{birthYear:-161,birthSource:"reviewed",birthStatus:"confirmed"})'),0);
 assert.equal(run('personEventAge({year:null},{birthYear:-161,birthSource:"reviewed",birthStatus:"confirmed"})'),null);
 assert.equal(run('personEventAge({year:-160},{birthYear:-161,birthSource:"reviewed",birthStatus:"confirmed"})'),null);
 assert.equal(run('personEventAge({year:-224},{birthYear:-161,deathYear:-223,birthSource:"reviewed",birthStatus:"confirmed"})'),null);
 assert.equal(run('personEventAge({year:-208},{birthYear:null})'),null);
 assert.equal(run('personEventAge({year:-208},{birthYear:-161})'),null);
 // Verify every published profile and event against the age coverage report.
 const lifeReviews=JSON.parse(fs.readFileSync(path.join(root,'../scripts/people/life-years.json'),'utf8')).people;
 const ageReport=JSON.parse(fs.readFileSync(path.join(root,'people-life-report.json'),'utf8'));
 const directory=JSON.parse(fs.readFileSync(path.join(root,'people-index.json'),'utf8')).people;
 assert.equal(Object.keys(lifeReviews).length,directory.length);
 let markedEvents=0,allPeopleEvents=0;
 for(const entry of directory){
  const person=JSON.parse(fs.readFileSync(path.join(root,'people',entry.id+'.json'),'utf8'));
  const review=lifeReviews[entry.id];assert(review);assert.equal(review.name,person.name);
  assert.equal(person.birthYear,review.birthYear);assert.equal(person.birthStatus,review.status);
  for(const event of person.events){
   allPeopleEvents++;
   const age=run('personEventAge('+JSON.stringify(event)+','+JSON.stringify(person)+')');
   const html=run('personEventHtml('+JSON.stringify(event)+','+JSON.stringify(person)+')');
   if(age!==null){assert(Number.isInteger(age)&&age>=0);assert.equal(person.birthStatus,'confirmed');assert(html.includes('约'+age+'岁'));markedEvents++;}
   else assert(!html.includes('class="event-age"'));
  }
 }
 assert.equal(markedEvents,ageReport.eventAgeCoverage.withAge);assert.equal(allPeopleEvents,ageReport.totalEvents);
 assert.equal(run('personEventAge({year:-208},{birthYear:-161,birthSource:"reviewed",birthStatus:"disputed"})'),null);
 console.log('PASS: '+checked+' annual volume entries across 294 volumes; all paragraph IDs and event anchors; BCE/CE transition; same-year continuation; bounded cache; whole-book worker search; legacy/deep links; intro; return state; '+directory.length+' people and '+allPeopleEvents+' events, '+markedEvents+' age labels.');
})().catch(e=>{console.error(e);process.exitCode=1});
