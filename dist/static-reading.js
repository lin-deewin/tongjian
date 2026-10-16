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
  mode.addEventListener('change', () => {
    document.body.classList.toggle('mode-original', mode.value === 'original');
    document.body.classList.toggle('mode-modern', mode.value === 'modern');
    notes.disabled = mode.value === 'modern';
  });
  notes.addEventListener('change', () => document.body.classList.toggle('hide-notes', !notes.checked));
  for (const [id, delta] of [['staticSmaller', -1], ['staticLarger', 1]]) {
    document.getElementById(id).addEventListener('click', () => {
      size = Math.max(15, Math.min(28, size + delta));
      document.documentElement.style.setProperty('--reading-size', size + 'px');
    });
  }
})();
