/* Source-linked annual events. One painted point is one model-reviewed event. */
(async () => {
 const root = document.querySelector('#historyRiver');
 if (!root) return;
 function restoreRiverPosition() {
  let state;
  try {state=JSON.parse(sessionStorage.getItem('tongjian-return-scroll'));} catch {}
  if (state?.source!==location.href || !Number.isFinite(state.scroll)) return;
  sessionStorage.removeItem('tongjian-return-scroll');
  requestAnimationFrame(()=>window.scrollTo({top:state.scroll,behavior:'instant'}));
 }
 window.addEventListener('pageshow',restoreRiverPosition);
 restoreRiverPosition();
 const $ = selector => root.querySelector(selector);
 const canvas = $('canvas'), ctx = canvas.getContext('2d');
 const colors = ['#79a4b1','#ac91a2','#88b58f','#8e83ba','#bd9873','#78b4ab','#b578a5','#a0b972','#819fbe','#bb7b76','#77b38f','#ad8bc0','#b9a365','#8fb6bd','#b19595','#91b580'];
 const topicNames = {all:'天灾、饥荒与战争',disaster:'天灾',famine:'饥荒',war:'战争'};
 const topicColors = {disaster:'#58abc4',famine:'#16843a',war:'#ef894c'};
 const esc = value => String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const label = year => (year > 0 ? '公元前 ' : '公元 ') + Math.abs(year) + ' 年';
 const href = (year,event) => {
  const source = event?.sources[0];
  return `reader.html#volume-${source?.volume || year.volumes[0]}-year-${source?.year || year.year}${source ? '-para-'+source.anchor : ''}`;
 };
 let data;
 try {
  const response = await fetch('river-data.json?v=deploy-1791962047');
  if (!response.ok) throw Error(response.status);
  data = await response.json();
  if (data.schemaVersion !== 3) throw Error('Event index version mismatch');
 } catch (error) {
  $('.river-detail').innerHTML = '<p>事件索引暂未加载，请刷新重试。仍可通过下方年表入口阅读。</p>';
  return;
 }
 const years = data.years, eras = [...new Set(years.map(year => year.dynasty))];
 $('.river-chart-note').textContent='一点表示已收录的事件。';
 const tooltip=document.createElement('div');
 tooltip.className='river-point-tooltip';tooltip.setAttribute('role','tooltip');tooltip.hidden=true;
 $('.river-stage').append(tooltip);
 let tooltipPinned=false,tooltipEvent=null,hoveredEvent=null;
 let topic='all', width=0, height=0, center=171, selected=171, span=170, selectedEvent=null;
 let drag=null, moved=false, phase=0, lastSaved='', animationFrame=0, points=[];
 const cache = new Map(), seeds = new Map();
 const entriesFor = year => {
  const key = topic+':'+year.year;
  if (!cache.has(key)) cache.set(key,year.events.filter(event => topic==='all' || event.categories.includes(topic)));
  return cache.get(key);
 };
 const seedFor = event => {
  if (!seeds.has(event.id)) {
   let hash=2166136261;
   for (const c of event.id) hash=Math.imul(hash^c.charCodeAt(0),16777619);
   seeds.set(event.id,hash>>>0);
  }
  return seeds.get(event.id);
 };
 const color = year => colors[eras.indexOf(year.dynasty)%colors.length];
 $('.river-era').innerHTML = eras.map(era=>`<option value="${esc(era)}">${esc(era)}纪</option>`).join('');
 const eraRanges=eras.map(era=>{
  const start=years.findIndex(year=>year.dynasty===era);
  const count=years.filter(year=>year.dynasty===era).length;
  return {era,start,count,mid:(start+count/2)/years.length};
 });
 $('.river-era-band').innerHTML = eraRanges.map(({era,mid})=>`<button type="button" class="river-era-label" data-era="${esc(era)}" aria-pressed="false" style="--era-mid:${mid*100}%">${esc(era)}纪</button>`).join('');
 $('.river-overview').innerHTML = eraRanges.map(({era,count},index)=>`<span data-era="${esc(era)}" style="width:${count/years.length*100}%;background:${colors[index]}" title="${esc(era)}纪"></span>`).join('')+'<div class="river-position" tabindex="0" role="slider" aria-label="拖动浏览全书年份" aria-valuemin="0"></div>';
 // Short periods share crowded space: stack labels, keeping their leaders at exact time positions.
 function layoutEraLabels() {
  const band=$('.river-era-band'), width=band.clientWidth, lanes=[];
  band.querySelectorAll('.river-era-label').forEach((item,index)=>{
   const labelWidth=item.offsetWidth, midpoint=eraRanges[index].mid*width;
   const left=Math.max(0,Math.min(width-labelWidth,midpoint-labelWidth/2));
   let lane=0;
   while(lanes[lane]!==undefined && left<lanes[lane]+6)lane++;
   lanes[lane]=left+labelWidth;
   item.style.left=left+'px';
   item.style.bottom=(lane*30+12)+'px';
   item.style.setProperty('--leader-x',(midpoint-left)+'px');
   item.style.setProperty('--leader-height',(lane*30+12)+'px');
  });
  band.style.height=(lanes.length*30+12)+'px';
 }
 new ResizeObserver(layoutEraLabels).observe($('.river-era-band'));
 const overview=$('.river-overview'), position=$('.river-position');
 position.setAttribute('aria-valuemax',String(years.length-1));
 try {
  const state=JSON.parse(sessionStorage.getItem('tongjian-river'));
  if (state && Number.isInteger(state.selected) && state.selected>=0 && state.selected<years.length && [60,170,400,1362].includes(state.span) && Number.isFinite(state.center)) {
   selected=state.selected;center=Math.max(0,Math.min(years.length-1,state.center));span=state.span;
   if (state.topic in topicNames) topic=state.topic;
   selectedEvent=state.selectedEvent || null;
  }
 } catch {}
 $('.river-zoom').value=span;
 $('.river-topic').value=topic;
 function bounds() {return center-span/2;}
 function detail() {
  const year=years[selected], events=entriesFor(year);
  $('.river-chart-year').textContent=label(year.year);
  $('.river-panel-year').textContent=label(year.year);
  $('.river-event-count').textContent=events.length+' 条';
  if (!events.some(event=>event.id===selectedEvent)) selectedEvent=events[0]?.id || null;
  const list=$('.river-event-list'), key=year.year+':'+topic;
  const scroll=list.dataset.key===key?list.scrollTop:0;
  $('.river-detail').innerHTML='';
  if (topic==='famine' && data.summary.famineSupplement) {
   const audit=data.summary.famineSupplement;
   $('.river-detail').innerHTML+=`<p>全书已收录 ${audit.famineCount} 条饥荒，涉及 ${audit.famineYearCount} 个年份。同年同地灾情与赈济合并，跨年按年记录；尚非全书穷尽统计。</p>`;
  }
  list.dataset.key=key;
  list.innerHTML=events.length ? events.map((item,index)=>`<li><a class="river-event-row${item.id===selectedEvent?' is-selected':''}" data-event="${item.id}" href="${href(year,item)}" aria-current="${item.id===selectedEvent}" title="${esc(item.categories.map(k=>topicNames[k]).join(' / ')+' · '+item.title)}"><span class="river-row-index" aria-hidden="true">${index+1}</span><span class="river-row-dots" aria-hidden="true">${item.categories.map(k=>`<i style="background:${topicColors[k]}"></i>`).join('')}</span><span class="river-row-title">${esc(item.title)}</span><span class="river-row-arrow" aria-hidden="true">↗</span></a></li>`).join('') : '<li class="river-event-empty">本年暂无已复核事件</li>';
  list.scrollTop=scroll;
  const row=list.querySelector('.is-selected');
  if(row) {
   const box=list.getBoundingClientRect(), target=row.getBoundingClientRect();
   if(target.top<box.top)list.scrollTop+=target.top-box.top;
   else if(target.bottom>box.bottom)list.scrollTop+=target.bottom-box.bottom;
  }
  $('.river-era').value=year.dynasty;
  root.querySelectorAll('.river-era-band [data-era], .river-overview [data-era]').forEach(item=>{
   const active=item.dataset.era===year.dynasty;
   item.classList.toggle('is-current',active);
   if(item.tagName==='BUTTON')item.setAttribute('aria-pressed',String(active));
  });

 }
 $('.river-event-list').addEventListener('click',e=>{
  const link=e.target.closest('a[data-event]');
  if(!link)return;
  try {sessionStorage.setItem('tongjian-reader-origin',JSON.stringify({source:location.href,target:new URL(link.href).hash,scroll:window.scrollY}));} catch {}
  selectedEvent=link.dataset.event;
  $('.river-event-list').querySelectorAll('[data-event]').forEach(item=>{
   const active=item.dataset.event===selectedEvent;
   item.classList.toggle('is-selected',active);item.setAttribute('aria-current',String(active));
  });
  draw();
 });
 function choose(index,recenter=true,eventId=null) {
  hideTooltip();
  selected=Math.max(0,Math.min(years.length-1,Math.round(index)));
  if (recenter) center=selected;
  selectedEvent=eventId;
  detail();draw();
 }
 // Keep both banks continuous while making the current visible at a glance.
 const bankWave = index => 9*Math.sin(index*.075+phase*.34)+4*Math.sin(index*.19+phase*.22);
 function draw() {
  const saved=JSON.stringify({selected,center,span,topic,selectedEvent});
  if (saved!==lastSaved) {try {sessionStorage.setItem('tongjian-river',saved);lastSaved=saved;} catch {}}
  if (!width) return;
  const start=bounds(), x=index=>(index-start)/span*width, top=92, bottom=height-62;
  ctx.clearRect(0,0,width,height);points=[];
  for (let i=Math.max(0,Math.floor(start));i<=Math.min(years.length-1,Math.ceil(start+span));i++) {
   const year=years[i], events=entriesFor(year), px=x(i), next=x(i+1);
   const wave=bankWave(i),t=top+wave,b=bottom+wave*.6;
   const gradient=ctx.createLinearGradient(0,t,0,b);
   gradient.addColorStop(0,color(year));gradient.addColorStop(1,'#5a7f80');
   ctx.globalAlpha=.7;ctx.fillStyle=gradient;
   const nw=bankWave(i+1);
   ctx.beginPath();ctx.moveTo(px,t);ctx.lineTo(next,top+nw);ctx.lineTo(next,bottom+nw*.6);ctx.lineTo(px,b);ctx.closePath();ctx.fill();
   const heat=Math.min(1,events.length/20);
   if (heat>.2) {
    const glow=ctx.createRadialGradient(px,(t+b)/2,0,px,(t+b)/2,30+heat*70);
    glow.addColorStop(0,`rgba(224,122,55,${heat*.5})`);glow.addColorStop(1,'rgba(224,122,55,0)');
    ctx.fillStyle=glow;ctx.fillRect(px-100,t,200,b-t);
   }
   ctx.globalAlpha=1;
   // Event positions stay fixed while the river banks move around them.
   for (const event of events) {
    const seed=seedFor(event);
    const py=top+18+(seed%997/997)*(bottom-top-36);
    const pointX=px+(seed%101/100-.5)*Math.min(width/span*.65,12);
    const radius=2.8+seed%5/3;
    points.push({x:pointX,y:py,radius,event,index:i});
   }
  }
  // Decorative water lines only: event counts and their year positions stay fixed.
  ctx.strokeStyle='#f7f2dc';
  for (let n=0;n<4;n++) {
   ctx.globalAlpha=.24+.04*Math.sin(phase*.7+n);
   ctx.lineWidth=n%2?1:1.4;
   ctx.beginPath();
   for (let px=0;px<=width;px+=8) {
    const py=height*.43+n*23+6*Math.sin(px/65+n-phase*1.05);
    px?ctx.lineTo(px,py):ctx.moveTo(px,py);
   }
   ctx.stroke();
   // Short highlights travel with the current without adding event-like dots.
   ctx.globalAlpha=.36;
   ctx.setLineDash([24,150]);ctx.lineDashOffset=-phase*(20+n*3);
   ctx.stroke();ctx.setLineDash([]);
  }
  ctx.lineWidth=1;
  ctx.globalAlpha=1;
  // Draw event points last so passing water lines cannot make them flicker.
  for (const point of points) {
   const {x:pointX,y:py,radius,event,index:i}=point;
   const kinds=topic==='all'?event.categories:[topic];
   for (let k=0;k<kinds.length;k++) {
    ctx.beginPath();ctx.moveTo(pointX,py);ctx.arc(pointX,py,radius,k/kinds.length*Math.PI*2,(k+1)/kinds.length*Math.PI*2);ctx.closePath();
    ctx.fillStyle=topicColors[kinds[k]];ctx.fill();
   }
   if (hoveredEvent ? event.id===hoveredEvent : i===selected && event.id===selectedEvent) {
    ctx.beginPath();ctx.arc(pointX,py,radius+2,0,Math.PI*2);ctx.strokeStyle='#fffef9';ctx.lineWidth=1.5;ctx.stroke();ctx.lineWidth=1;
   }
  }
  const step=span<=80?10:span<=220?50:100;
  ctx.font='12px SimSun,serif';ctx.fillStyle='#697366';ctx.strokeStyle='#b4b5a8';
  for (let i=Math.max(0,Math.ceil(start));i<start+span && i<years.length;i++) {
   const year=years[i];if(Math.abs(year.year)%step!==0 && year.year!==-1)continue;
   const px=x(i);ctx.beginPath();ctx.moveTo(px,height-40);ctx.lineTo(px,height-33);ctx.stroke();
   ctx.fillText((year.year>0?'前':'')+Math.abs(year.year),px-12,height-14);
  }
  position.style.left=Math.max(0,start)/years.length*100+'%';position.style.width=(Math.min(years.length,start+span)-Math.max(0,start))/years.length*100+'%';
  position.setAttribute('aria-valuenow',String(selected));
  position.setAttribute('aria-valuetext',label(years[selected].year));
  $('.river-prev').disabled=selected===0;$('.river-next').disabled=selected===years.length-1;
 }
 function resize() {
  hideTooltip();
  const box=canvas.getBoundingClientRect(),dpr=window.devicePixelRatio||1;
  width=box.width;height=box.height;canvas.width=Math.round(width*dpr);canvas.height=Math.round(height*dpr);
  ctx.setTransform(dpr,0,0,dpr,0,0);draw();
 }
 function pointAt(event) {
  const box=canvas.getBoundingClientRect(),px=event.clientX-box.left,py=event.clientY-box.top;
  let nearest=null,distance=Infinity;
  for (const point of points) {
   if(point.x<0 || point.x>width)continue;
   const d=Math.hypot(point.x-px,point.y-py);
   const hitRadius=Math.max(point.radius+6,event.pointerType==='touch'?18:12);
   if(d<=hitRadius && d<distance){nearest=point;distance=d;}
  }
  return nearest;
 }
 function hideTooltip() {
  tooltip.hidden=true;tooltipPinned=false;tooltipEvent=null;
  if(hoveredEvent!==null){hoveredEvent=null;draw();}
 }
 function positionTooltip(point) {
  const w=tooltip.offsetWidth,h=tooltip.offsetHeight;
  let left=point.x+14;
  if(left+w>width-8)left=point.x-w-14;
  tooltip.style.left=Math.max(8,Math.min(left,width-w-8))+'px';
  tooltip.style.top=Math.max(8,Math.min(point.y-h/2,height-h-8))+'px';
 }
 function showTooltip(point,pinned=false) {
  if(!point){if(hoveredEvent!==null){hoveredEvent=null;draw();}if(!tooltipPinned)hideTooltip();return;}
  if(tooltipEvent!==point.event.id) {
   const event=point.event;
   tooltip.innerHTML=`<div class="river-tooltip-meta">${label(years[point.index].year)} · ${event.categories.map(k=>topicNames[k]).join(' / ')}</div><strong class="river-tooltip-title">${esc(event.title)}</strong>`;
  }
  const highlightChanged=hoveredEvent!==point.event.id;
  hoveredEvent=point.event.id;
  tooltipEvent=point.event.id;tooltipPinned=pinned;tooltip.hidden=false;positionTooltip(point);
  if(highlightChanged)draw();
 }
 canvas.addEventListener('pointerdown',event=>{
  $('.river-stage').focus({preventScroll:true});drag={x:event.clientX,y:event.clientY,center,point:pointAt(event)};moved=false;canvas.setPointerCapture(event.pointerId);
  if(!drag.point)hideTooltip();
 });
 canvas.addEventListener('pointermove',event=>{
  if (!drag) {const point=pointAt(event);showTooltip(point,!!point&&tooltipPinned&&tooltipEvent===point.event.id);return;}
  const delta=event.clientX-drag.x;
  if (Math.abs(delta)>7) moved=true;
  if (moved) {canvas.style.cursor='grabbing';center=Math.max(0,Math.min(years.length-1,drag.center-delta/width*span));choose(center,false);}
 });
 canvas.addEventListener('pointerup',event=>{
  if (!drag)return;
  if(!moved && Math.abs(event.clientY-drag.y)<=7) {
   const point=drag.point;
   if(point){choose(point.index,false,point.event.id);showTooltip(point,true);}
   else choose(bounds()+(event.clientX-canvas.getBoundingClientRect().left)/width*span,false);
  }
  drag=null;canvas.style.cursor='pointer';
 });
 canvas.addEventListener('pointercancel',()=>{drag=null;canvas.style.cursor='pointer';hideTooltip();});
 canvas.addEventListener('pointerleave',()=>{hoveredEvent=null;if(!tooltipPinned)hideTooltip();draw();});
 document.addEventListener('pointerdown',event=>{if(!$('.river-stage').contains(event.target))hideTooltip();});
 document.addEventListener('keydown',event=>{if(event.key==='Escape')hideTooltip();});
 $('.river-stage').addEventListener('keydown',event=>{
  if (event.key==='ArrowLeft' || event.key==='ArrowRight') {event.preventDefault();choose(selected+(event.key==='ArrowLeft'?-1:1));}
 });
 $('.river-topic').onchange=event=>{hideTooltip();topic=event.target.value;selectedEvent=null;detail();draw();};
 $('.river-prev').onclick=()=>choose(selected-1);$('.river-next').onclick=()=>choose(selected+1);
 $('.river-zoom').onchange=event=>{hideTooltip();span=+event.target.value;draw();};
 $('.river-era').onchange=event=>choose(years.findIndex(year=>year.dynasty===event.target.value));
 $('.river-era-band').addEventListener('click',event=>{
  const button=event.target.closest('button[data-era]');
  if(button)choose(years.findIndex(year=>year.dynasty===button.dataset.era));
 });
 let overviewDrag=null;
 position.addEventListener('pointerdown',event=>{
  if(event.button!==0)return;
  event.preventDefault();position.focus({preventScroll:true});
  overviewDrag={pointerId:event.pointerId,x:event.clientX,center};
  position.setPointerCapture(event.pointerId);
  position.classList.add('is-dragging');
 });
 position.addEventListener('pointermove',event=>{
  if(!overviewDrag || event.pointerId!==overviewDrag.pointerId)return;
  const trackWidth=overview.getBoundingClientRect().width;
  if(!trackWidth)return;
  center=Math.max(0,Math.min(years.length-1,overviewDrag.center+(event.clientX-overviewDrag.x)/trackWidth*years.length));
  choose(center,false);
 });
 const endOverviewDrag=()=>{overviewDrag=null;position.classList.remove('is-dragging');};
 position.addEventListener('pointerup',endOverviewDrag);
 position.addEventListener('pointercancel',endOverviewDrag);
 position.addEventListener('lostpointercapture',endOverviewDrag);
 position.addEventListener('keydown',event=>{
  let index;
  if(event.key==='ArrowLeft')index=selected-1;
  else if(event.key==='ArrowRight')index=selected+1;
  else if(event.key==='PageDown')index=selected+span;
  else if(event.key==='PageUp')index=selected-span;
  else if(event.key==='Home')index=0;
  else if(event.key==='End')index=years.length-1;
  else return;
  event.preventDefault();choose(index);
 });
 const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
 let visible=false,lastFrame=0;
 function animate(time) {
  animationFrame=0;if(!visible || document.hidden || reducedMotion.matches)return;
  if (time-lastFrame>=33) {phase=time/1000;draw();lastFrame=time;}
  animationFrame=requestAnimationFrame(animate);
 }
 function updateAnimation() {
  if (animationFrame)cancelAnimationFrame(animationFrame);animationFrame=0;
  if (visible && !document.hidden && !reducedMotion.matches)animationFrame=requestAnimationFrame(animate);
 }
 new IntersectionObserver(entries=>{visible=entries[0].isIntersecting;updateAnimation();}).observe(canvas);
 document.addEventListener('visibilitychange',updateAnimation);
 reducedMotion.addEventListener('change',()=>{phase=0;draw();updateAnimation();});
 new ResizeObserver(resize).observe(canvas);detail();resize();
})();
