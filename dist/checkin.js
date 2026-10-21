// Explicit reading check-ins; repeated reading counts as a visit, unique years as progress.
(()=>{
 'use strict';
 const reader=document.querySelector('#readerBackdrop');
 if(!reader)return;
 const guestKey='tongjian-reading-checkins-v2',oldKey='tongjian-reading-days-v1';
 let interacted=false,dismissed=false,frame=0;
 let key=guestKey,userId=null,syncing=false,syncAgain=false,ranking=null,lastPraise='';
 const box=document.createElement('section');box.className='reading-checkin';box.setAttribute('aria-label','阅读打卡');
 box.innerHTML='<div class="checkin-emblem" aria-hidden="true"><svg viewBox="0 0 64 64" fill="none"><path d="M14 20c7-2 13 0 18 4 5-4 11-6 18-4v27c-7-2-13 0-18 4-5-4-11-6-18-4V20Z"/><path d="M32 25v25M20 29l6 2m-6 6 6 2m12-8 6-2m-6 10 6-2"/><path class="emblem-rays" d="M32 6v6M12 10l4 5m36-5-4 5M4 27l6 1m50-1-6 1"/></svg><span>✓</span></div><div class="checkin-copy"><span class="checkin-kicker">读史有得 · 一年一印</span><h2>又读过一年历史</h2><p class="checkin-year"></p><p class="checkin-message" role="status" aria-live="polite"></p><div class="checkin-stats"><div><b data-stat="years">0</b><span>已读年份</span></div><div><b data-stat="visits">0</b><span>阅读打卡</span></div><div><b data-stat="days">0</b><span>阅读天数</span></div></div><p class="checkin-ranking"></p><small></small></div><button type="button" class="checkin-primary">为这一年，留个印记 <span aria-hidden="true">✦</span></button><p class="checkin-footnote">不必赶路，每读一年都有收获。</p>';
 // A non-modal completion prompt, shown only after reaching the end.
 box.hidden=true;reader.append(box);
 const close=document.createElement('button');close.type='button';close.className='checkin-close';close.setAttribute('aria-label','收起打卡提示');close.textContent='×';box.append(close);
 close.onclick=()=>{dismissed=true;box.hidden=true;reader.querySelector('#nextYear')?.focus({preventScroll:true});};
 function visibility(){
  frame=0;
  const content=document.querySelector('#readerContent .reader-inner');
  const nav=reader.querySelector('.reader-nav');
  const bottom=nav?Math.max(0,innerHeight-nav.getBoundingClientRect().top):0;
  box.style.setProperty('--checkin-bottom',Math.max(20,bottom+16)+'px');
  const rect=content?.getBoundingClientRect();
  box.hidden=!currentYear()||reader.classList.contains('hidden')||dismissed||!interacted||!rect||rect.bottom>innerHeight-bottom-8||rect.bottom<80;
 }
 function schedule(){if(!frame)frame=requestAnimationFrame(visibility);}
 const interact=()=>{interacted=true;schedule();};
 window.addEventListener('scroll',schedule,{passive:true});
 window.addEventListener('wheel',interact,{passive:true});
 window.addEventListener('touchmove',interact,{passive:true});
 window.addEventListener('keydown',e=>{if(['PageDown','End','ArrowDown',' '].includes(e.key))interact();});
 window.addEventListener('resize',schedule);
 new ResizeObserver(schedule).observe(document.querySelector('#readerContent'));
 new MutationObserver(schedule).observe(reader,{attributes:true,attributeFilter:['class']});
 const button=box.querySelector('button:not(.checkin-close)'),message=box.querySelector('.checkin-message'),rankText=box.querySelector('.checkin-ranking'),status=box.querySelector('small');
 const retry=document.createElement('button');retry.className='checkin-retry';retry.type='button';retry.textContent='重试同步';retry.hidden=true;box.append(retry);retry.onclick=()=>sync();
 const encouragement=['又读过一年历史，慢慢积累，也能走很远。','这一年的兴衰，你又多懂了一点。','读过的一段，都是向前的一步。','不必赶路，这次也有收获。'];
 const newId=()=>crypto.randomUUID?crypto.randomUUID():'10000000-1000-4000-8000-100000000000'.replace(/[018]/g,c=>(Number(c)^crypto.getRandomValues(new Uint8Array(1))[0]&15>>Number(c)/4).toString(16));
 const merge=(a,b)=>[...new Map([...a,...b].map(e=>[e.id,e])).values()];
 function today(){const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;}
 function validDay(day){return typeof day==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(day)&&Number.isFinite(Date.parse(day+'T12:00:00'))&&new Date(day+'T12:00:00').getDate()===Number(day.slice(-2));}
 function read(storageKey=key){
  const raw=localStorage.getItem(storageKey),entries=raw===null?[]:JSON.parse(raw);
  if(!Array.isArray(entries)||!entries.every(e=>e&&typeof e.id==='string'&&/^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(e.id)&&Number.isInteger(e.year)&&e.year!==0&&e.year>=-959&&e.year<=403&&Number.isInteger(e.volume)&&e.volume>=1&&e.volume<=294&&validDay(e.day)))throw new Error('Invalid check-ins');
  return merge([],entries);
 }
 function currentYear(){return typeof book!=='undefined'&&book&&readingIndex>=0&&book.years[readingIndex]?.year===selected&&book.years[readingIndex].recorded?{year:selected,volume:book.volume}:null;}
 function render(){
  const current=currentYear();box.classList.toggle('checkin-complete',!!lastPraise);schedule();
  box.querySelector('h2').textContent=lastPraise?'这一年，记下了':'又读过一年历史';
  box.querySelector('.checkin-year').textContent=current?`${current.year>0?'公元前':'公元'} ${Math.abs(current.year)} 年 · ${lastPraise?'阅读已记录':'已读至篇末'}`:'';
  try{
   const entries=read(),years=new Set(entries.map(e=>e.year));
   const legacy=JSON.parse(localStorage.getItem(userId?oldKey+':account:'+userId:oldKey)||'[]');
   if(!Array.isArray(legacy)||!legacy.every(validDay))throw new Error('Invalid legacy days');
   const days=new Set([...legacy,...entries.map(e=>e.day)]);
   button.disabled=!current;
   button.textContent=lastPraise?(document.querySelector('#nextYear')?.disabled?'收好这份积累 ✓':'接着读下一年 →'):'为这一年，留个印记 ✦';
   message.textContent=lastPraise||'千年的历史，你又向前走了一年。';
   box.querySelector('[data-stat="years"]').textContent=years.size;
   box.querySelector('[data-stat="visits"]').textContent=entries.length;
   box.querySelector('[data-stat="days"]').textContent=days.size;
   rankText.textContent=!userId?'登录后，看看你的阅读排名。':ranking?(ranking.rank?`阅读榜 第 ${ranking.rank} 名 · 共 ${ranking.participants} 位读者`:'你的阅读旅程，就从这一年开始。'):'阅读排名更新中…';
   rankText.title='按读过的不同年份数排名，同分并列';

  }catch{button.disabled=!current;message.textContent='暂时无法读取本机打卡记录，请检查浏览器存储设置。';}
 }
 button.addEventListener('click',()=>{
  const current=currentYear();if(!current)return;
  if(lastPraise){if(!document.querySelector('#nextYear')?.disabled)document.querySelector('#nextYear').click();else close.click();return;}
  try{
   const entries=read(),repeated=entries.some(e=>e.year===current.year);
   entries.push({id:newId(),...current,day:today()});
   localStorage.setItem(key,JSON.stringify(entries));
   ranking=null;box.classList.remove('checkin-error');
   lastPraise=(repeated?'重读这一年，又有新的收获。':'')+encouragement[(entries.length-1)%encouragement.length];
   render();sync();
  }catch{box.classList.add('checkin-error');message.textContent='这次打卡未能保存，请检查浏览器存储设置后重试。';}
 });
 async function api(path,data,csrf){
  const response=await fetch('/api/v1/'+path,{method:data?'POST':'GET',credentials:'same-origin',cache:'no-store',headers:{'Accept':'application/json',...(data?{'Content-Type':'application/json','X-CSRFToken':csrf}:{})},...(data?{body:JSON.stringify(data)}:{})});
  if(!response.ok)throw new Error('sync');return response.json();
 }
 async function sync(){
  if(syncing){syncAgain=true;return;}syncing=true;
  try{
   const session=await api('session/'),nextUser=session.authenticated?session.user_id:null;
   if(nextUser!==userId){ranking=null;lastPraise='';}
   userId=nextUser;key=userId?guestKey+':account:'+userId:guestKey;
   render();retry.hidden=true;
   if(!userId){status.textContent='';return;}
   status.textContent='正在同步…';
   const owner=userId,guest=read(guestKey),pending=read(key),upload=merge(guest,pending);
   let result;
   if(!upload.length)result=await api('me/reading-checkins/');
   for(let i=0;i<upload.length;i+=500)result=await api('me/reading-checkins/',{user_id:owner,entries:upload.slice(i,i+500)},session.csrf_token);
   if(result.user_id!==owner)throw new Error('account changed');
   const latest=read(key),sentIds=new Set(guest.map(e=>e.id)),remaining=read(guestKey).filter(e=>!sentIds.has(e.id));
   localStorage.setItem(key,JSON.stringify(merge(result.entries,latest)));
   localStorage.setItem(guestKey,JSON.stringify(remaining));
   const confirmed=new Set(result.entries.map(e=>e.id));
   if(latest.some(e=>!confirmed.has(e.id))||remaining.length)syncAgain=true;
   ranking=syncAgain?null:result;
   // Preserve earlier daily records without inventing historical years or check-ins.
   const oldAccount=oldKey+':account:'+owner;
   const oldGuest=JSON.parse(localStorage.getItem(oldKey)||'[]'),oldLocal=JSON.parse(localStorage.getItem(oldAccount)||'[]');
   if(!Array.isArray(oldGuest)||!Array.isArray(oldLocal)||![...oldGuest,...oldLocal].every(validDay))throw new Error('Invalid legacy days');
   const dates=[...new Set([...oldGuest,...oldLocal])];
   let oldResult;
   if(!dates.length)oldResult=await api('me/reading-days/');
   for(let i=0;i<dates.length;i+=1000)oldResult=await api('me/reading-days/',{user_id:owner,days:dates.slice(i,i+1000)},session.csrf_token);
   if(oldResult.user_id!==owner)throw new Error('account changed');
   localStorage.setItem(oldAccount,JSON.stringify(oldResult.days));
   if(dates.length){localStorage.setItem(oldKey,JSON.stringify(JSON.parse(localStorage.getItem(oldKey)||'[]').filter(d=>!oldGuest.includes(d))));}
   render();status.textContent='';
  }catch{ranking=null;render();status.textContent='本机记录已保留，同步后更新排名。';retry.hidden=false;}
  finally{syncing=false;if(syncAgain){syncAgain=false;sync();}}
 }
 new MutationObserver(()=>{lastPraise='';interacted=false;dismissed=false;box.hidden=true;render();}).observe(document.querySelector('#readerContent'),{childList:true});
 window.addEventListener('tongjian-session',()=>sync());window.addEventListener('online',()=>sync());
 window.addEventListener('storage',e=>{if(e.key===key||e.key===guestKey||e.key===null){render();sync();}});
 window.addEventListener('focus',()=>{render();sync();});
 document.addEventListener('visibilitychange',()=>{if(!document.hidden){render();sync();}});
 render();sync();
})();
