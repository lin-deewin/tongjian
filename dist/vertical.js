'use strict';
const $=id=>document.getElementById(id), viewport=$('viewport');
let catalog=[], current=0, loading=0, timer;
const key='tongjian-vertical-reader-v1';
let saved={};
try{saved=JSON.parse(localStorage.getItem(key)||'{}')||{};}catch{}
$('size').value=Math.max(16,Math.min(48,Number(saved.size)||20));
$('notes').checked=saved.notes!==false;
$('layout').value=saved.layout==='horizontal'?'horizontal':'vertical';
function preferences(){
 document.documentElement.style.setProperty('--size',$('size').value+'px');
 document.body.classList.toggle('hide-notes',!$('notes').checked);
 document.body.classList.toggle('horizontal',$('layout').value==='horizontal');
 $('back').textContent=$('layout').value==='horizontal'?'上一屏':'向右翻页';
 $('forward').textContent=$('layout').value==='horizontal'?'下一屏':'向左翻页';
}
function save(){if(!catalog.length)return;try{localStorage.setItem(key,JSON.stringify({chapter:current,x:viewport.scrollLeft,y:viewport.scrollTop,size:$('size').value,notes:$('notes').checked,layout:$('layout').value}));}catch{}}
async function load(index,restore=false){
 const token=++loading;current=index;
 $('chapter').value=String(index);$('status').textContent='正在载入…';
 $('previous').disabled=index===0;$('next').disabled=index===catalog.length-1;
 try{
  const response=await fetch('vertical-book/'+catalog[index].file);
  if(!response.ok)throw Error('载入失败');
  const chapter=await response.json();if(token!==loading)return;
  $('text').innerHTML=chapter.html;
  const title=$('text').querySelector('h1');
  if(title&&title.textContent.startsWith('資治通鑑')){
   const text=title.textContent,name=document.createElement('strong'),volume=document.createElement('small');
   name.textContent=text.slice(0,4);volume.textContent=text.slice(4);title.replaceChildren(name,volume);
  }
  const walker=document.createTreeWalker($('text'),NodeFilter.SHOW_TEXT),nodes=[];
  while(walker.nextNode())nodes.push(walker.currentNode);
  for(const node of nodes){
   if(node.parentElement.closest('.note'))continue;
   const parts=node.textContent.split(/(【[^】〕]*[】〕])/g);if(parts.length===1)continue;
   const fragment=document.createDocumentFragment();
   parts.forEach((part,i)=>{if(i%2){const note=document.createElement('span');note.className='bracket-note';note.textContent=part;fragment.append(note);}else fragment.append(document.createTextNode(part));});
   node.replaceWith(fragment);
  }
  document.title=chapter.title+' · 竖排阅读';
  history.replaceState(null,'','#chapter='+index);
  requestAnimationFrame(()=>{if(token!==loading)return;viewport.scrollLeft=restore?Number(saved.x)||0:0;viewport.scrollTop=restore?Number(saved.y)||0:0;save();});
  $('status').textContent=chapter.title;
 }catch{if(token!==loading)return;$('text').textContent='篇卷载入失败，请检查网络后重新选择篇卷。';$('status').textContent='载入失败';}
}
function page(direction){const horizontal=$('layout').value==='horizontal';viewport.scrollBy({left:horizontal?0:-direction*viewport.clientWidth*.85,top:horizontal?direction*viewport.clientHeight*.85:0,behavior:'smooth'});}
$('chapter').addEventListener('change',()=>load(Number($('chapter').value)));
$('previous').onclick=()=>current>0&&load(current-1);
$('next').onclick=()=>current<catalog.length-1&&load(current+1);
$('back').onclick=()=>page(-1);$('forward').onclick=()=>page(1);
for(const id of ['size','notes','layout'])$(id).addEventListener('input',()=>{preferences();save();});
viewport.addEventListener('scroll',()=>{clearTimeout(timer);timer=setTimeout(save,150);});
window.addEventListener('pagehide',save);
viewport.addEventListener('keydown',event=>{if(event.key==='PageDown'||event.key==='PageUp'){event.preventDefault();page(event.key==='PageDown'?1:-1);}});
preferences();
(async()=>{try{
 const response=await fetch('vertical-book/catalog.json');if(!response.ok)throw Error();catalog=await response.json();
 catalog.forEach((chapter,index)=>$('chapter').add(new Option(chapter.title,index)));
 const match=location.hash.match(/^#chapter=(\d+)$/),requested=match?Number(match[1]):(Number.isInteger(saved.chapter)?saved.chapter:3);
 await load(Math.max(0,Math.min(catalog.length-1,requested)),!match||Number(match[1])===saved.chapter);
}catch{$('status').textContent='目录载入失败，请刷新重试。';}})();
