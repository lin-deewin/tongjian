// Local reading annotations. Text offsets are checked against the source before restoration.
(()=>{
 const KEY='tongjian-annotations-v2',colors={yellow:'麦黄',green:'竹青',blue:'浅蓝',pink:'藕粉'};
 const content=document.querySelector('#readerContent'),surface=document.querySelector('#readerScroll');
 const activeContent=()=>readingMode==='vertical'?document.querySelector('#traditionalReader article'):content;
 let items=[],pending=null,editing=null,libraryType='bookmark',libraryQuery='';
 function load(){try{const value=JSON.parse(localStorage.getItem(KEY)||'[]');return Array.isArray(value)?value.filter(x=>x&&typeof x.id==='string'&&['highlight','note','bookmark'].includes(x.type)&&Number.isInteger(x.volume)&&Number.isInteger(x.year)&&Array.isArray(x.segments)&&x.segments.every(s=>typeof s.target==='string'&&typeof s.source==='string'&&Number.isInteger(s.start)&&Number.isInteger(s.end)&&s.start>=0&&s.end>s.start&&s.end<=s.source.length)):[];}catch{return [];}}
 items=load();
 const launch=document.createElement('button');launch.className='annotation-launch';launch.textContent='我的摘记';document.querySelector('.header-right').prepend(launch);
 const popup=document.createElement('div');popup.className='annotation-popover';popup.hidden=true;popup.setAttribute('role','dialog');popup.setAttribute('aria-label','选中文字的操作');document.body.append(popup);
 const dialog=document.createElement('dialog');dialog.className='annotation-dialog';dialog.innerHTML='<header><h2>我的摘记</h2><button data-close aria-label="关闭">×</button></header><div class="annotation-body"></div>';document.body.append(dialog);
 const toast=document.createElement('div');toast.className='annotation-toast';toast.setAttribute('role','status');document.body.append(toast);let toastTimer;
 function tell(text){toast.textContent=text;clearTimeout(toastTimer);toastTimer=setTimeout(()=>toast.textContent='',2800);}
 function save(next){try{localStorage.setItem(KEY,JSON.stringify(next));items=next;return true;}catch{tell('保存失败，请允许浏览器使用本地存储。');return false;}}
 function nodes(p,includeNotes=false){const walker=document.createTreeWalker(p,NodeFilter.SHOW_TEXT,{acceptNode:n=>n.parentElement.closest(includeNotes?'.marker':'.note,.marker')?NodeFilter.FILTER_REJECT:NodeFilter.FILTER_ACCEPT});let n,result=[];while(n=walker.nextNode())result.push(n);return result;}
 function targets(legacy=false){if(readingMode==='vertical')return [...(activeContent()?.querySelectorAll('[data-source-block]')||[])].map(p=>({p,anchor:0,key:'traditional-'+(legacy?'':'full-')+p.dataset.sourceBlock,includeNotes:!legacy}));return [...content.querySelectorAll('p[id^="para-"],.modern-text')].filter(p=>!p.closest('.source-differences')).map((p,i)=>{const row=p.closest('.compare-row');const anchor=p.id?+p.id.slice(5):+(row?.querySelector('p[id^="para-"]')?.id.slice(5)||0);return {p,anchor,key:p.id||'modern-'+(row?.dataset.pair??i)};});}
 function source(p,includeNotes=false){return nodes(p,includeNotes).map(n=>n.textContent).join('');}
 function clearMarks(){const root=activeContent();if(!root)return;root.querySelectorAll('[data-annotation-ids]').forEach(span=>span.replaceWith(...span.childNodes));root.normalize();}
 function restore(){
  clearMarks();if(!readerOpen||readingIndex<0)return;
  const current=items.filter(x=>x.volume===book.volume&&(readingMode==='vertical'?x.segments.some(s=>s.target.startsWith('traditional-')):x.year===selected));
  // Legacy vertical offsets omitted notes; restore them against that same text.
  for(const t of readingMode==='vertical'?[...targets(true),...targets()]:targets()){
   const text=source(t.p,t.includeNotes),segments=current.flatMap(item=>item.segments.filter(s=>s.target===t.key&&s.source===text).map(s=>({...s,item})));
   let offset=0;
   for(const n of nodes(t.p,t.includeNotes)){
    const start=offset,end=start+n.length;offset=end;
    const relevant=segments.filter(s=>s.start<end&&s.end>start);if(!relevant.length)continue;
    const cuts=[...new Set([start,end,...relevant.flatMap(s=>[Math.max(start,s.start),Math.min(end,s.end)])])].sort((a,b)=>a-b),fragment=document.createDocumentFragment();
    for(let i=0;i<cuts.length-1;i++){
     const a=cuts[i],b=cuts[i+1],active=relevant.filter(s=>s.start<=a&&s.end>=b).map(s=>s.item),textNode=document.createTextNode(n.textContent.slice(a-start,b-start));
     if(!active.length){fragment.append(textNode);continue;}
     const mark=document.createElement('span');mark.dataset.annotationIds=active.map(x=>x.id).join(' ');mark.className='reader-annotation';
     const highlight=active.find(x=>x.type==='highlight');if(highlight)mark.dataset.color=colors[highlight.color]?highlight.color:'yellow';
     if(active.some(x=>x.type==='note')){mark.classList.add('has-thought');mark.tabIndex=0;mark.setAttribute('role','button');mark.setAttribute('aria-label','查看想法');}
     if(active.some(x=>x.type==='bookmark'))mark.classList.add('has-bookmark');
     mark.append(textNode);fragment.append(mark);
    }n.replaceWith(fragment);
   }
  }
 }
 function capture(){
  const sel=window.getSelection();if(!sel||sel.isCollapsed||!sel.rangeCount||!readerOpen||readingIndex<0)return null;
  const range=sel.getRangeAt(0);if(!activeContent()?.contains(range.startContainer)||!activeContent()?.contains(range.endContainer))return null;
  const segments=[];
  for(const t of targets()){
   let offset=0,start=null,end=null;
   const text=source(t.p,t.includeNotes);
   const flush=()=>{if(start!==null&&end>start)segments.push({target:t.key,anchor:t.anchor,source:text,start,end});start=end=null;};
   for(const n of nodes(t.p,t.includeNotes)){
    if(range.intersectsNode(n)){
     const note=n.parentElement.closest('.note');
     const hidden=note&&getComputedStyle(note).display==='none';
     const a=n===range.startContainer?range.startOffset:0,b=n===range.endContainer?range.endOffset:n.length;
     if(hidden)flush();
     else if(b>a){if(start===null)start=offset+a;end=offset+b;}
    }offset+=n.length;
   }
   flush();
  }
  if(!segments.length)return null;
  return {volume:book.volume,year:selected,segments,text:segments.map(s=>s.source.slice(s.start,s.end)).join('\n'),rect:range.getBoundingClientRect()};
 }
 function hide(){popup.hidden=true;}
 function position(rect){popup.hidden=false;const w=popup.offsetWidth,h=popup.offsetHeight;popup.style.left=Math.max(10,Math.min(innerWidth-w-10,rect.left+rect.width/2-w/2))+'px';popup.style.top=Math.max(10,Math.min(innerHeight-h-10,rect.top>h+18?rect.top-h-12:rect.bottom+12))+'px';}
 const icons={highlight:'<path d="m5 15 9-9 4 4-9 9H5v-4ZM13 7l4 4M4 22h16"/>',note:'<path d="M12 4H5a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h13a2 2 0 0 0 2-2v-7M16 3l5 5-9 9H7v-5l9-9Z"/>',bookmark:'<path d="M6 3h12v19l-6-4-6 4V3Z"/>'};
 function icon(type){return `<svg viewBox="0 0 24 26" width="22" height="24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[type]}</svg>`;}
 function menu(){const selection=capture();if(!selection){hide();return;}pending=selection;popup.innerHTML=`<button data-action="highlight">${icon('highlight')}<span>划线</span></button><button data-action="note">${icon('note')}<span>写想法</span></button><button data-action="bookmark">${icon('bookmark')}<span>书签</span></button>`;position(selection.rect);}
 function commit(type,color,note){
  const entry=editing?{...editing,note}:{id:globalThis.crypto?.randomUUID?.()||Date.now()+'-'+Math.random(),volume:pending.volume,year:pending.year,segments:pending.segments,text:pending.text,type,color,note,created:Date.now()};
  const duplicate=items.find(x=>x.type===type&&x.volume===entry.volume&&x.year===entry.year&&JSON.stringify(x.segments)===JSON.stringify(entry.segments));
  if(save(editing?items.map(x=>x.id===editing.id?entry:x):[entry,...items.filter(x=>x.id!==duplicate?.id)])){hide();dialog.close();window.getSelection()?.removeAllRanges();restore();tell(type==='note'?'想法已保存':type==='bookmark'?'已加入书签':'划线已保存');}
 }
 function editor(item=null){editing=item;hide();dialog.querySelector('h2').textContent=item?'我的想法':'写想法';dialog.querySelector('.annotation-body').innerHTML=`<blockquote>${esc(item?.text||pending.text)}</blockquote><label for="annotationThought">记下此刻的想法</label><textarea id="annotationThought" maxlength="10000" placeholder="读到这里，你想到了什么？"></textarea><div class="annotation-actions"><button data-cancel>取消</button><button class="primary" data-save>保存想法</button></div>`;dialog.querySelector('textarea').value=item?.note||'';if(!dialog.open)dialog.showModal();dialog.querySelector('textarea').focus();}
 function filterLibrary(){
  const entries=[...dialog.querySelectorAll('.annotation-entry')];let shown=0;
  for(const entry of entries){entry.hidden=!((libraryType==='all'||entry.dataset.type===libraryType)&&entry.textContent.toLowerCase().includes(libraryQuery.trim().toLowerCase()));if(!entry.hidden)shown++;}
  dialog.querySelectorAll('[data-library-type]').forEach(button=>{button.setAttribute('aria-pressed',String(button.dataset.libraryType===libraryType));});
  const empty=dialog.querySelector('.annotation-empty');if(empty){empty.hidden=shown>0;empty.innerHTML=libraryQuery?'没有找到相关摘记。<small>试试摘录中的词语、想法内容或年份。</small>':`还没有${({bookmark:'书签',note:'想法',highlight:'划线'})[libraryType]||'摘记'}。<small>选中原文或译文，即可划线、写想法或添加书签。</small>`;}
 }
 function library(){editing=null;hide();dialog.querySelector('h2').textContent='我的摘记';
  let legacy=[];try{legacy=JSON.parse(localStorage.getItem('tongjian-bookmarks-v1')||'[]');if(!Array.isArray(legacy))legacy=[];}catch{}
  const old=legacy.filter(b=>Number.isInteger(b.volume)&&Number.isInteger(b.year)&&Number.isInteger(b.anchor));
  const tabs=[['bookmark','书签',items.filter(x=>x.type==='bookmark').length+old.length],['note','想法',items.filter(x=>x.type==='note').length],['highlight','划线',items.filter(x=>x.type==='highlight').length]];
  dialog.querySelector('.annotation-body').innerHTML=`<div class="annotation-library-tools"><div class="annotation-tabs" role="group" aria-label="摘记分类">${tabs.map(([type,label,count])=>`<button data-library-type="${type}" aria-pressed="${type===libraryType}">${icon(type==='highlight'?'highlight':type==='note'?'note':'bookmark')}${label}<span>${count}</span></button>`).join('')}</div><input class="annotation-search" type="search" aria-label="搜索摘记" placeholder="搜索摘录、想法或年份"></div><div class="annotation-entries">`+items.map(x=>`<article class="annotation-entry" data-type="${x.type}"><div class="annotation-entry-meta">${x.type==='note'?'想法':x.type==='bookmark'?'书签':'划线'} · 卷${esc(x.volume)} · ${esc(yearLabel(x.year))}</div><a data-annotation-link="${esc(x.id)}" href="#volume-${x.volume}-year-${x.year}-para-${x.segments[0]?.anchor||0}">${esc(x.text)}</a>${x.type==='note'?`<p class="thought-text">${esc(x.note||'')}</p><button data-edit="${esc(x.id)}">编辑想法</button>`:''}<button data-delete="${esc(x.id)}">删除</button></article>`).join('')+old.map(b=>`<article class="annotation-entry" data-type="bookmark"><div class="annotation-entry-meta">书签 · 卷${b.volume} · ${esc(yearLabel(b.year))}</div><a href="#volume-${b.volume}-year-${b.year}-para-${b.anchor}">${esc(b.text)}</a><button data-legacy="${legacy.indexOf(b)}">删除</button></article>`).join('')+'</div><div class="annotation-empty" role="status"></div>';
  dialog.querySelector('.annotation-search').value=libraryQuery;filterLibrary();
  if(!dialog.open)dialog.showModal();
 }
 dialog.addEventListener('input',e=>{if(e.target.matches('.annotation-search')){libraryQuery=e.target.value;filterLibrary();}});
 launch.onclick=library;
 popup.addEventListener('pointerdown',e=>e.preventDefault());
 popup.onclick=e=>{const b=e.target.closest('button');if(!b||!pending)return;editing=null;
  if(b.dataset.action==='highlight'){popup.innerHTML='<span class="palette-label">高亮颜色</span>'+Object.entries(colors).map(([color,label])=>`<button class="annotation-swatch" data-color="${color}" aria-label="${label}" title="${label}"></button>`).join('');position(pending.rect);}
  else if(b.dataset.action==='note')editor();else if(b.dataset.action==='bookmark')commit('bookmark');else if(b.dataset.color)commit('highlight',b.dataset.color);
 };
 dialog.onclick=async e=>{const link=e.target.closest('[data-annotation-link]');if(link){const item=items.find(x=>x.id===link.dataset.annotationLink);if(item?.segments[0]?.target.startsWith('traditional-')){e.preventDefault();dialog.close();await openYear(item.volume,item.year);setReadingMode('vertical');window.tongjianVertical.reveal(Number(item.segments[0].target.match(/^traditional-(?:full-)?(\d+)/)?.[1]));return;}}const b=e.target.closest('button');if(e.target.closest('a'))dialog.close();if(!b)return;if(b.dataset.libraryType){libraryType=b.dataset.libraryType;filterLibrary();}else if(b.hasAttribute('data-close')||b.hasAttribute('data-cancel'))dialog.close();else if(b.hasAttribute('data-save')){const note=dialog.querySelector('textarea').value.trim();if(note)commit('note',null,note);else dialog.querySelector('textarea').focus();}else if(b.hasAttribute('data-legacy')){try{const legacy=JSON.parse(localStorage.getItem('tongjian-bookmarks-v1')||'[]');legacy.splice(+b.dataset.legacy,1);localStorage.setItem('tongjian-bookmarks-v1',JSON.stringify(legacy));library();}catch{tell('删除失败，请检查本地存储权限。');}}else if(b.dataset.edit)editor(items.find(x=>x.id===b.dataset.edit));else if(b.dataset.delete){if(save(items.filter(x=>x.id!==b.dataset.delete))){restore();library();}}};
 surface.addEventListener('pointerup',()=>setTimeout(menu,25));
 surface.addEventListener('keyup',e=>{if(e.shiftKey)menu();});
 let selectionTimer;document.addEventListener('selectionchange',()=>{clearTimeout(selectionTimer);if(dialog.open)return;selectionTimer=setTimeout(()=>{if(window.getSelection()?.isCollapsed)hide();else menu();},180);});
 surface.addEventListener('click',e=>{if(!window.getSelection()?.isCollapsed)return;const mark=e.target.closest('.has-thought');if(mark){const item=items.find(x=>x.type==='note'&&mark.dataset.annotationIds.split(' ').includes(x.id));if(item)editor(item);}});
 surface.addEventListener('keydown',e=>{if((e.key==='Enter'||e.key===' ')&&e.target.matches('.has-thought')){e.preventDefault();e.target.click();}});
 document.addEventListener('pointerdown',e=>{if(!popup.contains(e.target)&&!surface.contains(e.target))hide();});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&(!popup.hidden||dialog.open)){e.stopImmediatePropagation();hide();dialog.close();}},true);
 window.addEventListener('scroll',hide,{passive:true,capture:true});
 document.addEventListener('traditional-reader-ready',()=>{hide();restore();});window.addEventListener('resize',hide);
 new MutationObserver(records=>{if(records.some(r=>r.target===content)){hide();restore();}}).observe(content,{childList:true});
 window.addEventListener('storage',e=>{if(e.key===KEY||e.key===null){items=load();restore();if(dialog.open&&!dialog.querySelector('textarea'))library();}});
 restore();
})();
