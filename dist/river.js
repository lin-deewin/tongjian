/* Source-linked annual events. One painted point is one model-reviewed event. */
(async () => {
 const root = document.querySelector('#historyRiver');
 if (!root) return;
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
  const response = await fetch('river-data.json?v=20261012-final');
  if (!response.ok) throw Error(response.status);
  data = await response.json();
  if (data.schemaVersion !== 3) throw Error('Event index version mismatch');
 } catch (error) {
  $('.river-detail').innerHTML = '<p>事件索引暂未加载，请刷新重试。仍可通过下方年表入口阅读。</p>';
  return;
 }
 const years = data.years, eras = [...new Set(years.map(year => year.dynasty))];
 let topic='all', width=0, height=0, center=171, selected=171, span=170, selectedEvent=null;
 let drag=null, moved=false, wheelActive=false, phase=0, lastSaved='', animationFrame=0, points=[], pointerInside=false;
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
 $('.river-era-band').innerHTML = eras.map(era=>`<button type="button" class="river-era-label" data-era="${esc(era)}" aria-pressed="false">${esc(era)}纪</button>`).join('');
 $('.river-overview').innerHTML = eras.map(era=>`<span style="width:${years.filter(y=>y.dynasty===era).length/years.length*100}%;background:${colors[eras.indexOf(era)]}" title="${esc(era)}纪"></span>`).join('')+'<i class="river-position"></i>';
 const range=$('.river-range');
 range.max=years.length-1;
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
 const summary=data.summary;
  $('.river-audit').innerHTML=`<summary>核算说明 · 一点一条按年事件</summary><p>10 个 Luna low 子代理复核：已语义核读 ${summary.modelReviewedParagraphs.toLocaleString()} / ${summary.candidateParagraphs.toLocaleString()} 个候选段，收录 ${summary.modelReviewedEvents.toLocaleString()} 条事件。${summary.pendingCandidates ? `另有 ${summary.pendingCandidates.toLocaleString()} 条暂定事件，不作为图上点位；` : ''}${summary.unreviewedCandidateParagraphs ? `还有 ${summary.unreviewedCandidateParagraphs.toLocaleString()} 段候选未核读；` : ''}${summary.unclassifiedCandidates ? `${summary.unclassifiedCandidates.toLocaleString()} 段候选尚未列明事件或排除项；` : ''}${summary.unreviewedCandidateParagraphs || summary.unclassifiedCandidates ? '这些未决候选不绘为事件点。' : '关键词未召回的原文仍可能存在遗漏。'}${summary.limitations?.find(x=>x.includes('排除理由记录'))||''}同事件的多类别合为一个点；跨年战事按年分别记，远景可能重叠。模型复核仍可能有分类、归年和拆并错误，空白不代表当年没有事件。</p><a href="river-audit-report.json" target="_blank" rel="noopener">查看核算报告 ↗</a>`;
 function bounds() {return center-span/2;}
 function detail() {
  const year=years[selected], events=entriesFor(year);
  if (!events.some(event=>event.id===selectedEvent)) selectedEvent=events[0]?.id || null;
  const event=events.find(event=>event.id===selectedEvent);
  $('.river-detail').innerHTML=`<h3>${label(year.year)}</h3><p>${esc(year.dynasty)}纪 · ${topicNames[topic]}：${events.length} 条已复核事件${year.volumes.length>1?' · 本年跨卷':''}</p><div class="river-event-slot">${events.length ? `<select class="river-event-picker" aria-label="选择本年事件">${events.map(item=>`<option value="${item.id}" ${item.id===selectedEvent?'selected':''}>${item.categories.map(k=>topicNames[k]).join(' / ')} · ${esc(item.title)}</option>`).join('')}</select>` : '<p class="river-empty">本年暂无已复核事件</p>'}</div><a class="river-read" href="${href(year,event)}">阅读原文与白话 →</a>`;
  const picker=$('.river-event-picker');
  if (picker) picker.onchange=e=>{selectedEvent=e.target.value;detail();draw();};
  $('.river-era').value=year.dynasty;
  $('.river-era-band').querySelectorAll('[data-era]').forEach(item=>{
   const active=item.dataset.era===year.dynasty;
   item.classList.toggle('is-current',active);item.setAttribute('aria-pressed',String(active));
  });
  range.value=selected;
 }
 function choose(index,recenter=true,eventId=null) {
  selected=Math.max(0,Math.min(years.length-1,Math.round(index)));
  if (recenter) center=selected;
  selectedEvent=eventId;
  detail();draw();
 }
 function draw() {
  const saved=JSON.stringify({selected,center,span,topic,selectedEvent});
  if (saved!==lastSaved) {try {sessionStorage.setItem('tongjian-river',saved);lastSaved=saved;} catch {}}
  if (!width) return;
  const start=bounds(), x=index=>(index-start)/span*width, top=92, bottom=height-62;
  ctx.clearRect(0,0,width,height);points=[];
  for (let i=Math.max(0,Math.floor(start));i<=Math.min(years.length-1,Math.ceil(start+span));i++) {
   const year=years[i], events=entriesFor(year), px=x(i), next=x(i+1);
   const wave=8*Math.sin(i*.075+phase*.22)+4*Math.sin(i*.19+phase*.12),t=top+wave,b=bottom+wave*.6;
   const gradient=ctx.createLinearGradient(0,t,0,b);
   gradient.addColorStop(0,color(year));gradient.addColorStop(1,'#5a7f80');
   ctx.globalAlpha=.7;ctx.fillStyle=gradient;
   const nw=8*Math.sin((i+1)*.075+phase*.22)+4*Math.sin((i+1)*.19+phase*.12);
   ctx.beginPath();ctx.moveTo(px,t);ctx.lineTo(next,top+nw);ctx.lineTo(next,bottom+nw*.6);ctx.lineTo(px,b);ctx.closePath();ctx.fill();
   const heat=Math.min(1,events.length/20);
   if (heat>.2) {
    const glow=ctx.createRadialGradient(px,(t+b)/2,0,px,(t+b)/2,30+heat*70);
    glow.addColorStop(0,`rgba(224,122,55,${heat*.5})`);glow.addColorStop(1,'rgba(224,122,55,0)');
    ctx.fillStyle=glow;ctx.fillRect(px-100,t,200,b-t);
   }
   ctx.globalAlpha=1;
   // No annual cap: every reviewed event gets its own selectable point.
   for (const event of events) {
    const seed=seedFor(event);
    const py=t+15+(seed%997/997)*(b-t-30)+Math.sin(phase+seed)*3;
    const pointX=px+(seed%101/100-.5)*Math.min(width/span*.65,12);
    const radius=(2.8+seed%5/3)*(.9+.1*Math.sin(phase*1.2+seed));
    const kinds=topic==='all'?event.categories:[topic];
    for (let k=0;k<kinds.length;k++) {
     ctx.beginPath();ctx.moveTo(pointX,py);ctx.arc(pointX,py,radius,k/kinds.length*Math.PI*2,(k+1)/kinds.length*Math.PI*2);ctx.closePath();
     ctx.fillStyle=topicColors[kinds[k]];ctx.fill();
    }
    if (i===selected && event.id===selectedEvent) {
     ctx.beginPath();ctx.arc(pointX,py,radius+2,0,Math.PI*2);ctx.strokeStyle='#fffef9';ctx.lineWidth=1.5;ctx.stroke();ctx.lineWidth=1;
    }
    points.push({x:pointX,y:py,radius,event,index:i});
   }
  }
  ctx.globalAlpha=.2;ctx.strokeStyle='#f7f2dc';
  for (let n=0;n<3;n++) {
   ctx.beginPath();
   for (let px=0;px<=width;px+=8) {
    const py=height*.46+n*24+6*Math.sin(px/65+n-phase*.8);
    px?ctx.lineTo(px,py):ctx.moveTo(px,py);
   }
   ctx.stroke();
  }
  ctx.globalAlpha=1;
  const step=span<=80?10:span<=220?50:100;
  ctx.font='12px SimSun,serif';ctx.fillStyle='#697366';ctx.strokeStyle='#b4b5a8';
  for (let i=Math.max(0,Math.ceil(start));i<start+span && i<years.length;i++) {
   const year=years[i];if(Math.abs(year.year)%step!==0 && year.year!==-1)continue;
   const px=x(i);ctx.beginPath();ctx.moveTo(px,height-40);ctx.lineTo(px,height-33);ctx.stroke();
   ctx.fillText((year.year>0?'前':'')+Math.abs(year.year),px-12,height-14);
  }
  const sx=width/2;
  ctx.fillStyle='#27372f';ctx.beginPath();ctx.moveTo(sx-5,45);ctx.lineTo(sx+5,45);ctx.lineTo(sx,53);ctx.fill();
  const position=$('.river-position');
  position.style.left=Math.max(0,start)/years.length*100+'%';position.style.width=(Math.min(years.length,start+span)-Math.max(0,start))/years.length*100+'%';
  $('.river-prev').disabled=selected===0;$('.river-next').disabled=selected===years.length-1;
 }
 function resize() {
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
 canvas.addEventListener('pointerdown',event=>{
  pointerInside=true;wheelActive=true;$('.river-stage').focus({preventScroll:true});drag={x:event.clientX,y:event.clientY,center,point:pointAt(event)};moved=false;canvas.setPointerCapture(event.pointerId);
 });
 canvas.addEventListener('pointermove',event=>{
  if (!drag) return;
  const delta=event.clientX-drag.x;
  if (Math.abs(delta)>7) moved=true;
  if (moved) {canvas.style.cursor='grabbing';center=Math.max(0,Math.min(years.length-1,drag.center-delta/width*span));choose(center,false);}
 });
 canvas.addEventListener('pointerup',event=>{
  if (!drag)return;
  if(!moved && Math.abs(event.clientY-drag.y)<=7) {
   const point=drag.point;
   if(point)choose(point.index,false,point.event.id);
  }
  drag=null;canvas.style.cursor='pointer';
 });
 canvas.addEventListener('pointercancel',()=>{drag=null;canvas.style.cursor='pointer';pointerInside=false;});
 canvas.addEventListener('pointerenter',()=>{pointerInside=true;});
 canvas.addEventListener('pointerleave',()=>{pointerInside=false;});
 document.addEventListener('pointerdown',event=>{if(!$('.river-stage').contains(event.target))wheelActive=false;});
 $('.river-stage').addEventListener('focusout',event=>{if(!$('.river-stage').contains(event.relatedTarget))wheelActive=false;});
 canvas.addEventListener('wheel',event=>{
  if (!wheelActive || event.ctrlKey)return;
  const delta=Math.abs(event.deltaX)>Math.abs(event.deltaY)?event.deltaX:event.deltaY;
  if (!delta)return;
  event.preventDefault();
  const pixels=delta*(event.deltaMode===1?16:event.deltaMode===2?height:1);
  center=Math.max(0,Math.min(years.length-1,center+pixels/width*span));choose(center,false);
 },{passive:false});
 $('.river-stage').addEventListener('keydown',event=>{
  if (event.key==='ArrowLeft' || event.key==='ArrowRight') {event.preventDefault();choose(selected+(event.key==='ArrowLeft'?-1:1));}
 });
 $('.river-topic').onchange=event=>{topic=event.target.value;selectedEvent=null;detail();draw();};
 $('.river-prev').onclick=()=>choose(selected-1);$('.river-next').onclick=()=>choose(selected+1);
 $('.river-zoom').onchange=event=>{span=+event.target.value;draw();};
 $('.river-era').onchange=event=>choose(years.findIndex(year=>year.dynasty===event.target.value));
 $('.river-era-band').addEventListener('click',event=>{
  const button=event.target.closest('button[data-era]');
  if(button)choose(years.findIndex(year=>year.dynasty===button.dataset.era));
 });
 range.oninput=event=>choose(+event.target.value);
 const reducedMotion=matchMedia('(prefers-reduced-motion: reduce)');
 let visible=false,lastFrame=0;
 function animate(time) {
  animationFrame=0;if(!visible || document.hidden || reducedMotion.matches)return;
  if (time-lastFrame>=33) {if(!pointerInside && !drag)phase=time/1000;draw();lastFrame=time;}
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
