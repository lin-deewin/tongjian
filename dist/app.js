// All theme selectors share one preference without changing route or position.
function setTheme(value){
 const theme=[...document.querySelector('.theme-select').options].some(option=>option.value===value)?value:'light';
 document.documentElement.dataset.theme=theme;
 document.querySelectorAll('.theme-select').forEach(select=>{select.value=theme;});
}
setTheme(document.documentElement.dataset.theme);
document.querySelectorAll('.theme-select').forEach(select=>select.addEventListener('change',()=>{
 setTheme(select.value);
 try{localStorage.setItem('tongjian-theme',select.value);}catch(e){}
}));
window.addEventListener('storage',event=>{
 if(event.key==='tongjian-theme'||event.key===null)setTheme(event.newValue);
});

let yearVolumes={},fullSearchHits=[],searchChecked=0,searchComplete=true,resultLimit=50,searchWorker,searchTimer;let catalog=[],booksCache=new Map(),pendingBooks=new Map(),navigationId=0;let book,period='all',eventFilter='all',selected=403,readingIndex=0,readingSize=19,readerOpen=false,focusBefore;const $=s=>document.querySelector(s),esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));const cn=n=>{if(n===1)return '元';const d='零一二三四五六七八九';if(n<10)return d[n];if(n<100)return (n>=20?d[Math.floor(n/10)]:'')+'十'+(n%10?d[n%10]:'');return d[Math.floor(n/100)]+'百'+(n%100?(n%100<10?'零'+d[n%100]:n%100<20?'一'+cn(n%100):cn(n%100)):'');};const reign=y=>y.reignLabel||(y.dynasty||'周')+y.king+cn(y.reign)+'年';const yearLabel=y=>(y>0?'前':'')+Math.abs(y)+'年';const yearRange=(start,end)=>yearLabel(start)+' — '+yearLabel(end);

