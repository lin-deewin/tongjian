/* Shared select menu, independent of native picker styling support. */
(()=>{
 let menu=null,owner=null;
 const close=()=>{if(owner)owner.setAttribute('aria-expanded','false');menu?.remove();menu=null;owner=null;};
 function open(select){
  if(select.disabled)return;
  if(owner===select){close();return;}
  close();owner=select;select.focus({preventScroll:true});
  menu=document.createElement('div');menu.className='site-select-menu';menu.id='siteSelectMenu';menu.role='listbox';
  if(select.id==='volumeSelect')menu.classList.add('site-volume-menu');
  menu.setAttribute('aria-label',select.getAttribute('aria-label')||select.closest('label')?.textContent.trim()||'选择选项');
  select.setAttribute('aria-expanded','true');select.setAttribute('aria-controls',menu.id);
  let active=select.selectedIndex;
  const options=Array.from(select.options),buttons=[];
  let lastGroup=null;
  options.forEach((option,index)=>{
   if(select.id==='volumeSelect' && option.parentElement.tagName==='OPTGROUP' && option.parentElement!==lastGroup){
    lastGroup=option.parentElement;
    const heading=document.createElement('div');heading.className='site-select-group';heading.textContent=lastGroup.label;heading.setAttribute('role','presentation');menu.append(heading);
   }
   const button=document.createElement('button');button.type='button';button.role='option';button.textContent=option.textContent;
   if(select.id==='volumeSelect' && option.dataset.title){
    button.textContent='';const title=document.createElement('span'),years=document.createElement('small');
    title.textContent=option.dataset.title;years.textContent=option.dataset.years;button.append(title,years);
   }
   button.setAttribute('aria-selected',String(index===active));button.disabled=option.disabled||option.parentElement.disabled;button.tabIndex=-1;
   button.onclick=()=>{select.selectedIndex=index;select.dispatchEvent(new Event('input',{bubbles:true}));select.dispatchEvent(new Event('change',{bubbles:true}));close();select.focus({preventScroll:true});};
   menu.append(button);buttons.push(button);
  });
  document.body.append(menu);
  const box=select.getBoundingClientRect(),available=innerHeight-16;
  menu.style.minWidth=Math.min(Math.max(box.width,140),innerWidth-16)+'px';menu.style.maxHeight=Math.min(340,available)+'px';
  const size=menu.getBoundingClientRect();
  menu.style.left=Math.max(8,Math.min(box.left,innerWidth-size.width-8))+'px';
  const below=innerHeight-box.bottom-8,above=box.top-8;
  menu.style.maxHeight=Math.min(340,Math.max(below,above))+'px';
  menu.style.top=(below>=Math.min(size.height,340)?box.bottom+6:Math.max(8,box.top-Math.min(size.height,above)-6))+'px';
  function focus(index){if(!buttons.length)return;let tries=0;while(buttons[index]?.disabled&&tries++<buttons.length)index=(index+1)%buttons.length;active=index;buttons[index]?.focus({preventScroll:true});buttons[index]?.scrollIntoView({block:'nearest'});}
  focus(Math.max(0,active));
  let typed='',timer;
  menu.onkeydown=event=>{
   if(event.key==='Escape'){event.preventDefault();close();select.focus({preventScroll:true});return;}
   if(event.key==='Tab'){close();select.focus({preventScroll:true});return;}
   if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){
    event.preventDefault();let next=event.key==='Home'?0:event.key==='End'?buttons.length-1:(active+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length;
    focus(next);return;
   }
   if(event.key.length===1&&event.key!==' '){typed+=event.key.toLowerCase();clearTimeout(timer);timer=setTimeout(()=>typed='',600);const index=options.findIndex(o=>o.textContent.trim().toLowerCase().startsWith(typed));if(index>=0)focus(index);}
  };
 }
 document.addEventListener('pointerdown',event=>{
  const select=event.target.closest('select:not([multiple]):not([size])');
  if(select){event.preventDefault();open(select);}
  else if(menu&&!menu.contains(event.target))close();
 });
 document.addEventListener('click',event=>{if(event.target.closest('select:not([multiple]):not([size])'))event.preventDefault();});
 document.addEventListener('keydown',event=>{
  if(event.target.matches('select:not([multiple]):not([size])')&&['Enter',' ','ArrowDown','ArrowUp'].includes(event.key)){
   event.preventDefault();open(event.target);
  }
 });
 document.addEventListener('scroll',event=>{if(menu&&!menu.contains(event.target))close();},true);
 window.addEventListener('resize',close);
})();
