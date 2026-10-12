// Reviewed identities and source locations are loaded separately from book text.
let peopleIndex = {people: [], locations: {}}, peopleIndexReady = false;
let peopleOrigin = null, peopleSession = null, peopleView = null;
const peopleCache = new Map();
const peopleFilters = new Map();
const peopleBiographies = new Map();
const biographyPeople = new Set(['p-f6466c6cd5b8', 'p-06fac22214af', 'p-29d2c1938dab', 'p-b0c0b4daac92']);
async function loadPersonBiography(id) {
 if (!biographyPeople.has(id) || peopleBiographies.has(id)) return;
 try {
  const response = await fetch('biographies/' + id + '.json');
  if (!response.ok) throw Error('人物资料加载失败');
  peopleBiographies.set(id, await response.json());
 } catch (error) { console.error(error); }
}
async function loadPeopleIndex() {
 try {
  const response = await fetch('people-index.json?v=20261012-all-ages');
  if (!response.ok) throw Error('人物索引加载失败');
  peopleIndex = await response.json();
  peopleIndexReady = true;
 } catch (error) { console.error(error); }
}
function peopleIdsAt(volume, year, indices) {
 return [...new Set(indices.flatMap(i => peopleIndex.locations[`${volume}:${year}:${i}`] || []))];
}
function personButton(id) {
 const p = peopleIndex.people.find(p => p.id === id);
 return p ? `<button class="person-link" data-person="${esc(id)}">${esc(p.name)}</button>` : '';
}
function decoratePeople() {
 // Only reviewed paragraphs are annotated; generic names never match globally.
 if (!peopleIndexReady || !document.createTreeWalker || readingIndex < 0) return;
 const y = book.years[readingIndex];
 for (const row of document.querySelectorAll('#readerContent .compare-row')) {
  if (row.dataset.peopleDecorated) continue;
  const paragraphs = [...row.querySelectorAll('.original p[id^="para-"]')];
  const allIds = peopleIdsAt(book.volume, y.year, paragraphs.map(p => Number(p.id.slice(5))));
  for (const p of paragraphs) markPersonNames(p, peopleIdsAt(book.volume, y.year, [Number(p.id.slice(5))]));
  for (const p of row.querySelectorAll('.modern-text')) markPersonNames(p, allIds);
  if (allIds.length) {
   const links = document.createElement('div');
   links.className = 'paragraph-people';
   links.innerHTML = '<span>本段人物</span> ' + allIds.map(personButton).join(' · ');
   row.append(links);
  }
  row.dataset.peopleDecorated = 'true';
 }
}
function markPersonNames(element, ids) {
 const names = new Map();
 for (const p of peopleIndex.people.filter(p => ids.includes(p.id))) {
  for (const alias of p.aliases) {
   if (!names.has(alias)) names.set(alias, []);
   names.get(alias).push(p.id);
  }
 }
 if (!names.size) return;
 const pattern = new RegExp([...names.keys()].sort((a,b) => b.length-a.length).map(s => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'g');
 const walker = document.createTreeWalker(element, NodeFilter.SHOW_TEXT);
 const nodes = [];
 while (walker.nextNode()) {
  const node = walker.currentNode;
  if (!node.parentElement.closest('button,.note')) nodes.push(node);
 }
 for (const node of nodes) {
  pattern.lastIndex = 0;
  const matches = [...node.textContent.matchAll(pattern)];
  if (!matches.length) continue;
  const fragment = document.createDocumentFragment();
  let cursor = 0;
  for (const match of matches) {
   fragment.append(document.createTextNode(node.textContent.slice(cursor, match.index)));
   const ids = names.get(match[0]);
   // An ambiguous label is left as text. The paragraph list offers distinct identities.
   if (ids.length !== 1) fragment.append(document.createTextNode(match[0]));
   else {
    const button = document.createElement('button');
    button.className = 'person-name'; button.dataset.person = ids[0];
    button.textContent = match[0]; button.title = '查看人物经历';
    fragment.append(button);
   }
   cursor = match.index + match[0].length;
  }
  fragment.append(document.createTextNode(node.textContent.slice(cursor)));
  node.replaceWith(fragment);
 }
}
function capturePeopleOrigin() {
 if (peopleOrigin) return;
 peopleFilters.clear();
 const currentHash = /^#(?:people|person-)/.test(location.hash) ? (readerOpen ? '#volume-'+book.volume+(readingIndex<0?'-intro':'-year-'+selected) : '#volume-'+(book?.volume||1)) : location.hash;
 peopleOrigin = {
  hash: currentHash || '#volume-1', scroll: window.scrollY,
  volume: book?.volume || 1, year: readerOpen && readingIndex >= 0 ? selected : null,
  intro: readerOpen && readingIndex < 0,
  period, eventFilter, search: $('#search').value, scope: $('#searchScope').value,
  recordedOnly: $('#recordedOnly').checked, readerReturnState,
  mode: readingMode, notes: $('#showNotes').checked,
  cutoff: readerOpen && readingIndex >= 0 ? selected : null
 };
}
function restorePeopleHistory() {
 if (!peopleOrigin || peopleOrigin.hash !== location.hash) return;
 const origin = peopleOrigin;
 peopleOrigin = null; peopleSession = null; peopleView = null;
 updateReaderReturn();
 readerReturnState = origin.readerReturnState;
 if (!readerOpen) {
  period=origin.period; eventFilter=origin.eventFilter;
  $('#search').value=origin.search; $('#searchScope').value=origin.scope;
  $('#recordedOnly').checked=origin.recordedOnly; render();
 }
 requestAnimationFrame(() => window.scrollTo({top:origin.scroll, behavior:'instant'}));
}
function updateReaderReturn() {
 const person = peopleSession && peopleIndex.people.find(p => p.id === peopleSession.id);
 const label = person ? `← 返回${person.name}时间轴` : '← 返回年表';
 $('#closeReader').textContent = label;
 $('#closeReader').setAttribute?.('aria-label', label.replace('← ', ''));
}
function returnFromReader() {
 if (peopleSession) return openPeople(peopleSession.id);
 closeReader();
}
function hidePeoplePage() {
 $('#peoplePage').classList.add('hidden');
 updateReaderReturn();
}
function showPeoplePage() {
 $('#annualPage').classList.add('hidden');
 $('#readerBackdrop').classList.add('hidden');
 $('#peoplePage').classList.remove('hidden');
 updateReaderReturn();
}
function timelineVisible(event, cutoff, showFuture) {
 if (showFuture || cutoff === null) return true;
 // BCE is positive, CE negative; a larger key is earlier. Gate source and event dates.
 return event.sources.every(s => s.year >= cutoff) && (event.year === null || event.year >= cutoff);
}
function selectedPeopleEvents(person, filters) {
 return person.events.filter(e => timelineVisible(e, filters.cutoff, filters.future)
  && (filters.scope === 'all' || e.kind === '主要经历')
  && (filters.category === 'all' || e.category === filters.category));
}
async function openPeople(id = null, updateHistory = true) {
 capturePeopleOrigin();
 const nav = ++navigationId;
 if (peopleView && !$('#peoplePage').classList.contains('hidden')) {
  peopleView.scroll = window.scrollY;
  if (peopleView.id && peopleFilters.has(peopleView.id)) peopleFilters.get(peopleView.id).scroll = window.scrollY;
 }
 showPeoplePage();
 $('#peoplePage').classList.toggle('person-detail-page', Boolean(id));
 peopleView = {id, scroll: peopleFilters.get(id)?.scroll || 0};
 if (updateHistory) history.pushState({people:true}, '', id ? '#person-' + id : '#people');
 $('#peopleContent').innerHTML = '<p role="status">正在载入人物资料…</p>';
 if (!peopleIndexReady) await loadPeopleIndex();
 if (nav !== navigationId) return;
 if (!peopleIndexReady) {
  $('#peopleContent').innerHTML = '<p role="alert">人物资料加载失败，请重试。</p><button data-people-retry>重新加载</button>';
  return;
 }
 if (!id) {
  document.title = '人物档案 · 资治通鉴';
  $('#peopleContent').innerHTML = `<h1>人物档案</h1><p>已收录 ${peopleIndex.people.length} 个人物档案。档案范围见各人物页；全书其他记载可用年表搜索查找。</p><label class="people-search">查找姓名或别名 <input id="peopleSearch" type="search" placeholder="如 吴起、卫鞅" autocomplete="off"></label><div id="peopleDirectory"></div>`;
  renderPeopleDirectory('');
 } else {
  try {
   const meta = peopleIndex.people.find(p => p.id === id);
   if (!meta) throw Error('尚未收录这个人物');
   if (!peopleCache.has(id)) {
    const response = await fetch('people/' + id + '.json?v=20261012-all-ages');
    if (!response.ok) throw Error('人物档案加载失败');
    peopleCache.set(id, await response.json());
   }
   await loadPersonBiography(id);
   if (nav !== navigationId) return;
   const person = peopleCache.get(id);
   const filters = peopleFilters.get(id) || {scope:'major', category:'all', cutoff:peopleOrigin.cutoff, future:peopleOrigin.cutoff === null, scroll:0};
   peopleFilters.set(id, filters);
   document.title = person.name + ' · 人物经历 · 资治通鉴';
   renderPerson(person, filters);
   restoreTimelineOffsets(filters);
  } catch (error) {
   if (nav === navigationId) $('#peopleContent').innerHTML = `<p role="alert">${esc(error.message)}</p><button data-people-retry>重新加载</button>`;
  }
 }
 window.scrollTo({top:peopleView.scroll, behavior:'instant'});
 $('#returnFromPeople').focus({preventScroll:true});
}
function renderPeopleDirectory(query) {
 const people = peopleIndex.people.filter(p => [p.name, ...p.aliases].some(s => s.includes(query.trim())));
 $('#peopleDirectory').innerHTML = people.length ? people.map(p => `<article class="person-card"><h2>${personButton(p.id)}</h2><p>${esc(p.identity)}</p><p class="reading-hint">别名：${esc(p.aliases.filter(a => a !== p.name).join('、') || '未另列')}</p></article>`).join('') : '<p role="status">没有匹配人物，可返回年表使用全书搜索。</p>';
}
function renderPerson(person, filters) {
 const events = selectedPeopleEvents(person, filters);
 const vertical = filters.timelineLayout === 'vertical';
 const biography = peopleBiographies.get(person.id);
 const hasBiography = biographyPeople.has(person.id);
 const biographyPanel = hasBiography && filters.panel !== 'timeline';
 const dated = events.filter(e => e.year !== null).sort((a,b) => b.year-a.year || person.events.indexOf(a)-person.events.indexOf(b));
 const undated = events.filter(e => e.year === null);
 $('#peopleContent').innerHTML = `<div class="person-overview${biography?' person-overview-biography':''}"><div class="person-identity"><button class="person-link" data-people-directory>← 全部人物</button><h1>${esc(person.name)}</h1><p>${esc(person.identity)}</p><p>姓名 / 别名：${esc(person.aliases.join('、'))}</p></div><aside class="person-context">${person.birthStatus==='confirmed'?`<p class="reading-hint">生于${yearLabel(person.birthYear)} · 年龄按年份差估算 <a href="${esc(person.birthSource)}" target="_blank" rel="noopener noreferrer">生年出处 ↗</a></p>`:`<p class="reading-hint">${({unknown:'生年未详',disputed:'生年有争议',approximate:'生年仅有估计',unconfirmed:'生年待核实'})[person.birthStatus]||'生年未详'}</p>`}</aside>${biography?.portrait?`<figure class="person-portrait"><a href="${esc(biography.portrait.originalUrl)}" target="_blank" rel="noopener noreferrer"><img src="${esc(biography.portrait.src)}" width="${biography.portrait.width}" height="${biography.portrait.height}" alt="${esc(person.name)}画像" decoding="async"></a><figcaption>后世画像 · <a href="${esc(biography.portrait.sourceUrl)}" target="_blank" rel="noopener noreferrer">图片出处 ↗</a></figcaption></figure>`:''}</div>${hasBiography?`<nav class="person-panel-tabs" aria-label="人物档案内容"><button data-person-panel="biography" aria-pressed="${biographyPanel}" class="${biographyPanel?'active':''}">人物资料</button><button data-person-panel="timeline" aria-pressed="${!biographyPanel}" class="${!biographyPanel?'active':''}">通鉴时间轴</button></nav>`:''}<div class="person-timeline-panel${biographyPanel?' hidden':''}">${filters.cutoff!==null?`<div class="person-filters"><label><input type="checkbox" id="peopleFuture" ${filters.future?'checked':''}>查看后续经历</label></div>`:''}${events.length ? `<div class="timeline-layout-controls"><button data-timeline-layout aria-pressed="${vertical}">${vertical?'切换为水平时间轴':'切换为竖向时间轴'}</button></div>${dated.length?`${horizontalTimeline("dated", "有明确年份的经历", dated, "", person) }`:''}${undated.length?`${horizontalTimeline("undated", "追叙、年份未详与评论", undated.sort((a,b)=>a.sources[0].volume-b.sources[0].volume||b.sources[0].year-a.sources[0].year||a.sources[0].indices[0]-b.sources[0].indices[0]), "以下条目按出处顺序排列，不把记载年份当作发生年份。", person) }`:''}`:'<p class="no-result">当前范围没有已收录记载。</p>'}</div>${biographyPanel ? renderPersonBiography(person, biography) : ''}`;
}
function renderPersonBiography(person, biography) {
 if (!biography) return '<div class="biography-unavailable"><p role="alert">人物资料暂时无法加载。</p><button class="person-link" data-biography-retry>重试加载</button></div>';
 const link = (url, label) => `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer">${esc(label)}</a>`;
 const attribution = `资料来自${link(biography.sourceUrl, '中文维基百科《' + person.name + '》')}及其${link(biography.historyUrl, '贡献者')}，按 ${link(biography.licenseUrl, biography.license)} 转载。快照日期 ${esc(biography.fetchedAt.slice(0,10))} · ${link(biography.revisionUrl, '原始版本')}。`;
 return `<section class="person-biography" aria-label="${esc(person.name)}人物资料"><div class="biography-source">${attribution}</div><div class="biography-layout"><aside class="biography-toc"><details${window.innerWidth > 650?' open':''}><summary>章节目录</summary><nav aria-label="人物资料章节"><a href="#wiki-${esc(person.id)}-intro" data-wiki-anchor="wiki-${esc(person.id)}-intro">人物概览</a>${biography.sections.map(section => `<a href="#${esc(section.id)}" data-wiki-anchor="${esc(section.id)}" class="toc-level-${section.level}">${esc(section.title)}</a>`).join('')}<a href="#wiki-${esc(person.id)}-credits" data-wiki-anchor="wiki-${esc(person.id)}-credits">来源与图片许可</a></nav></details></aside><div class="biography-reading"><article class="wiki-article" id="wiki-${esc(person.id)}-intro">${biography.html}</article><footer class="biography-credits" id="wiki-${esc(person.id)}-credits"><h2>来源与图片许可</h2><p>${attribution}</p><p>${esc(biography.adaptation)} 本页转载文字沿用 CC BY-SA 4.0；图片依各自许可使用。图片可点击查看原始分辨率。</p><details><summary>查看 ${biography.images.length} 张图片的作者与许可</summary><ul>${biography.images.map(image => `<li>${link(image.sourceUrl, image.file.replace(/^File:/,''))} · ${esc(image.artist || '作者见图片出处')} · ${image.licenseUrl?link(image.licenseUrl, image.license):esc(image.license)} · 原图 ${image.originalWidth} × ${image.originalHeight}</li>`).join('')}</ul></details></footer></div></div></section>`;
}
function horizontalTimeline(id, title, events, hint, person) {
 const vertical = peopleFilters.get(person.id)?.timelineLayout === 'vertical';
 return `<section class="timeline-section${vertical?' timeline-section-vertical':''}"><div class="timeline-heading"><h2>${esc(title)}</h2><div class="timeline-controls${vertical?' hidden':''}"><button data-timeline-step="-1" data-timeline-id="${id}" aria-label="向左浏览${esc(title)}">←</button><button data-timeline-step="1" data-timeline-id="${id}" aria-label="向右浏览${esc(title)}">→</button></div></div>${hint?`<p class="reading-hint">${esc(hint)}</p>`:''}<ol class="person-timeline${vertical?' timeline-vertical':''}" id="timeline-${id}" data-timeline-track="${id}" tabindex="0" aria-label="${esc(title)}，${vertical?'竖向':'横向'}浏览">${events.map(event => personEventHtml(event, person)).join('')}</ol></section>`;
}
function restoreTimelineOffsets(filters) {
 if (!document.getElementById) return;
 for (const [id, left] of Object.entries(filters.timelineOffsets || {})) {
  const track = document.getElementById('timeline-' + id);
  if (track && filters.timelineLayout !== 'vertical') track.scrollLeft = left;
 }
}
function personEventAge(event, person) {
 const validYear = year => Number.isInteger(year) && year !== 0;
 if (person?.birthStatus !== 'confirmed' || !person.birthSource || !validYear(person.birthYear) || !validYear(event.year)) return null;
 // Convert the project's BC-positive year keys to a continuous axis without year zero.
 const chronological = year => year > 0 ? 1 - year : -year;
 const eventTime = chronological(event.year), birthTime = chronological(person.birthYear);
 if (eventTime < birthTime || (validYear(person.deathYear) && eventTime > chronological(person.deathYear))) return null;
 return eventTime - birthTime;
}
function personEventHtml(event, person) {
 const age = personEventAge(event, person);
 const source = event.sources[0];
 const title = source ? `<a class="timeline-event-link" href="#volume-${source.volume}-year-${source.year}-para-${source.indices[0]}" data-person-source="${esc(event.id)}" data-source-volume="${source.volume}" data-source-year="${source.year}" data-source-anchor="${source.indices[0]}">${esc(event.title)}</a>` : esc(event.title);
 return `<li><div class="timeline-date">${esc(event.timeLabel)}${age!==null?` <em class="event-age">约${age}岁</em>`:''} <span>${esc(event.kind)} · ${esc(event.category)}</span></div><div class="timeline-event"><h3>${title}</h3>${event.dateNote && event.dateNote!=="依原书本年记事。"?`<p class="reading-hint">${esc(event.dateNote)}</p>`:""}${event.sources.map(s => `<div class="timeline-source"><details><summary>原文依据 · 第${s.volume}卷 · ${yearLabel(s.year)}记载</summary><p class="serif">${esc(s.quote)}</p></details></div>`).join('')}</div></li>`;
}
async function returnFromPeople() {
 const origin = peopleOrigin;
 peopleOrigin = null; peopleSession = null; peopleView = null;
 hidePeoplePage();
 if (!origin) { await changeVolume(1); return; }
 $('#showNotes').checked = origin.notes;
 readingMode = origin.mode;
 if (origin.year !== null) await openYear(origin.volume, origin.year);
 else if (origin.intro) { await changeVolume(origin.volume, false); volumeIntro(); }
 else {
  await changeVolume(origin.volume);
  period=origin.period; eventFilter=origin.eventFilter;
  $('#search').value=origin.search; $('#searchScope').value=origin.scope;
  $('#recordedOnly').checked=origin.recordedOnly;
  if (origin.scope==='all' && origin.search) searchChanged(); else render();
 }
 readerReturnState = origin.readerReturnState;
 requestAnimationFrame(() => window.scrollTo({top:origin.scroll, behavior:'instant'}));
}
async function routePeopleHash(hash) {
 const match = hash.match(/^#person-([a-z0-9-]+)$/);
 if (hash !== '#people' && !match) return false;
 // A direct link starts without a reader; do not pretend to have a saved origin.
 await openPeople(match ? match[1] : null, false);
 return true;
}
document.addEventListener('click', async event => {
 const wikiAnchor = event.target.closest('a[data-wiki-anchor]');
 if (wikiAnchor) {
  event.preventDefault();
  const destination = document.getElementById(wikiAnchor.dataset.wikiAnchor);
  if (destination) {
   for (let parent = destination.parentElement; parent; parent = parent.parentElement) {
    if (parent.tagName === 'DETAILS') parent.open = true;
   }
   destination.scrollIntoView({behavior:'instant', block:'start'});
   destination.setAttribute('tabindex', '-1');
   destination.focus({preventScroll:true});
  }
  return;
 }
 const b = event.target.closest('button, a[data-person-source]');
 if (!b) return;
 if (b.dataset.personPanel !== undefined && peopleView?.id) {
  const filters = peopleFilters.get(peopleView.id);
  filters.panel = b.dataset.personPanel;
  renderPerson(peopleCache.get(peopleView.id), filters);
  restoreTimelineOffsets(filters);
  document.querySelector(`[data-person-panel="${filters.panel}"]`)?.focus({preventScroll:true});
 }
 if (b.dataset.biographyRetry !== undefined && peopleView?.id) {
  const id = peopleView.id;
  await loadPersonBiography(id);
  if (peopleView?.id === id) renderPerson(peopleCache.get(id), peopleFilters.get(id));
 }
 if (b.dataset.timelineLayout !== undefined && peopleView?.id) {
  const filters = peopleFilters.get(peopleView.id);
  filters.timelineLayout = filters.timelineLayout === 'vertical' ? 'horizontal' : 'vertical';
  renderPerson(peopleCache.get(peopleView.id), filters);
  restoreTimelineOffsets(filters);
  document.querySelector('[data-timeline-layout]')?.focus({preventScroll:true});
 }
 if (b.dataset.timelineStep) {
  const track = document.getElementById('timeline-' + b.dataset.timelineId);
  track?.scrollBy({left:Number(b.dataset.timelineStep)*track.clientWidth*0.85, behavior:'smooth'});
 }
 if (b.dataset.person) { await openPeople(b.dataset.person); }
 if (b.id === 'openPeople' || b.id === 'readerPeople' || b.dataset.peopleDirectory !== undefined) await openPeople();
 if (b.id === 'returnFromPeople') await returnFromPeople();
 if (b.dataset.peopleRetry !== undefined) await openPeople(peopleView?.id || null, false);
 if (b.dataset.personSource) {
  event.preventDefault();
  const filters = peopleFilters.get(peopleView.id);
  filters.scroll = window.scrollY;
  peopleSession = {id:peopleView.id};
  await openYear(+b.dataset.sourceVolume, +b.dataset.sourceYear, +b.dataset.sourceAnchor);
 }
});
document.addEventListener('input', event => {
 if (event.target.id === 'peopleSearch') renderPeopleDirectory(event.target.value);
});
document.addEventListener('change', event => {
 if (!['peopleScope','peopleCategory','peopleFuture'].includes(event.target.id) || !peopleView?.id) return;
 const filters = peopleFilters.get(peopleView.id);
 if (event.target.id === 'peopleScope') filters.scope = event.target.value;
 if (event.target.id === 'peopleCategory') filters.category = event.target.value;
 if (event.target.id === 'peopleFuture') filters.future = event.target.checked;
 renderPerson(peopleCache.get(peopleView.id), filters);
 $('#'+event.target.id)?.focus({preventScroll:true});
});

// Remember horizontal position when visiting a source passage and returning.
document.addEventListener('scroll', event => {
 const id = event.target.dataset?.timelineTrack;
 if (!id || !peopleView?.id) return;
 const filters = peopleFilters.get(peopleView.id);
 if (filters && filters.timelineLayout !== 'vertical') { (filters.timelineOffsets ||= {})[id] = event.target.scrollLeft; }
}, true);

function renderVolumePeople() {
 const section = $('#volumePeople');
 const visible = eventFilter === 'person';
 section.classList.toggle('hidden', !visible);
 if (!visible) return;
 const people = peopleIndex.people.filter(p => p.mainVolumes?.includes(book.volume));
 section.innerHTML = people.length ? `<div class="volume-people-list">${people.map(p => `<button class="volume-person-circle" data-person="${esc(p.id)}" aria-label="查看${esc(p.name)}时间轴">${esc(p.name)}</button>`).join('')}</div>` : `<p class="reading-hint">${peopleIndexReady?'本卷人物档案尚在整理。':'人物资料暂时无法加载，请刷新重试。'}</p>`;
}
