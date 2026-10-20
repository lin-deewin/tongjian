// Yearbook-only menus; reading navigation and filtering remain in app.js.
(() => {
 const trigger=document.getElementById('annualFilterTrigger');
 const options=document.getElementById('annualFilterOptions');
 if(!trigger||!options)return;
 const jump=document.getElementById('annualYearJump');
 const volume=document.getElementById('volumeSelect');
 const field=volume.closest('.annual-volume-field');
 const measure=document.createElement('canvas').getContext('2d');
 window.refreshYearbookVolumeLabel=()=>{
  const selected=volume.selectedOptions[0];
  if(!selected)return;
  document.getElementById('annualSelectedVolumeTitle').textContent=selected.dataset.title;
  document.getElementById('annualSelectedVolumeYears').textContent=selected.dataset.years;
  const style=getComputedStyle(volume);
  measure.font=style.font;
  const available=volume.clientWidth-parseFloat(style.paddingLeft)-parseFloat(style.paddingRight);
  field.classList.toggle('is-wrapped',measure.measureText(selected.textContent).width>available);
  const overlay=field.querySelector('.annual-selected-volume');
  volume.style.minHeight=field.classList.contains('is-wrapped')?([...overlay.children].reduce((height,el)=>height+el.offsetHeight,0)+16)+'px':'';
 };
 new ResizeObserver(window.refreshYearbookVolumeLabel).observe(field);
 window.refreshYearbookVolumeLabel();
 const navigation=document.querySelector('body>header .header-right');
 const menu=document.createElement('button');
 menu.type='button';menu.className='annual-site-toggle';menu.textContent='菜单 ⌄';
 navigation.id='readerSiteNavigation';
 menu.setAttribute('aria-controls',navigation.id);menu.setAttribute('aria-expanded','false');
 navigation.before(menu);
 function closeMenu(restoreFocus=false){
  navigation.classList.remove('annual-menu-open');menu.setAttribute('aria-expanded','false');
  if(restoreFocus)menu.focus();
 }
 menu.addEventListener('click',()=>{
  const open=menu.getAttribute('aria-expanded')!=='true';
  navigation.classList.toggle('annual-menu-open',open);menu.setAttribute('aria-expanded',String(open));
 });
 navigation.addEventListener('click',event=>{if(event.target.closest('a,button'))closeMenu();});
 document.addEventListener('click',event=>{if(!navigation.contains(event.target)&&!menu.contains(event.target))closeMenu();});
 document.addEventListener('keydown',event=>{if(event.key==='Escape'&&menu.getAttribute('aria-expanded')==='true'){event.preventDefault();event.stopImmediatePropagation();closeMenu(true);}},true);
 function closeFilters(restoreFocus=false){
  options.classList.remove('is-open');options.inert=true;options.hidden=true;
  trigger.setAttribute('aria-expanded','false');
  if(restoreFocus)trigger.focus({preventScroll:true});
 }
 trigger.addEventListener('click',()=>{
  if(trigger.getAttribute('aria-expanded')==='true'){closeFilters();return;}
  jump.open=false;closeMenu();options.hidden=false;options.inert=false;
  options.getBoundingClientRect();
  options.classList.add('is-open');
  trigger.setAttribute('aria-expanded','true');
 });
 function filterKeys(event){if(event.key==='Escape'&&trigger.getAttribute('aria-expanded')==='true'){event.preventDefault();event.stopPropagation();closeFilters(true);}}
 options.addEventListener('keydown',filterKeys);trigger.addEventListener('keydown',filterKeys);
 document.addEventListener('click',event=>{if(jump.open&&!jump.contains(event.target))jump.open=false;});
 jump.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();event.stopPropagation();jump.open=false;jump.querySelector('summary').focus();}});
 window.addEventListener('popstate',()=>closeFilters());
})();
