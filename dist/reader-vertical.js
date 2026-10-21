// The uploaded traditional EPUB shares the existing reader shell and navigation.
(()=>{
 const scroll=document.querySelector('#readerScroll');
 const host=document.createElement('section');host.id='traditionalReader';host.hidden=true;
 host.innerHTML='<div class="traditional-viewport" tabindex="0" aria-label="繁体竖版正文，从右向左阅读"><article lang="zh-Hant"></article></div><div class="traditional-pages"><button type="button" data-vertical-page="1">向左 · 下一屏</button><span role="status"></span><button type="button" data-vertical-page="-1">向右 · 上一屏</button></div>';
 scroll.append(host);
 const viewport=host.querySelector('.traditional-viewport'),article=host.querySelector('article'),status=host.querySelector('[role=status]');
 const cache=new Map();let generation=0,route='',timer,activePositionKey='',revealBlock=null;
 // Keep the 20px vertical default independent of the parallel-text reader.
 let verticalSize=20,horizontalSize=19,verticalFontActive=false;
 let verticalNotes=true,horizontalNotes=false;
 const noteInput=document.querySelector('#showNotes');
 try{verticalNotes=localStorage.getItem('tongjian-vertical-show-notes')!=='false';}catch{}
 try{const size=Number(localStorage.getItem('tongjian-vertical-font-size'));if(size>=15&&size<=48)verticalSize=size;}catch{}
 function syncFont(){
  if(readingMode==='vertical'&&!verticalFontActive){horizontalSize=Math.min(28,readingSize);horizontalNotes=noteInput.checked;readingSize=verticalSize;noteInput.checked=verticalNotes;verticalFontActive=true;}
  else if(readingMode!=='vertical'&&verticalFontActive){readingSize=horizontalSize;noteInput.checked=horizontalNotes;verticalFontActive=false;}
  document.querySelectorAll('.original').forEach(node=>node.classList.toggle('hide-notes',!noteInput.checked));
  document.documentElement.style.setProperty('--reading-size',readingSize+'px');
 }
 document.addEventListener('click',event=>{
  if(readingMode!=='vertical'||!event.target.closest('#smaller,#larger'))return;
  verticalSize=readingSize;
  try{localStorage.setItem('tongjian-vertical-font-size',String(verticalSize));}catch{}
 });
 const positionKey=()=>`tongjian-traditional:${book?.volume}:${selected}`;
 function save(){if(readingMode!=='vertical'||host.hidden)return;try{localStorage.setItem(activePositionKey||positionKey(),String(viewport.scrollLeft));}catch{}}
 function progress(){if(readingMode!=='vertical')return;const max=viewport.scrollWidth-viewport.clientWidth;const value=max>0?Math.min(1,Math.abs(viewport.scrollLeft)/max):1;document.querySelector('#progressBar').style.width=value*100+'%';status.textContent=`${Math.round(value*100)}% · 从右往左阅读`;}
 function page(direction){viewport.scrollBy({left:-direction*viewport.clientWidth*.85,behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'});}
 function styleVolumeTitle(){
  const first=article.querySelector('[data-source-block="0"]');if(!first)return;
  const node=first.firstChild;if(!node||node.nodeType!==Node.TEXT_NODE)return;
  const match=node.textContent.match(/資治通鑑[^\n]+/);if(!match)return;
  const title=document.createElement('h1');title.className='traditional-volume-title';
  const name=document.createElement('strong');name.textContent=match[0].slice(0,4);
  const volume=document.createElement('small');volume.textContent=match[0].slice(4);
  title.append(name,volume);
  const fragment=document.createDocumentFragment();
  fragment.append(document.createTextNode(node.textContent.slice(0,match.index)),title,document.createTextNode(node.textContent.slice(match.index+match[0].length)));
  node.replaceWith(fragment);
 }
 function styleBracketNotes(root){
  // Work from text offsets so brackets split by existing EPUB spans still match.
  // Some source notes close with 〕; retain that source character unchanged.
  for(const section of root.querySelectorAll('[data-source-block]')){
   const walker=document.createTreeWalker(section,NodeFilter.SHOW_TEXT),leaves=[];let node,offset=0;
   while(node=walker.nextNode()){leaves.push({node,start:offset});offset+=node.length;}
   const ranges=[...section.textContent.matchAll(/【[^】〕]*[】〕]/g)].map(m=>({start:m.index,end:m.index+m[0].length}));
   for(const {node,start} of leaves){
    const hits=ranges.filter(r=>r.start<start+node.length&&r.end>start);if(!hits.length)continue;
    const fragment=document.createDocumentFragment();let cursor=0;
    for(const r of hits){const a=Math.max(0,r.start-start),b=Math.min(node.length,r.end-start);
     fragment.append(document.createTextNode(node.textContent.slice(cursor,a)));
     const span=document.createElement('span');span.className='bracket-note';span.textContent=node.textContent.slice(a,b);fragment.append(span);cursor=b;
    }
    fragment.append(document.createTextNode(node.textContent.slice(cursor)));node.replaceWith(fragment);
   }
  }
 }
 async function sync(anchor=null){
  syncFont();
  const enabled=readingMode==='vertical'&&readerOpen;
  host.hidden=!enabled;scroll.classList.toggle('mode-vertical',enabled);document.querySelector('#readerContent').hidden=enabled;
  host.classList.toggle('hide-traditional-notes',!document.querySelector('#showNotes').checked);
  if(!enabled){generation++;route='';return;}
  const nextRoute=`${book.volume}:${selected}`;if(route===nextRoute&&anchor===null){document.dispatchEvent(new Event('traditional-reader-ready'));progress();return;}
  route=nextRoute;const token=++generation,volume=book.volume,year=selected;
  article.textContent='正在载入繁体原书…';
  try{
   let data=cache.get(volume);
   if(!data){const response=await fetch(new URL(`vertical-book/chapter-${String(volume+2).padStart(3,'0')}.json`,document.baseURI));if(!response.ok)throw Error();data=await response.json();cache.set(volume,data);}
   if(token!==generation)return;
   activePositionKey=positionKey();
   article.innerHTML=data.blocks.map((block,i)=>`<section data-source-block="${i}">${block}</section>`).join('');
   styleVolumeTitle();
   styleBracketNotes(article);
   document.dispatchEvent(new Event('traditional-reader-ready'));
   requestAnimationFrame(()=>{
    if(token!==generation)return;
    let restored=null;try{restored=localStorage.getItem(positionKey());}catch{}
    const exact=data.anchors[`${year}:${anchor??0}`];
    const yearEntry=Object.entries(data.anchors).find(([key])=>key.startsWith(year+':'));
    const index=exact??yearEntry?.[1];
    if(revealBlock!==null){reveal(revealBlock);}
    else if(anchor===null&&restored!==null)viewport.scrollLeft=Number(restored)||0;
    else if(index!==undefined){const target=article.querySelector(`[data-source-block="${index}"]`);viewport.scrollLeft=0;viewport.scrollLeft=target.getBoundingClientRect().right-viewport.getBoundingClientRect().right+24;}
    else{viewport.scrollLeft=0;status.textContent='本年段落尚未可靠定位，显示完整卷文。';return;}
    progress();if(exact===undefined)status.textContent='已定位本年可核对的段落 · 本卷连续阅读';
   });
  }catch{if(token===generation){route='';article.textContent='繁体原书载入失败，请切换阅读模式后重试。';}}
 }
 host.addEventListener('click',e=>{const button=e.target.closest('[data-vertical-page]');if(button)page(Number(button.dataset.verticalPage));});
 viewport.addEventListener('scroll',()=>{progress();clearTimeout(timer);timer=setTimeout(save,160);},{passive:true});
 viewport.addEventListener('wheel',e=>{if(Math.abs(e.deltaY)>Math.abs(e.deltaX)&&!e.ctrlKey){e.preventDefault();viewport.scrollLeft-=e.deltaY*(e.deltaMode===1?20:1);}},{passive:false});
 viewport.addEventListener('keydown',e=>{if(['PageDown','PageUp','ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();page(['PageDown','ArrowLeft'].includes(e.key)?1:-1);}});
 noteInput.addEventListener('change',()=>{
  if(readingMode==='vertical'){verticalNotes=noteInput.checked;try{localStorage.setItem('tongjian-vertical-show-notes',String(verticalNotes));}catch{}}
  host.classList.toggle('hide-traditional-notes',!noteInput.checked);progress();
 });
 window.addEventListener('pagehide',save);
 window.addEventListener('resize',progress);
 function reveal(block){revealBlock=block;const target=article.querySelector(`[data-source-block="${block}"]`);if(!target)return;viewport.scrollLeft+=target.getBoundingClientRect().right-viewport.getBoundingClientRect().right+24;revealBlock=null;progress();}
 window.tongjianVertical={sync,save,reveal,horizontalSize:()=>verticalFontActive?horizontalSize:readingSize,horizontalNotes:()=>verticalFontActive?horizontalNotes:noteInput.checked};
})();