// These browsing labels are keyword suggestions from index titles, not source annotations.
const eventTypes=[['all','全部'],['major','要事'],['war','战争'],['power','权变'],['reform','改革'],['person','人物']];
const eventRules={war:/战争|之战|战役|交战|战败|战胜|大败|击败|攻|伐|围|征讨|讨伐|出兵|起兵|进军|入侵|军队|叛乱|平叛|兵变|破敌|破城|克城|军攻|灭国/,power:/继位|即位|登基|称帝|称王|篡|废立|废帝|废太子|政变|夺权|夺位|被杀|弑|诛|获封|封侯|分晋|代齐|实权|立为|立太子|立皇|专权|摄政|禅位|禅让|让位|合纵|连横/,reform:/变法|改革|新法|新政|改制|改元|制度|法令|法制|赋税|税制|均田|屯田|科举|度量衡|郡县|盐铁|治水|水利|修渠/,person:/去世|逝世|卒|病死|身亡|出生|用人|任用|任命|任职|拜相|为相|拜为|礼贤|事迹|报仇|游说|劝谏|进谏|谏言|辞官|辞职|罢官|罢免|召见|荐|论礼|论政|臣光曰|太史公曰/};
function eventCategories(title){const types=Object.keys(eventRules).filter(type=>eventRules[type].test(title));return types.length?types:['major'];}
function eventIndices(y){return y.titles.map((_,i)=>i).filter(i=>eventFilter==='all'||eventCategories(y.titles[i]).includes(eventFilter));}
function filtered(){const q=$('#search').value.trim().toLowerCase();const all=$('#searchScope').value==='all'&&q;const ys=all?fullSearchHits.filter(y=>!$('#recordedOnly').checked||y.recorded):book.years.filter(y=>(period==='all'||y.king===period)&&(!$('#recordedOnly').checked||y.recorded)&&(!q||[yearLabel(y.year),Math.abs(y.year),reign(y),...y.titles,y.search,...(y.bilingual||[]).map(p=>p.modern),...y.paragraphs.flatMap(p=>p.runs.filter(r=>r.kind==='note').map(r=>r.text))].join(' ').toLowerCase().includes(q))).map(y=>({...y,_volume:book.volume,_indexKind:book.indexKind,_titleReview:book.titleReview}));return ys.filter(y=>eventFilter==='all'||eventIndices(y).length);}
function render(){
 if(!book)return;
 renderVolumePeople();
 const results=filtered(),all=$('#searchScope').value==='all'&&$('#search').value.trim(),ys=all?results.slice(0,resultLimit):results;
 $('#annualPage').classList.toggle('annual-current-volume',!all);
 document.querySelectorAll('[data-event-filter]').forEach(button=>{const active=button.dataset.eventFilter===eventFilter;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
 document.querySelectorAll('[data-period]').forEach(button=>{const active=button.dataset.period===period;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});
 updateAnnualFilterState(results.length);
 $('#rail').innerHTML=ys.map(y=>`<button data-jump="${y.year}" data-volume="${y._volume}" class="${selected===y.year&&book.volume===y._volume?'active':''}">${yearLabel(y.year)}<i class="rail-dot ${y.recorded?'':'empty'}"></i></button>`).join('');
 let groupKey='';
 $('#chronicle').innerHTML=`<p class="year-summary" role="status">${all?`找到 ${results.length} 个年卷条目 · 已检索 ${searchChecked} / ${catalog.length} 卷${searchComplete?'':'，正在继续检索…'}`:`显示 ${ys.length} 年`}${eventFilter==='all'?'':` · ${eventTypes.find(t=>t[0]===eventFilter)[1]}`} · 点击事件阅读对应原文与白话。</p>`+ys.map(y=>{
  let group='';const key=y._volume+':'+y.king;
  if(groupKey!==key){groupKey=key;const meta=catalog.find(v=>v.volume===y._volume),groupYears=all?null:book.years.filter(x=>x.king===y.king);group=`<div class="group-heading"><h2>${esc(y.dynasty||'周')}${esc(y.king)}</h2><span>${all?esc(meta.title):yearRange(groupYears[0].year,groupYears.at(-1).year)}</span></div>`;}
  const indices=eventIndices(y),q=$('#search').value.trim().toLowerCase(),matches=all?indices.filter(i=>y.titles[i].toLowerCase().includes(q)):indices,shown=all?(matches.length?matches:indices).slice(0,3):indices;
  return group+`<article class="year-card ${y.recorded?'':'empty'}" id="year-${y._volume}-${y.year}"><button class="year-date" data-volume="${y._volume}" data-read="${y.year}" aria-label="阅读${yearLabel(y.year)}原文"><small>${y.year>0?'公元前':'公元'}</small><b>${Math.abs(y.year)}</b><span class="reign">${esc(reign(y))}</span></button><div class="year-events">${y.recorded?`<div class="event-top"><span class="category">${y._indexKind==='editorialSummary'?'':y._indexKind==='mixedSummary'?`事件标题 · 已重写 ${y._titleReview?.rewritten??0} / ${y._titleReview?.total??0} 条，其余待校对`:y._indexKind==='automaticSummary'?'待逐条重写 · 事件索引':y._indexKind==='translationExcerpt'?'白话节选 / 原文 · 事件索引':y.year===403?'当年记事 · 追叙 · 史论':'编年记事'}</span></div><div class="event-buttons">${shown.map(i=>`<button class="event-button" data-volume="${y._volume}" data-read="${y.year}" data-anchor="${y.anchors[i]??0}"><span class="event-number">${String(i+1).padStart(2,'0')}</span><span class="event-title">${esc(y.titles[i])}</span><span class="event-tags">${eventCategories(y.titles[i]).map(type=>`<span class="event-tag tag-${type}">${eventTypes.find(t=>t[0]===type)[1]}</span>`).join('')}</span></button>`).join('')}</div><p class="card-note">${y.paragraphs?.length??y.paragraphCount} 段原文 · ${y.bilingual?.filter(p=>!p.difference).length??y.pairCount} 组白话对照${eventFilter==='all'?'':` · 匹配 ${indices.length} / ${y.titles.length} 条索引`}${all&&indices.length>shown.length?' · 进入本年查看完整索引':''}${y.warning?' · 年头有版本差异':''}</p>`:`<span class="empty-message">本卷未单列此年记事</span><button class="read-link" data-volume="${y._volume}" data-read="${y.year}">查看 ↗</button>`}</div></article>`;
 }).join('')+(all&&results.length>resultLimit?'<button id="moreResults" class="more-results">显示更多结果 ↓</button>':'');
 if(!ys.length)$('#chronicle').innerHTML=`<div class="no-result" role="status">${all&&!searchComplete?`正在检索全书，已完成 ${searchChecked} / ${catalog.length} 卷…`:'没有匹配的年份或事件。可切换“全部”，或调整搜索和君主筛选。'}</div>`;
}
// The uploaded Hu EPUB has one stray U+E160 before “汉兵” in volume 9.
// Keep the source JSON unchanged and suppress this presentation-only artifact.
function visibleSourceText(text){return book?.volume===9?String(text).replaceAll('\uE160',''):String(text);}
function runsHtml(runs){return runs.map(r=>r.kind==='text'?esc(visibleSourceText(r.text)):`<button class="marker" data-note="${esc(visibleSourceText(r.text))}" aria-label="展开此处注释">〔注〕</button><span class="note">${esc(visibleSourceText(r.text))}</span>`).join('');}
function paragraphs(ps){return ps.map((p,i)=>`<p id="para-${i}" class="${/^(臣光曰|太史公曰)/.test(p.plain)?'commentary':''}">${runsHtml(p.runs)}</p>`).join('');}
let readingMode='compare',yearbookScroll=0,readerReturnState;
function enterReadingPage(){if(!readerOpen){yearbookScroll=window.scrollY;focusBefore=document.activeElement;}readerOpen=true;$('#annualPage').classList.add('hidden');$('#readerBackdrop').classList.remove('hidden');document.body.style.overflow='';}
function syncAnnualCanonical(){
 if(!document.documentElement.dataset.yearReader)return;
 const canonical=$('link[rel="canonical"]');if(!canonical)return;
 const root=new URL(document.baseURI).pathname;
 const path=location.pathname.startsWith(root)?location.pathname.slice(root.length):location.pathname;
 canonical.href=new URL(path,new URL('/',canonical.href)).href;
 const og=$('meta[property="og:url"]');if(og)og.content=canonical.href;
}
function updateRoute(hash,reading=true){
 let target=hash,changed=location.hash!==hash;
 if(document.documentElement.dataset.yearReader){
  const match=hash.match(/^#volume-(\d+)-year-(-?\d+)(?:-para-(\d+))?$/);
  const page=match?'year/'+(+match[2]>0?'bce':'ce')+'-'+Math.abs(+match[2])+'/':'reader.html';
  const url=new URL(page,document.baseURI);
  if(match){url.searchParams.set('volume',match[1]);if(match[3]!==undefined)url.searchParams.set('para',match[3]);}
  else url.hash=hash;
  target=url.pathname+url.search+url.hash;
  changed=location.pathname+location.search+location.hash!==target;
 }
 if(changed)history.pushState({reading},'',target);
 syncAnnualCanonical();
}

function setReadingMode(mode){readingMode=mode;$('#readerScroll').classList.toggle('mode-original',mode==='original');$('#readerScroll').classList.toggle('mode-modern',mode==='modern');$('#readerScroll').classList.toggle('mode-immersive',mode==='immersive');document.querySelectorAll('[data-reading-mode]').forEach(x=>x.classList.toggle('active',x.dataset.readingMode===mode));$('#showNotes').disabled=mode==='modern';$('#showNotes').closest('label').classList.toggle('dim',mode==='modern');}
function inlineGlyphsHtml(text){
 const token=/⟦glyph:([A-Za-z0-9._-]+)⟧/g;
 let html='',start=0,match;
 while((match=token.exec(text))){
  html+=esc(text.slice(start,match.index));
  html+=`<img class="translation-glyph" src="images/baiyang72/glyph/${match[1]}" alt="原书字形" loading="lazy">`;
  start=match.index+match[0].length;
 }
 return html+esc(text.slice(start));
}
// Translator explanations in either Chinese or western parentheses use a smaller Kai typeface.
function modernTextHtml(text){
 const lines=String(text||'').split('\n').map(t=>t.replace(/^\[\d+\]/,''));
 return lines.map(line=>{
  let result='',start=0,depth=0,opening=-1;
  for(let i=0;i<line.length;i++){
   if(line[i]==='（'||line[i]==='('){if(depth===0)opening=i;depth++;}
   else if((line[i]==='）'||line[i]===')')&&depth>0){
    depth--;
    if(depth===0){result+=inlineGlyphsHtml(line.slice(start,opening))+`<span class="translation-parenthesis">${inlineGlyphsHtml(line.slice(opening,i+1))}</span>`;start=i+1;}
   }
  }
  return result+inlineGlyphsHtml(line.slice(start));
 }).join('<br><br>');
}
function illustrationHtml(pic){
 if(!pic?.src)return '';
 const caption=pic.caption||'上传译本原书插图';
 const dimensions=Number.isInteger(pic.width)&&Number.isInteger(pic.height)?` width="${pic.width}" height="${pic.height}"`:'';
 return `<figure class="translation-illustration"><a href="${esc(pic.src)}" target="_blank" rel="noopener" aria-label="查看大图：${esc(caption)}"><img src="${esc(pic.src)}" alt="${esc(caption)}"${dimensions} loading="lazy"></a><figcaption>${esc(caption)}<span>上传译本原书插图 · 点击查看大图</span>${pic.placementNote?`<span>${esc(pic.placementNote)}</span>`:''}</figcaption></figure>`;
}
function translationIllustrations(pair){return (pair.illustrations||[]).map(illustrationHtml).join('');}
function yearIllustrations(y,after=null){return (y.yearIllustrations||[]).filter(pic=>(pic.afterParagraph??null)===after).map(illustrationHtml).join('');}
function unmatchedOriginals(y){if(!book.translationReplacement||!y.translationMissing.length)return '';return `<section class="unmatched-original original"><h3>尚未可靠对齐的胡注本原文</h3><p class="reading-hint">原文保持完整；对应的新译本白话在下方译本待核区按原书顺序保留。</p>${y.translationMissing.map(i=>`<p id="para-${i}">${runsHtml(y.paragraphs[i].runs)}</p>${yearIllustrations(y,i)}`).join('')}</section>`;}
function pairedRows(y){const unmatchedOriginals=book.translationReplacement?[]:y.translationMissing.map(i=>({huIndices:[i],modern:y.paragraphs[i].structural?'原书年号衔接，非记事正文。':'上传译本未提供或未能可靠对应本段白话。原文完整保留，等待补充校对。',kind:'record',missing:true}));const pairs=[...y.bilingual.filter(p=>!p.difference),...unmatchedOriginals].sort((a,b)=>a.huIndices[0]-b.huIndices[0]);return pairs.map((pair,k)=>`<section class="compare-row" tabindex="0" aria-label="第${k+1}组原文白话对照" data-pair="${k}"><div class="original-cell"><span class="row-index">${String(k+1).padStart(2,'0')}</span><span class="mobile-label">原文 · 胡三省注本</span>${pair.kind==='commentary'?'<span class="kind-label">史家评论 · 原文</span>':''}<div class="original ${$('#showNotes').checked?'':'hide-notes'}">${pair.huIndices.map(i=>`<p id="para-${i}">${runsHtml(y.paragraphs[i].runs)}</p>`).join('')}</div></div><div class="translation-cell"><span class="row-index">${String(k+1).padStart(2,'0')}</span><span class="mobile-label">白话 · 上传译本</span>${pair.kind==='commentary'?'<span class="kind-label">史家评论 · 白话译文</span>':''}${pair.dateWarning?`<span class="reading-hint">${esc(pair.dateWarning)}${pair.sourceYear?`译本记年：${yearLabel(pair.sourceYear)}。`:''}</span>`:''}${pair.reviewStatus==='check-source'?'<span class="reading-hint">两版字句有差异，建议核对原文。</span>':''}<p class="modern-text">${modernTextHtml(pair.modern)}</p>${translationIllustrations(pair)}</div></section>${pair.huIndices.map(i=>yearIllustrations(y,i)).join('')}`).join('');}
function versionDifferences(y){const differences=y.bilingual.filter(p=>p.difference);if(!differences.length)return '';return `<details class="source-differences"${book.translationReplacement?' open':''}><summary>译本中尚未与胡注本可靠对应 · ${differences.length} 段${book.translationReplacement?'':'，展开查看'}</summary><div class="difference-body">下列内容出现在上传的译本中，未在本年胡注本正文找到可靠对应。译本内容按来源顺序保留在此，供核对版本差异。${differences.map(p=>`<div class="difference-item">${p.sourceOriginal?`<span class="difference-label">译本所附古文</span><p class="serif">${esc(p.sourceOriginal)}</p>`:""}<span class="difference-label">${esc(p.sourceLabel||"译本白话")}</span><p class="modern-text">${modernTextHtml(p.modern)}</p></div>`).join('')}</div></details>`;}
// A temporary border around the entire original/translation content group.
function flashReaderTarget(row){
 row.classList.add('active','event-target-flash');
 const finish=event=>{
  if(event.target!==row||!['reader-target-border-pulse','reader-target-border-still'].includes(event.animationName))return;
  row.classList.remove('event-target-flash','active');
  row.removeEventListener('animationend',finish);
 };
 row.addEventListener('animationend',finish);
}
function positionReaderEvent(target,row){
 const align=()=>{
  if(typeof getComputedStyle==='function'){
   if(!target.isConnected||!readerOpen)return;
   const content=$('#readerContent');
   content.style.setProperty('--reader-anchor-tail','0px');
   const margin=parseFloat(getComputedStyle(target).scrollMarginTop)||0;
   const destination=window.scrollY+target.getBoundingClientRect().top-margin;
   const available=document.documentElement.scrollHeight-window.innerHeight;
   let tail=Math.max(0,Math.ceil(destination-available)+1);
   content.style.setProperty('--reader-anchor-tail',tail+'px');
   // Short years can absorb the first spacer in the reader's minimum height.
   if(document.documentElement.scrollHeight-window.innerHeight<destination){
    tail+=Math.ceil(window.innerHeight-margin-(content.getBoundingClientRect().bottom-target.getBoundingClientRect().top));
    content.style.setProperty('--reader-anchor-tail',tail+'px');
   }
  }
  target.scrollIntoView({block:'start',behavior:'instant'});
  flashReaderTarget(row);updateProgress();
 };
 // Reader tools and people labels finish their DOM updates before the next frame.
 if(typeof getComputedStyle==='function')requestAnimationFrame(align);else align();
}
function readYear(year,anchor=null,updateHistory=true){hidePeoplePage();enterReadingPage();selected=year;readingIndex=book.years.findIndex(y=>y.year===year);const y=book.years[readingIndex];$('#readerYear').value=year;$('#readerContent').style.setProperty('--reader-anchor-tail','0px');$('#readerContent').innerHTML=`<div class="reader-inner"><div class="reader-title"><div class="eyebrow">${yearLabel(y.year)} · ${esc(bookLabel())}</div><h2>${esc(reign(y))}</h2><p><a href="year/${y.year>0?'bce':'ce'}-${Math.abs(y.year)}/#volume-${book.volume}-year-${y.year}${anchor!==null?'-para-'+anchor:''}">本年独立阅读页 ↗</a></p>${y.recorded?'':'<div class="reign-line">本卷未单列此年记事</div>'}</div>${y.headingRuns?`<div class="original source-heading ${$('#showNotes').checked?'':'hide-notes'}"><p>${runsHtml(y.headingRuns)}</p></div>`:''}${y.warning?`<div class="year-note">版本提示：${esc(y.warning)}</div>`:''}${y.translationWarning?`<div class="year-note">${esc(y.translationWarning)}</div>`:''}${y.noteWarning?`<div class="year-note">${esc(y.noteWarning)}</div>`:''}${yearParts(y)}${yearIllustrations(y)}${y.translationMissing.some(i=>!y.paragraphs[i].structural)?(book.translationReplacement?'<div class="year-note">部分原文尚未与新译本可靠对齐；完整白话仍按原书顺序保留在下方待核区。</div>':'<div class="year-note">本年部分段落缺少可靠对应译文，右栏已逐段标注；未使用生成译文。</div>'):''}${y.year===403?'<div class="year-note">本年包含智氏覆亡、晋阳之战等更早事件的追叙，以及史家评论。这里保留胡注本正文次序，不将追叙改列为当年事件。</div>':''}${y.recorded?`<div class="column-labels"><div class="original-label">原文<small>司马光 · 胡三省注本</small></div><div class="translation-label">白话译文<small>上传译本</small></div></div><article class="comparison">${pairedRows(y)}</article>${unmatchedOriginals(y)}${versionDifferences(y)}${unparsedTranslation(y)}`:`<p class="empty-reading">胡注本未在本卷单列这一年的记事。可切换前后年份继续阅读。</p>${unmatchedOriginals(y)}${versionDifferences(y)}`}${y.after.length?`<div class="source-transition original ${$('#showNotes').checked?'':'hide-notes'}"><span class="reading-hint">原书衔接 · 下一君主年号</span>${y.after.map(t=>`<p>${esc(t)}</p>`).join('')}</div>`:''}</div>`;setReadingMode(readingMode);$('#progressBar').style.width='0';updateYearNavigation();document.querySelectorAll('[data-jump]').forEach(b=>b.classList.toggle('active',+b.dataset.jump===year));const target=anchor===null?null:$('#para-'+anchor),targetRow=target?.closest('.compare-row');if(!targetRow)window.scrollTo({top:0,behavior:'instant'});$('#closeReader').focus({preventScroll:true});document.documentElement.classList?.remove('reader-route-pending');if(updateHistory)updateRoute('#volume-'+book.volume+'-year-'+year+(anchor!==null?'-para-'+anchor:''));decoratePeople();updateProgress();if(targetRow)positionReaderEvent(target,targetRow);if(!updateHistory)restorePeopleHistory();}
function closeReader(updateHistory=true){hidePeoplePage();if(updateHistory&&readerReturnState){const state=readerReturnState;if(book!==state.book)applyBook(state.book);period=state.period;eventFilter=state.eventFilter;$('#search').value=state.search;$('#searchScope').value=state.scope;$('#recordedOnly').checked=state.recordedOnly;yearbookScroll=state.scroll;render();}readerReturnState=null;readerOpen=false;document.title='资治通鉴 · '+bookLabel();$('#readerBackdrop').classList.add('hidden');$('#annualPage').classList.remove('hidden');document.body.style.overflow='';if(updateHistory)updateRoute('#volume-'+book.volume,false);focusBefore?.focus({preventScroll:true});window.scrollTo({top:yearbookScroll,behavior:'instant'});}
function volumeIntro(updateHistory=true){hidePeoplePage();enterReadingPage();$('#readerContent').style.setProperty('--reader-anchor-tail','0px');setReadingMode('original');$('#readerContent').innerHTML=`<div class="reader-title"><div class="eyebrow">卷首 · 原文</div><h2>${esc(bookLabel())}</h2><div class="reign-line">${esc(book.fullTitle||book.title)}</div></div><article class="original ${$('#showNotes').checked?'':'hide-notes'}">${paragraphs(book.intro)}</article>`;window.scrollTo({top:0,behavior:'instant'});$('#readerPosition').textContent='卷首说明';$('#prevYear').disabled=true;$('#nextYear').disabled=false;readingIndex=-1;$('#closeReader').focus({preventScroll:true});if(updateHistory)updateRoute('#volume-'+book.volume+'-intro');updateProgress();if(!updateHistory)restorePeopleHistory();}
$('#showNotes').onchange=()=>document.querySelectorAll('.original').forEach(x=>x.classList.toggle('hide-notes',!$('#showNotes').checked));$('#smaller').onclick=()=>{readingSize=Math.max(15,readingSize-1);document.documentElement.style.setProperty('--reading-size',readingSize+'px')};$('#larger').onclick=()=>{readingSize=Math.min(28,readingSize+1);document.documentElement.style.setProperty('--reading-size',readingSize+'px')};$('#search').oninput=searchChanged;$('#recordedOnly').onchange=render;$('#readerYear').onchange=e=>readYear(+e.target.value);$('#prevYear').onclick=()=>stepYear(-1);$('#nextYear').onclick=()=>stepYear(1);$('#closeReader').onclick=()=>returnFromReader();$('#volumeIntro').onclick=()=>{if(book)volumeIntro()};$('#about').onclick=()=>{fetch('coverage.json?v=20261017-release1').then(r=>r.json()).then(c=>{$('#coverageSummary').textContent=`已收录${c.volumes}卷、${c.uniqueYears}个年份，${c.sourceBody}段原文正文。已有${c.matchedOriginal}段原文对应上传白话，${c.unmatchedOriginal}段缺译或待核对。阅读页保留新版译本的插图与地图。`;}).catch(()=>{});$('#infoBackdrop').classList.remove('hidden');$('#closeInfo').focus()};$('#closeInfo').onclick=()=>{$('#infoBackdrop').classList.add('hidden');$('#about').focus()};$('#infoBackdrop').onclick=e=>{if(e.target===$('#infoBackdrop'))$('#closeInfo').click()};function updateProgress(){if(!readerOpen)return;const start=$('#readerContent').getBoundingClientRect().top+window.scrollY;const available=document.documentElement.scrollHeight-window.innerHeight-start;const progress=available>0?Math.max(0,Math.min(100,(window.scrollY-start)/available*100)):100;$('#progressBar').style.width=progress+'%';}window.addEventListener('scroll',updateProgress,{passive:true});window.addEventListener('popstate',()=>routeFromHash());window.addEventListener('hashchange',()=>routeFromHash());

document.addEventListener('click',e=>{const row=e.target.closest('.compare-row');if(row){document.querySelectorAll('.compare-row').forEach(x=>x.classList.toggle('active',x===row));}const b=e.target.closest('button');if(!b||!book)return;if(b.dataset.readingMode){setReadingMode(b.dataset.readingMode);}if(b.dataset.eventFilter){eventFilter=b.dataset.eventFilter;resultLimit=50;render()}if(b.dataset.dynasty){const v=catalog.find(v=>v.dynasty===b.dataset.dynasty);if(v)changeVolume(v.volume)}if(b.dataset.period){period=b.dataset.period;document.querySelectorAll('[data-period]').forEach(x=>x.classList.toggle('active',x===b));render()}if(b.dataset.jump){selected=+b.dataset.jump;document.querySelectorAll('[data-jump]').forEach(x=>x.classList.toggle('active',x===b));$('#year-'+b.dataset.volume+'-'+selected)?.scrollIntoView({behavior:'smooth',block:'center'})}if(b.dataset.read)openYear(+(b.dataset.volume||book.volume),+b.dataset.read,b.dataset.anchor!==undefined?+b.dataset.anchor:null);if(b.id==='moreResults'){resultLimit+=50;render()}if(b.dataset.note){const next=b.nextElementSibling;if(next){next.style.display=next.style.display==='inline'?'':'inline';b.setAttribute('aria-expanded',next.style.display==='inline'?'true':'false')}}});
document.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.classList.contains('compare-row')){e.preventDefault();document.querySelectorAll('.compare-row').forEach(x=>x.classList.toggle('active',x===e.target));}if(e.key==='Escape'){if(!$('#infoBackdrop').classList.contains('hidden'))$('#closeInfo').click();else if(!$('#peoplePage').classList.contains('hidden'))returnFromPeople();else if(readerOpen)returnFromReader()}if(e.key==='Tab'){const modal=!$('#infoBackdrop').classList.contains('hidden')?$('#infoBackdrop'):null;if(modal){const fs=[...modal.querySelectorAll('button:not(:disabled),input:not(:disabled),select,a,[tabindex="0"],summary')].filter(el=>el.getClientRects().length);if(e.shiftKey&&document.activeElement===fs[0]){e.preventDefault();fs.at(-1).focus()}else if(!e.shiftKey&&document.activeElement===fs.at(-1)){e.preventDefault();fs[0].focus()}}}});

