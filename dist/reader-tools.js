// Compact reader tools reuse the existing controls and their bound handlers.
(()=>{
 const reader=document.querySelector('#readerBackdrop'),toolbar=reader.querySelector('.reader-toolbar');
 const drawings={catalog:'<path d="M5 6h14M5 12h14M5 18h14"/>',mode:'<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M12 4v16"/>',notes:'<path d="M6 3h12v18l-6-4-6 4V3Z"/>',font:'<path d="m4 20 7-16 7 16M7 14h8M20 7v10M18 9l2-2 2 2M18 15l2 2 2-2"/>',theme:'<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M2 12h2M20 12h2M5 5l1.5 1.5M17.5 17.5 19 19M5 19l1.5-1.5M17.5 6.5 19 5"/>'};
 const names={catalog:'目录',mode:'阅读模式',notes:'我的摘记',font:'字号与注释',theme:'主题'};
 const svg=type=>`<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${drawings[type]}</svg>`;
 const rail=document.createElement('nav');rail.className='reader-tools';rail.setAttribute('aria-label','阅读工具');
 rail.innerHTML=Object.keys(names).map(type=>`<button type="button" data-reader-tool="${type}" aria-label="${names[type]}" title="${names[type]}" aria-haspopup="dialog"${type==='notes'?'':' aria-controls="readerToolPanel" aria-expanded="false"'}>${svg(type)}<span>${names[type]}</span></button>`).join('');reader.append(rail);
 const shade=document.createElement('div');shade.className='reader-tool-shade';shade.hidden=true;reader.append(shade);
 const panel=document.createElement('section');panel.className='reader-tool-panel';panel.id='readerToolPanel';panel.hidden=true;panel.setAttribute('role','dialog');panel.setAttribute('aria-label','阅读工具');
 panel.innerHTML='<div class="reader-tool-panel-head"><h2>阅读工具</h2><button type="button" data-close-tool aria-label="关闭阅读工具">×</button></div><div class="reader-tool-body"></div>';reader.append(panel);
 const body=panel.querySelector('.reader-tool-body');
 const sections={};for(const type of ['catalog','mode','font','theme']){const section=document.createElement('div');section.className='reader-tool-section';section.dataset.toolSection=type;section.hidden=true;body.append(section);sections[type]=section;}
 sections.catalog.innerHTML='<label class="reader-tool-caption" for="volumeSelect">选择卷次</label><div class="tool-volume-slot"></div><label class="reader-tool-caption" for="readerYear">当前卷 · 跳转年份</label><div class="tool-year-slot"></div><div class="tool-catalog-events"></div><div class="tool-catalog-footer"></div>';
 const volume=document.querySelector('#volumeSelect'),volumeHome=document.createComment('yearbook volume selector');volume.before(volumeHome);
 const year=document.querySelector('#readerYear');sections.catalog.querySelector('.tool-year-slot').append(year);
 sections.catalog.querySelector('.tool-catalog-footer').append(document.querySelector('#readerPeople'));
 const intro=document.createElement('button');intro.type='button';intro.textContent='阅读卷首说明';intro.onclick=()=>{close(false);volumeIntro();};sections.catalog.querySelector('.tool-catalog-footer').append(intro);
 sections.mode.append(toolbar.querySelector('.reading-modes'));
 const fontSize=document.createElement('div');fontSize.className='tool-font-size';fontSize.innerHTML='<span>字号</span><div class="tool-size-stepper" role="group" aria-label="调整正文字号"></div>';fontSize.lastElementChild.append(document.querySelector('#smaller'),document.querySelector('#larger'));sections.font.append(fontSize);
 const sizeLabel=document.createElement('output');sizeLabel.className='tool-font-value';sizeLabel.setAttribute('aria-live','polite');fontSize.lastElementChild.insertBefore(sizeLabel,document.querySelector('#larger'));
 const noteInput=document.querySelector('#showNotes'),noteLabel=noteInput.closest('label');
 noteInput.setAttribute('role','switch');noteInput.setAttribute('aria-label','显示胡注与校勘');
 noteLabel.className='tool-note-setting';noteLabel.replaceChildren();
 const noteText=document.createElement('span');noteText.className='tool-setting-copy';noteText.innerHTML='<span>胡注与校勘</span><small class="tool-note-help">在原文中显示注释</small><small class="tool-note-unavailable">仅白话模式下不可用</small>';
 noteLabel.append(noteText,noteInput);sections.font.append(noteLabel);
 document.querySelector('#smaller').textContent='−';document.querySelector('#larger').textContent='+';
 function syncSize(){sizeLabel.textContent=readingSize;document.querySelector('#smaller').disabled=readingSize<=15;document.querySelector('#larger').disabled=readingSize>=28;}
 const themeControl=toolbar.querySelector('.theme-control'),themeSelect=themeControl.querySelector('select');themeControl.hidden=true;sections.theme.append(themeControl);
 const themeList=document.createElement('div');themeList.className='tool-theme-list';themeList.setAttribute('role','group');themeList.setAttribute('aria-label','选择阅读主题');
 themeList.innerHTML=[...themeSelect.options].map(option=>`<button type="button" data-choose-theme="${option.value}" aria-pressed="false"><span class="tool-theme-sample" data-preview-theme="${option.value}" aria-hidden="true">文</span><span>${esc(option.textContent)}</span><svg class="tool-theme-check" width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m5 12 4 4L19 6"/></svg></button>`).join('');sections.theme.append(themeList);
 function syncThemes(){themeList.querySelectorAll('button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.chooseTheme===document.documentElement.dataset.theme)));}
 themeList.addEventListener('click',e=>{const button=e.target.closest('[data-choose-theme]');if(!button)return;themeSelect.value=button.dataset.chooseTheme;themeSelect.dispatchEvent(new Event('change',{bubbles:true}));syncThemes();});
 new MutationObserver(syncThemes).observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});syncThemes();
 const mobile=document.createElement('button');mobile.type='button';mobile.className='reader-mobile-tools';mobile.setAttribute('aria-label','打开阅读工具');mobile.setAttribute('aria-controls',panel.id);mobile.setAttribute('aria-expanded','false');mobile.innerHTML=svg('catalog')+'<span>工具</span>';reader.querySelector('.reader-nav').insertBefore(mobile,document.querySelector('#readerPosition'));
 const yearLabelNode=document.createElement('span');yearLabelNode.className='reader-head-year';reader.querySelector('.reader-head').append(yearLabelNode);
 let active=null,opener=null;
 function catalogEntries(){if(!book)return;sections.catalog.querySelector('.tool-catalog-events').innerHTML=book.years.map(y=>`<details${y.year===selected?' open':''}><summary>${esc(yearLabel(y.year))}<small>${esc(reign(y))}</small></summary><button data-volume="${book.volume}" data-read="${y.year}" class="tool-read-year">阅读本年 →</button>${y.titles.map((title,i)=>`<button data-volume="${book.volume}" data-read="${y.year}" data-anchor="${y.anchors[i]??0}" class="tool-read-event">${esc(title)}</button>`).join('')}</details>`).join('');}
 function close(restoreFocus=true){panel.hidden=true;shade.hidden=true;active=null;rail.querySelectorAll('button').forEach(b=>b.setAttribute('aria-expanded','false'));mobile.setAttribute('aria-expanded','false');if(volume.parentNode!==volumeHome.parentNode)volumeHome.after(volume);if(restoreFocus&&opener?.isConnected)opener.focus({preventScroll:true});}
 function open(type,button){
  if(type==='notes'){close(false);opener=button;document.querySelector('.annotation-launch').click();return;}
  if(active===type){close();return;}active=type;opener=button;panel.hidden=false;panel.dataset.activeTool=type;panel.setAttribute('aria-label',names[type]||'阅读工具');panel.querySelector('h2').textContent=names[type]||'阅读工具';
  Object.values(sections).forEach(s=>s.hidden=s.dataset.toolSection!==type);
  let menu=body.querySelector('.reader-tool-menu');if(!menu){menu=document.createElement('div');menu.className='reader-tool-menu';menu.innerHTML=Object.entries(names).map(([id,label])=>`<button type="button" data-reader-tool="${id}">${svg(id)}<span>${label}</span></button>`).join('');body.prepend(menu);}menu.hidden=type!=='menu';
  rail.querySelectorAll('button').forEach(b=>b.setAttribute('aria-expanded',String(b.dataset.readerTool===type)));mobile.setAttribute('aria-expanded','true');
  if(type==='catalog'){sections.catalog.querySelector('.tool-volume-slot').append(volume);catalogEntries();}
  else if(volume.parentNode!==volumeHome.parentNode)volumeHome.after(volume);
  syncSize();const compact=matchMedia('(max-width:800px)').matches;shade.hidden=!compact;panel.setAttribute('aria-modal',String(compact));
  const target=[...panel.querySelectorAll('[data-tool-section]:not([hidden]) select,[data-tool-section]:not([hidden]) button,.reader-tool-menu:not([hidden]) button')].find(el=>el.getClientRects().length);target?.focus({preventScroll:true});
 }
 rail.addEventListener('click',e=>{const b=e.target.closest('[data-reader-tool]');if(b)open(b.dataset.readerTool,b);});
 mobile.onclick=()=>{if(active)close();else open('menu',mobile);};
 panel.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.hasAttribute('data-close-tool'))close();else if(b.dataset.readerTool)open(b.dataset.readerTool,mobile);else if(b.dataset.read||b.id==='readerPeople')close(false);else if(b.id==='smaller'||b.id==='larger')syncSize();});
 // The original volume selector continues to call changeVolume and opens its yearbook.
 volume.addEventListener('change',()=>close(false));year.addEventListener('change',()=>close(false));
 shade.onclick=()=>close();
 document.addEventListener('pointerdown',e=>{if(active&&!panel.contains(e.target)&&!rail.contains(e.target)&&!mobile.contains(e.target))close(false);});
 document.addEventListener('keydown',e=>{if(e.key==='Tab'&&active&&matchMedia('(max-width:800px)').matches){const controls=[...panel.querySelectorAll('button,select,input')].filter(el=>!el.disabled&&el.getClientRects().length);const first=controls[0],last=controls.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}if(e.key==='Escape'&&active){e.preventDefault();e.stopImmediatePropagation();close();}},true);
 function sync(){const visible=!reader.classList.contains('hidden');document.body.classList.toggle('tools-reading',visible);yearLabelNode.textContent=book?(readingIndex<0?'卷首':yearLabel(selected)):'';if(!visible)close(false);else if(active==='catalog')catalogEntries();}
 new MutationObserver(sync).observe(reader,{attributes:true,attributeFilter:['class']});
 new MutationObserver(()=>{close(false);sync();}).observe(document.querySelector('#readerContent'),{childList:true});
 window.addEventListener('resize',()=>{if(active){const compact=matchMedia('(max-width:800px)').matches;shade.hidden=!compact;panel.setAttribute('aria-modal',String(compact));}});
 document.querySelector('.annotation-dialog').addEventListener('close',()=>{if(readerOpen&&opener?.isConnected)opener.focus({preventScroll:true});});
 sync();
})();
