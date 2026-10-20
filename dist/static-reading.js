// Progressive reading controls: the complete article and links work without JS.
(() => {
  const filter = document.querySelector('#peopleFilter');
  if (filter) {
    document.querySelector('.directory-search').hidden = false;
    const items = [...document.querySelectorAll('#staticPeopleList li')];
    const status = document.querySelector('#peopleFilterStatus');
    filter.addEventListener('input', () => {
      const query = filter.value.trim().toLocaleLowerCase();
      let count = 0;
      for (const item of items) {
        item.hidden = !item.dataset.names.toLocaleLowerCase().includes(query);
        if (!item.hidden) count++;
      }
      status.textContent = count ? `找到 ${count} 人` : '未找到，可到逐年阅读器搜索全书。';
    });
  }
  const controls = document.querySelector('.reading-controls');
  if (!controls) return;
  controls.hidden = false;
  const mode = document.querySelector('#staticMode');
  const notes = document.querySelector('#staticNotes');
  let size = 19;
  function remember(){
    const blocks=[...document.querySelectorAll('.source-original,.modern-text')].filter(p=>p.getClientRects().length);
    const block=blocks.find(p=>p.getBoundingClientRect().bottom>24);
    if(!block)return null;
    const box=block.getBoundingClientRect();return {block,ratio:Math.max(0,(24-box.top)/box.height),top:Math.max(24,box.top)};
  }
  function restore(saved){requestAnimationFrame(()=>{
    if(!saved)return;
    let block=saved.block;
    if(!block.getClientRects().length)block=[...(block.closest('.comparison-row')?.querySelectorAll('.source-original,.modern-text')||[])].find(p=>p.getClientRects().length);
    if(block){const box=block.getBoundingClientRect();window.scrollBy({top:box.top+box.height*saved.ratio-saved.top,behavior:'instant'});}
  });}
  let position=null;
  window.addEventListener('scroll',()=>{position=remember();},{passive:true});
  window.addEventListener('resize',()=>restore(position));
  mode.addEventListener('change', () => {
    const saved=remember();restore(saved);
    document.body.classList.toggle('mode-original', mode.value === 'original');
    document.body.classList.toggle('mode-modern', mode.value === 'modern');
    notes.disabled = mode.value === 'modern';
  });
  notes.addEventListener('change', () => {const saved=remember();document.body.classList.toggle('hide-notes', !notes.checked);restore(saved);});
  for (const [id, delta] of [['staticSmaller', -1], ['staticLarger', 1]]) {
    document.getElementById(id).addEventListener('click', () => {
      const saved=remember();restore(saved);
      size = Math.max(15, Math.min(28, size + delta));
      document.documentElement.style.setProperty('--reading-size', size + 'px');
    });
  }
})();