function reportError(error){document.documentElement.classList?.remove('reader-route-pending');console.error(error);const target=readerOpen?$('#readerContent'):$('#chronicle');target.innerHTML='<div class="error">内容加载失败，请刷新重试。卷次与年份已保留在地址中。</div>';}
function applyTranslationSupplement(data,overlay){
 if(overlay.schemaVersion!==1 || overlay.volume!==data.volume)throw Error('Translation supplement version mismatch');
 const years=new Map(data.years.map(y=>[y.year,y]));
 const seen=new Set(data.years.flatMap(y=>y.bilingual.flatMap(p=>p.huIndices.map(i=>y.year+':'+i))));
 for(const entry of overlay.entries){
  if(entry.provenance!=='uploaded-recovery')throw Error('Unsupported translation provenance');
  const y=years.get(entry.year);
  if(!y || !entry.huIndices.length || entry.huIndices.length!==entry.sourceTexts.length)throw Error('Translation supplement target mismatch');
  entry.huIndices.forEach((i,k)=>{if(!y.paragraphs[i] || y.paragraphs[i].plain!==entry.sourceTexts[k] || seen.has(y.year+':'+i))throw Error('Translation supplement source changed');seen.add(y.year+':'+i)});
  const source=years.get(entry.sourceYear), find=()=>source?.bilingual.find(p=>p.sourceOriginal===entry.sourceOriginal && p.modern===(entry.sourceGroupModern||entry.modern));
  if(entry.action==='extend'){
   const pair=find();if(source!==y || !pair || pair.difference)throw Error('Translation extension mismatch');
   pair.huIndices=[...pair.huIndices,...entry.huIndices].sort((a,b)=>a-b);pair.recoverySource=entry.provenance;continue;
  }
  if(entry.removeDifference){const pair=find();if(!pair?.difference)throw Error('Translation difference mismatch');source.bilingual.splice(source.bilingual.indexOf(pair),1)}
  const pair={huIndices:entry.huIndices,sourceOriginal:entry.sourceOriginal,modern:entry.modern,score:entry.score,kind:entry.kind,difference:false,reviewStatus:entry.reviewStatus,provenance:entry.provenance,translationFiles:entry.files||[]};
  if(entry.provenance==='uploaded-recovery' && entry.sourceYear!==entry.year){pair.sourceYear=entry.sourceYear;pair.dateWarning='上传译本此段记年与胡注本当前位置不同，按原文定位保留对照，年份待校对。'}
  y.bilingual.push(pair);
 }
 for(const y of data.years){
  const covered=new Set(y.bilingual.flatMap(p=>p.huIndices));y.translationMissing=y.paragraphs.map((_,i)=>i).filter(i=>!covered.has(i));
  if(data.volume===28)y.translationWarning='上传本卷混有白话和仅古文部分；已恢复可核对的白话，古文不当作白话。';
 }
 return data;
}
async function sha256Hex(text){
 if(!globalThis.crypto?.subtle)return sha256Fallback(text);
 const bytes=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(text));
 return Array.from(new Uint8Array(bytes),byte=>byte.toString(16).padStart(2,'0')).join('');
}
// HTTP LAN previews lack Web Crypto; retain the same SHA-256 integrity checks.
function sha256Fallback(text){
 const input=new TextEncoder().encode(text),length=input.length;
 const data=new Uint8Array(Math.ceil((length+9)/64)*64);data.set(input);data[length]=128;
 const view=new DataView(data.buffer);view.setUint32(data.length-8,Math.floor(length/0x20000000));view.setUint32(data.length-4,(length*8)>>>0);
 const k=[0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2];
 const h=[0x6a09e667,0xbb67ae85,0x3c6ef372,0xa54ff53a,0x510e527f,0x9b05688c,0x1f83d9ab,0x5be0cd19],w=new Uint32Array(64),rot=(x,n)=>(x>>>n)|(x<<(32-n));
 for(let offset=0;offset<data.length;offset+=64){
  for(let i=0;i<16;i++)w[i]=view.getUint32(offset+i*4);
  for(let i=16;i<64;i++){const x=w[i-15],y=w[i-2];w[i]=(w[i-16]+(rot(x,7)^rot(x,18)^(x>>>3))+w[i-7]+(rot(y,17)^rot(y,19)^(y>>>10)))>>>0;}
  let [a,b,c,d,e,f,g,j]=h;
  for(let i=0;i<64;i++){const t1=(j+(rot(e,6)^rot(e,11)^rot(e,25))+((e&f)^(~e&g))+k[i]+w[i])>>>0,t2=((rot(a,2)^rot(a,13)^rot(a,22))+((a&b)^(a&c)^(b&c)))>>>0;j=g;g=f;f=e;e=(d+t1)>>>0;d=c;c=b;b=a;a=(t1+t2)>>>0;}
  [a,b,c,d,e,f,g,j].forEach((value,i)=>{h[i]=(h[i]+value)>>>0;});
 }
 return h.map(value=>value.toString(16).padStart(8,'0')).join('');
}
function validReplacementImage(pic){
 if(!pic||typeof pic.src!=='string'||typeof pic.caption!=='string')return false;
 const path=pic.src.split('/');
 return path[0]==='images'&&path[1]==='baiyang72'&&path.length>2&&path.every(part=>/^[A-Za-z0-9._-]+$/.test(part)&&part!=='.'&&part!=='..');
}
async function applyTranslationReplacement(data,replacement,baseRaw){
 if(replacement?.schemaVersion!==1||replacement.volume!==data.volume||!Array.isArray(replacement.years)||typeof replacement.translationSource!=='string'||!replacement.translationSource.trim())throw Error('Translation replacement version mismatch');
 if(typeof replacement.baseSHA256!=='string'||replacement.baseSHA256!==await sha256Hex(baseRaw))throw Error('Translation replacement source changed');
 const canonicalYears=new Map(data.years.map(y=>[y.year,y]));
 if(replacement.years.length!==canonicalYears.size)throw Error('Translation replacement year coverage mismatch');
 const replacements=[];
 const usedYears=new Set();
 for(const entry of replacement.years){
  const y=canonicalYears.get(entry?.year);
  if(!y||usedYears.has(entry.year)||typeof entry.sourceParagraphSHA256!=='string'||!Array.isArray(entry.bilingual)||!Array.isArray(entry.translationMissing)||!Array.isArray(entry.yearIllustrations))throw Error('Translation replacement target mismatch');
  usedYears.add(entry.year);
  if(entry.sourceParagraphSHA256!==await sha256Hex(JSON.stringify(y.paragraphs)))throw Error('Translation replacement paragraph source changed');
  if(entry.translationHeaders!==undefined&&(entry.translationHeaders===null||typeof entry.translationHeaders!=='object'))throw Error('Translation replacement headers mismatch');
  if(entry.translationWarning!==undefined&&entry.translationWarning!==null&&typeof entry.translationWarning!=='string')throw Error('Translation replacement warning mismatch');
  if(entry.yearIllustrations.some(pic=>!validReplacementImage(pic)))throw Error('Translation replacement image mismatch');
  const covered=new Set();
  for(const pair of entry.bilingual){
   if(!pair||typeof pair.modern!=='string'||!Array.isArray(pair.huIndices)||/柏杨曰\s*[：:]/.test(pair.modern))throw Error('Translation replacement pair mismatch');
   for(const index of pair.huIndices){
    if(!Number.isInteger(index)||index<0||index>=y.paragraphs.length||covered.has(index))throw Error('Translation replacement duplicate or invalid paragraph');
    covered.add(index);
   }
  }
  const missing=new Set(entry.translationMissing);
  if(missing.size!==entry.translationMissing.length||[...missing].some(index=>!Number.isInteger(index)||index<0||index>=y.paragraphs.length||covered.has(index)))throw Error('Translation replacement missing paragraph mismatch');
  if(missing.size+covered.size!==y.paragraphs.length)throw Error('Translation replacement paragraph coverage mismatch');
  replacements.push({y,entry});
 }
 if(usedYears.size!==canonicalYears.size)throw Error('Translation replacement incomplete');
 for(const {y,entry} of replacements){
  y.bilingual=entry.yearIllustrations.length?entry.bilingual.map(pair=>{const replacementPair={...pair};delete replacementPair.illustrations;return replacementPair;}):entry.bilingual;
  y.translationMissing=entry.translationMissing;
  y.translationHeaders=entry.translationHeaders||{};
  y.translationWarning=entry.translationWarning||'';
  y.yearIllustrations=entry.yearIllustrations;
 }
 data.translationSource=replacement.translationSource;
 data.translationReplacement={schemaVersion:1,sourceSHA256:replacement.sourceSHA256};
 return data;
}
async function loadVolume(volume){if(booksCache.has(volume))return booksCache.get(volume);if(!catalog.some(v=>v.volume===volume))throw Error('Unknown volume');if(!pendingBooks.has(volume))pendingBooks.set(volume,(async()=>{const response=await fetch('volume'+volume+'.json?v=20261017-release1');if(!response.ok)throw Error('Cannot load volume');const raw=await response.text();const data=JSON.parse(raw);const meta=catalog.find(v=>v.volume===volume),replacement=meta?.translationReplacement;if(replacement){const replacementResponse=await fetch(replacement+'?v=20261017-release1');if(!replacementResponse.ok)throw Error('Cannot load translation replacement');await applyTranslationReplacement(data,await replacementResponse.json(),raw);}else if(meta?.translationSupplement){const response=await fetch(meta.translationSupplement+'?v=20261017-release1');if(!response.ok)throw Error('Cannot load translation supplement');applyTranslationSupplement(data,await response.json());}if(meta?.illustrations){const picturesResponse=await fetch(meta.illustrations+'?v=20261017-release1');if(!picturesResponse.ok)throw Error('Cannot load illustrations');const pictures=await picturesResponse.json();if(pictures.volume!==volume||!Array.isArray(pictures.years))throw Error('Invalid illustrations');data.years.forEach(y=>y.yearIllustrations=[]);for(const entry of pictures.years){const target=data.years.find(y=>y.year===entry.year);if(!target||!Array.isArray(entry.images)||entry.images.some(pic=>!validReplacementImage(pic)||(pic.afterParagraph!==null&&(!Number.isInteger(pic.afterParagraph)||pic.afterParagraph<0||pic.afterParagraph>=target.paragraphs.length))))throw Error('Invalid illustration placement');target.yearIllustrations=entry.images;}}booksCache.set(volume,data);if(booksCache.size>5){const oldest=[...booksCache.keys()].find(v=>v!==volume&&v!==book?.volume);if(oldest!==undefined)booksCache.delete(oldest)}return data;})().finally(()=>pendingBooks.delete(volume)));return pendingBooks.get(volume);}
function bookLabel(){return catalog.find(v=>v.volume===book.volume)?.title||book.title;}
function applyBook(data){
 const changed=book?.volume!==data.volume;book=data;
 if(changed){period='all';yearbookScroll=0;selected=book.years[0].year;$('#search').value='';}
 $('#volumeSelect').value=book.volume;
 window.refreshYearbookVolumeLabel?.();
 $('#volumeTitle').textContent=bookLabel()+' · 逐年年表';
 $('#volumeCount').textContent='第 '+book.volume+' / '+catalog.length+' 卷';
 const volumeIndex=catalog.findIndex(v=>v.volume===book.volume);
 $('#prevVolume').disabled=volumeIndex<=0;$('#nextVolume').disabled=volumeIndex===catalog.length-1;
 $('#readerBackdrop .reader-head .label').textContent=bookLabel()+' / 原文与白话对读';
 $('#readerYear').innerHTML=book.years.map(y=>`<option value="${y.year}">${yearLabel(y.year)}</option>`).join('');
 const kings=[...new Set(book.years.map(y=>y.king))];
 $('#periods').innerHTML=`<button data-period="all">全部君主</button>`+kings.map(king=>`<button data-period="${esc(king)}">${esc(king)}</button>`).join('');
 $('#mobilePeriod').innerHTML='<option value="all">全部君主</option>'+kings.map(king=>`<option value="${esc(king)}">${esc(king)}</option>`).join('');
 render();
}
function updateAnnualFilterState(count){
 $('#mobilePeriod').value=period;
 const active=Number(eventFilter!=='all')+Number($('#recordedOnly').checked);
 $('#annualFilterTrigger').classList.toggle('has-filter',active>0);
 $('#annualFilterCount').textContent=active;
 $('#annualFilterResults').textContent=count+' 年';
 const labels=[period!=='all'?period:'',eventFilter!=='all'?eventTypes.find(t=>t[0]===eventFilter)[1]:'',$('#recordedOnly').checked?'仅有记事年份':''].filter(Boolean);
 $('#annualFilterStatus').classList.toggle('hidden',!labels.length);
 $('#annualFilterStatus').textContent=labels.length?'当前筛选：'+labels.join(' · '):'';
}
function stepVolume(direction){const i=catalog.findIndex(v=>v.volume===book?.volume),next=catalog[i+direction];if(i>=0&&next)changeVolume(next.volume);}

async function openYear(volume,year,anchor=null,updateHistory=true){if(!readerOpen&&book)readerReturnState={book,period,eventFilter,search:$('#search').value,scope:$('#searchScope').value,recordedOnly:$('#recordedOnly').checked,scroll:window.scrollY};const nav=++navigationId;try{const data=await loadVolume(volume);if(nav!==navigationId)return;if(!data.years.some(y=>y.year===year))throw Error('Unknown year');if(book!==data)applyBook(data);readYear(year,anchor,updateHistory);}catch(error){if(nav===navigationId)reportError(error);}}
async function changeVolume(volume,updateHistory=true){const nav=++navigationId;try{const data=await loadVolume(volume);if(nav!==navigationId)return;applyBook(data);closeReader(false);window.scrollTo({top:0,behavior:'instant'});if(updateHistory)updateRoute('#volume-'+volume);}catch(error){if(nav===navigationId)reportError(error);}}
function updateYearNavigation(){const hasPrev=readingIndex>0||book.volume>catalog[0].volume;const hasNext=readingIndex<book.years.length-1||book.volume<catalog.at(-1).volume;$('#prevYear').disabled=!hasPrev;$('#nextYear').disabled=!hasNext;$('#prevYear').textContent=readingIndex===0&&hasPrev?(catalog.find(v=>v.volume===book.volume-1)?.end===selected?'← 本年上篇':'← 上一年 · 上一卷'):'← 上一年';$('#nextYear').textContent=readingIndex===book.years.length-1&&hasNext?(catalog.find(v=>v.volume===book.volume+1)?.start===selected?'本年续篇 →':'下一年 · 下一卷 →'):'下一年 →';$('#readerPosition').textContent='卷 '+book.volume+' · '+(readingIndex+1)+' / '+book.years.length+' 年';document.title=yearLabel(book.years[readingIndex].year)+' · 资治通鉴';}
async function stepYear(direction){const next=readingIndex+direction;if(next>=0&&next<book.years.length){readYear(book.years[next].year);return;}const volume=book.volume+direction;const meta=catalog.find(v=>v.volume===volume);if(meta)await openYear(volume,direction<0?meta.end:meta.start);}
async function routeFromHash(){syncAnnualCanonical();let hash=location.hash;
 const annual=location.pathname.match(/\/year\/(bce|ce)-(\d+)\/$/);
 if(annual){
  const params=new URLSearchParams(location.search),year=(annual[1]==='bce'?1:-1)*Number(annual[2]);
  const legacy=hash.match(/^#volume-(\d+)-year-(-?\d+)(?:-para-(\d+))?$/);
  if(!hash||legacy){
   const volume=params.get('volume')||legacy?.[1]||yearVolumes[year]?.[0];
   const para=legacy?.[3]??params.get('para');
   if(volume&&/^\d+$/.test(String(volume))&&(para===null||para===undefined||/^\d+$/.test(para))){
    hash=`#volume-${volume}-year-${year}${para!=null?'-para-'+para:''}`;
    if(location.hash){params.set('volume',String(volume));if(para!=null)params.set('para',para);history.replaceState(history.state,'',location.pathname+'?'+params.toString());}
   }
  }
 }
if(await routePeopleHash(hash))return;hidePeoplePage();let m=hash.match(/^#volume-(\d+)-year-(-?\d+)(?:-para-(\d+))?$/);if(m){await openYear(+m[1],+m[2],m[3]!==undefined?+m[3]:null,false);return;}m=hash.match(/^#year-(-?\d+)$/);if(m){const meta=catalog.find(v=>v.start>=+m[1]&&v.end<=+m[1]);if(meta){await openYear(meta.volume,+m[1],null,false);return;}}m=hash.match(/^#volume-(\d+)(-intro)?$/);const volume=m?+m[1]:1;const nav=++navigationId;try{const data=await loadVolume(volume);if(nav!==navigationId)return;applyBook(data);if(m?.[2]||hash==='#volume-intro')volumeIntro(false);else{closeReader(false);document.title='资治通鉴 · '+book.title;restorePeopleHistory();}}catch(error){if(nav===navigationId)reportError(error);}}
function yearParts(y){const volumes=yearVolumes[y.year]||[book.volume];if(volumes.length<2)return '';return `<div class="year-note">本年记事分见 ${volumes.length} 卷：${volumes.map(v=>v===book.volume?`第${v}卷（当前）`:`<button class="part-link" data-volume="${v}" data-read="${y.year}">第${v}卷 →</button>`).join(' · ')}。按原书卷次分别保留，可接续阅读。</div>`;}
function unparsedTranslation(y){if(!y.translationBlocks?.length)return '';return `<details class="source-differences"><summary>译本所载内容待核对 · 展开原文件</summary><div class="difference-body">${esc(y.translationWarning||'这部分原文与白话的边界待核对，保留源内容。')}${y.translationBlocks.map(t=>`<p>${esc(t)}</p>`).join('')}</div></details>`;}
let searchId=0;function searchChanged(){const id=++searchId;clearTimeout(searchTimer);resultLimit=50;const q=$('#search').value.trim().toLowerCase();if($('#searchScope').value!=='all'||!q){fullSearchHits=[];searchComplete=true;searchWorker?.postMessage({type:'cancel'});render();return;}fullSearchHits=[];searchComplete=false;searchChecked=0;render();searchTimer=setTimeout(()=>{if(id!==searchId)return;if(!searchWorker){try{searchWorker=new Worker('search-worker.js?v=20261017-release1');searchWorker.onmessage=e=>{const m=e.data;if(m.id!==searchId)return;if(m.error){searchComplete=true;$('#chronicle').innerHTML='<div class="error">全书搜索部分文件加载失败，请重试。</div>';return;}fullSearchHits=m.hits;searchChecked=m.checked;searchComplete=m.complete;render();};searchWorker.onerror=()=>{$('#chronicle').innerHTML='<div class="error">全书搜索暂不可用，可切换本卷搜索。</div>';};}catch(error){reportError(error);return;}}searchWorker.postMessage({type:'search',id,q,volumes:catalog.map(v=>v.volume)});},350);}
function selectOptions(){
 const dynasties=[...new Set(catalog.map(v=>v.dynasty||'周'))];
 const datedYear=y=>(y>0?'前':'公元')+Math.abs(y)+'年';
 const directory=$('#volumeDirectory'), groups=$('#volumeDirectoryGroups');
 if(directory && groups){
  groups.innerHTML=dynasties.map((d,i)=>{
   const volumes=catalog.filter(v=>(v.dynasty||'周')===d);
   return `<details data-chronicle="${i+1}"><summary>${esc(d)}纪 <small>卷${volumes[0].volume}—${volumes.at(-1).volume}</small></summary><div class="reader-volume-grid">${volumes.map(v=>`<a href="#volume-${v.volume}" data-directory-volume="${v.volume}"><b>${esc(v.title.replace('【',' · ').replace('】',''))}</b><small>${datedYear(v.start)}—${datedYear(v.end)}</small></a>`).join('')}</div></details>`;
  }).join('');
  const trigger=$('#currentVolumeButton');
  trigger.onclick=()=>{
   directory.open=!directory.open;
   if(directory.open){const current=groups.querySelector(`[data-directory-volume="${$('#volumeSelect').value}"]`);if(current)current.closest('details').open=true;}
   trigger.setAttribute('aria-expanded',String(directory.open));
  };
  directory.addEventListener('toggle',()=>trigger.setAttribute('aria-expanded',String(directory.open)));
  const requested=new URLSearchParams(location.search).get('catalog');
  if(requested){directory.open=true;const group=groups.querySelector(`[data-chronicle="${/^\d+$/.test(requested)?requested:1}"]`);if(group)group.open=true;requestAnimationFrame(()=>directory.scrollIntoView({block:'start'}));}
  groups.onclick=event=>{const link=event.target.closest('[data-directory-volume]');if(!link)return;event.preventDefault();directory.open=false;$('#volumeSelect').value=link.dataset.directoryVolume;$('#volumeSelect').dispatchEvent(new Event('change',{bubbles:true}));trigger.focus({preventScroll:true});};
 }

 $('#volumeSelect').innerHTML=dynasties.map(d=>`<optgroup label="${esc(d)}">${catalog.filter(v=>(v.dynasty||'周')===d).map(v=>`<option value="${v.volume}" data-title="${esc(v.title.replace('【',' · ').replace('】',''))}" data-years="${datedYear(v.start)}—${datedYear(v.end)}">${esc(v.title.replace('【',' · ').replace('】',''))}（${datedYear(v.start)}—${datedYear(v.end)}）</option>`).join('')}</optgroup>`).join('');
}
$('#prevVolume').onclick=()=>stepVolume(-1);
$('#nextVolume').onclick=()=>stepVolume(1);
$('#mobilePeriod').onchange=e=>{period=e.target.value;render();};
$('#annualFilterReset').onclick=()=>{eventFilter='all';$('#recordedOnly').checked=false;resultLimit=50;render();};
$('#jumpYearForm').onsubmit=e=>{e.preventDefault();const value=Number($('#jumpYearInput').value);if(!Number.isInteger(value)||value<1){$('#jumpYearStatus').textContent='请输入大于0的年份。';return;}const key=$('#jumpYearEra').value==='bce'?value:-value;const volumes=yearVolumes[key];if(!volumes?.length){$('#jumpYearStatus').textContent='收录前403年至959年，公历没有0年。';return;}$('#jumpYearStatus').textContent='';$('#annualYearJump').open=false;openYear(volumes[0],key);};
$('#searchScope').onchange=searchChanged;$('#volumeSelect').onchange=e=>changeVolume(+e.target.value);
fetch('catalog.json?v=20261017-release1').then(r=>{if(!r.ok)throw Error('Cannot load catalog');return r.json()}).then(async data=>{catalog=data.volumes;yearVolumes=data.yearVolumes||{};await loadPeopleIndex();selectOptions();return routeFromHash();}).catch(reportError);
