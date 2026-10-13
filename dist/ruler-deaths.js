'use strict';
const $ = selector => document.querySelector(selector);
const escapeHtml = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nonnaturalCategories = new Set(['killed','suicide','poison','starved','battle','accident']);
const pageSize = 20;
let data = null, categories = new Map(), eraLabels = new Map();
let rows = [], page = 1, selectedId = null;
let filters = {query:'', era:'all', polity:'all', cause:'all', sort:'earliest'};
const yearLabel = year => year > 0 ? `前${year}年` : `${-year}年`;
const percent = (count, total) => total ? Math.round(count / total * 100) + '%' : '—';
const tally = records => {
 const counts = new Map(data.categories.map(c => [c.id, 0]));
 records.forEach(row => counts.set(row.category, counts.get(row.category) + 1));
 return counts;
};
const categoryTag = row => {
 const category = categories.get(row.category);
 return `<span class="cause-tag" style="--cause:${category.color}"><span class="color-dot" aria-hidden="true"></span>${escapeHtml(category.label)}</span>`;
};

async function load() {
 $('#loadingState').hidden = false;
 try {
  const response = await fetch('ruler-deaths.json?v=20261012');
  if (!response.ok) throw new Error('资料读取失败');
  const incoming = await response.json();
  if (!Array.isArray(incoming.rows) || !incoming.rows.length) throw new Error('资料暂未就绪');
  data = incoming;
  categories = new Map(data.categories.map(c => [c.id,c]));
  eraLabels = new Map(data.eras.map(e => [e.id,e.label]));
  $('#eraFilter').innerHTML = '<option value="all">全部时代</option>' + data.eras.map(e => `<option value="${e.id}">${escapeHtml(e.label)}</option>`).join('');
  $('#polityFilter').innerHTML = '<option value="all">全部政权</option>' + [...new Set(data.rows.map(r => r.polity))].map(polity => `<option value="${escapeHtml(polity)}">${escapeHtml(polity)}</option>`).join('');
  $('#causeFilter').innerHTML = '<option value="all">全部结局</option>' + data.categories.map(c => `<option value="${c.id}">${escapeHtml(c.label)}</option>`).join('');
  readUrl();
  $('#coverageNote').textContent = `前403年至公元959年 · 当前已核对 ${data.rows.length} 位君主的死亡记录，尚非全书君主的穷尽名单。比例仅代表这些记录；分类为本站整理。`;
  $('#categoryDefinitions').innerHTML = data.categories.map(c => `<dt>${escapeHtml(c.label)}</dt><dd>${escapeHtml(c.definition)}</dd>`).join('');
  $('#chartLegend').innerHTML = data.categories.map(c => `<button type="button" data-cause="${c.id}" style="--cause:${c.color}" title="${escapeHtml(c.definition)}"><span class="color-dot" aria-hidden="true"></span>${escapeHtml(c.label)}</button>`).join('');
  renderStories();
  render(false);
  $('#loadingState').hidden = true;
 } catch (error) {
  $('#loadingState').innerHTML = `${escapeHtml(error.message)}。<button type="button" data-retry>重试</button>`;
  $('#loadingState').setAttribute('role','alert');
 }
}

function readUrl() {
 const params = new URLSearchParams(location.search);
 filters.query = params.get('q') || '';
 filters.era = eraLabels.has(params.get('era')) ? params.get('era') : 'all';
 filters.cause = categories.has(params.get('cause')) ? params.get('cause') : 'all';
 filters.polity = data.rows.some(r => r.polity === params.get('polity')) ? params.get('polity') : 'all';
 filters.sort = ['earliest','latest','name'].includes(params.get('sort')) ? params.get('sort') : 'earliest';
 page = Math.max(1, Math.floor(Number(params.get('page')) || 1));
}
function saveUrl() {
 const url = new URL(location.href);
 url.search = '';
 for (const [key,value] of Object.entries({q:filters.query, era:filters.era, polity:filters.polity, cause:filters.cause, sort:filters.sort})) {
  if (value && value !== 'all' && !(key === 'sort' && value === 'earliest')) url.searchParams.set(key,value);
 }
 if (page > 1) url.searchParams.set('page',String(page));
 history.replaceState(null,'',url);
}
function applyFilters() {
 const query = filters.query.trim().toLocaleLowerCase();
 rows = data.rows.filter(row => (filters.era === 'all' || row.era === filters.era)
  && (filters.polity === 'all' || row.polity === filters.polity)
  && (filters.cause === 'all' || row.category === filters.cause)
  && (!query || [row.name,row.personalName,row.polity,row.reason,categories.get(row.category).label].join(' ').toLocaleLowerCase().includes(query)));
 rows.sort((a,b) => filters.sort === 'name' ? a.name.localeCompare(b.name,'zh-CN')
  : filters.sort === 'latest' ? a.year-b.year || a.name.localeCompare(b.name,'zh-CN')
  : b.year-a.year || a.sources[0].volume-b.sources[0].volume || a.sources[0].anchor-b.sources[0].anchor);
 page = Math.min(page, Math.max(1, Math.ceil(rows.length / pageSize)));
}
function render(updateUrl=true) {
 if (!data) return;
 applyFilters();
 $('#rulerSearch').value = filters.query;
 $('#eraFilter').value = filters.era;
 $('#polityFilter').value = filters.polity;
 $('#causeFilter').value = filters.cause;
 $('#sortOrder').value = filters.sort;
 const counts = tally(rows);
 const nonnatural = rows.filter(row => nonnaturalCategories.has(row.category)).length;
 $('#metrics').innerHTML = [
  [rows.length,'当前记录','每位君主只计一次',''],
  [nonnatural,'明确的非自然结局',`占当前记录 ${percent(nonnatural,rows.length)}`,'emphasis'],
  [counts.get('unknown'),'所引原文未述死因','不把“崩”当成寿终正寝',''],
  [counts.get('disputed'),'记载存疑或原因交织','保留异说，暂不强行归类','']
 ].map(([value,label,note,className]) => `<div class="metric ${className}"><strong>${value}</strong><p class="metric-label">${label}</p><small>${escapeHtml(note)}</small></div>`).join('');
 const active = [filters.era !== 'all' && eraLabels.get(filters.era), filters.polity !== 'all' && filters.polity,
  filters.cause !== 'all' && categories.get(filters.cause).label, filters.query && `“${filters.query}”`].filter(Boolean);
 $('#filterStatus').textContent = `${active.length ? active.join(' · ') : '全部已收录记录'} · ${rows.length} 位君主。图形与表格同步筛选。`;
 renderDistribution(counts,nonnatural);
 renderLives();
 renderEras();
 renderTable();
 if (updateUrl) saveUrl();
}
function renderDistribution(counts,nonnatural) {
 const circumference = 2*Math.PI*65;
 let offset = 0;
 const arcs = data.categories.map(category => {
  const length = rows.length ? counts.get(category.id)/rows.length*circumference : 0;
  const arc = `<circle cx="100" cy="100" r="65" fill="none" stroke="${category.color}" stroke-width="20" stroke-dasharray="${length} ${circumference}" stroke-dashoffset="${-offset}" transform="rotate(-90 100 100)"><title>${escapeHtml(category.label)}：${counts.get(category.id)} 位</title></circle>`;
  offset += length;
  return length ? arc : '';
 }).join('');
 $('#distribution').innerHTML = `<div class="donut"><svg viewBox="0 0 200 200" role="img" aria-label="当前${rows.length}条记录的结局分布"><circle cx="100" cy="100" r="65" fill="none" stroke="#e6e4db" stroke-width="20"/>${arcs}<text class="donut-total" x="100" y="102" text-anchor="middle">${rows.length}</text><text class="donut-label" x="100" y="123" text-anchor="middle">位君主 / 当前记录</text></svg></div><div class="distribution-caption"><strong>${percent(nonnatural,rows.length)}</strong>当前记录中，明确记有非自然结局。<p class="chart-note">包含被杀、自尽、中毒、困围饿死、交战身亡与意外；存疑者不计入。</p></div>`;
 $('#causeBars').innerHTML = data.categories.map(category => {
  const count = counts.get(category.id);
  const share = rows.length ? count/rows.length*100 : 0;
  return `<button type="button" class="cause-bar" data-cause="${category.id}" aria-pressed="${filters.cause===category.id}" aria-label="筛选${escapeHtml(category.label)}，${count}位，占${percent(count,rows.length)}" style="--cause:${category.color};--share:${share}%"><span class="cause-name"><span class="color-dot" aria-hidden="true"></span>${escapeHtml(category.label)}</span><span class="bar-track" aria-hidden="true"><span class="bar-fill"></span></span><span class="cause-value">${count} · ${percent(count,rows.length)}</span></button>`;
 }).join('');
}
function renderLives() {
 const chronological = [...rows].sort((a,b) => b.year-a.year || a.sources[0].volume-b.sources[0].volume || a.sources[0].anchor-b.sources[0].anchor);
 $('#lifeGrid').innerHTML = chronological.length ? chronological.map(row => {
  const category = categories.get(row.category);
  const label = `${row.name} · ${row.polity} · 记于${yearLabel(row.year)} · ${category.label}`;
  return `<button type="button" class="life-dot" data-ruler="${row.id}" data-category="${row.category}" aria-pressed="${selectedId===row.id}" aria-label="${escapeHtml(label)}，查看原文" title="${escapeHtml(label)}" style="--cause:${category.color}"></button>`;
 }).join('') : '<p class="chart-note">当前筛选没有记录，试试重置筛选。</p>';
 if (!chronological.some(row => row.id === selectedId)) {
  selectedId = null;
  $('#lifeSelection').textContent = '点选一个名字，展开原文依据。';
 }
}
function renderEras() {
 $('#eraChart').innerHTML = data.eras.map(era => {
  const records = rows.filter(row => row.era === era.id);
  const counts = tally(records);
  return `<div class="era-row"><button type="button" class="era-name" data-era="${era.id}" aria-pressed="${filters.era===era.id}">${escapeHtml(era.label)}</button><div class="era-stack" aria-label="${escapeHtml(era.label)}，${records.length}位，结局分布">${data.categories.filter(c => counts.get(c.id)).map(c => `<button type="button" class="era-segment" data-era="${era.id}" data-cause="${c.id}" style="--cause:${c.color};--count:${counts.get(c.id)}" title="${escapeHtml(era.label+' · '+c.label)}：${counts.get(c.id)}位，${percent(counts.get(c.id),records.length)}" aria-label="筛选${escapeHtml(era.label+'的'+c.label)}，${counts.get(c.id)}位，占${percent(counts.get(c.id),records.length)}"></button>`).join('')}</div><span>${records.length} 位</span></div>`;
 }).join('');
}
function renderStories() {
 const stories = [
  ['秦武王','举鼎而亡','力量未能护住自己。原文记，与孟说举鼎，“绝脉而薨”。'],
  ['赵武灵王','饿死宫中','曾推行胡服骑射，最终被围沙丘宫，欲出不得、又不得食。'],
  ['曹髦','殒于车下','面对权臣，他亲自出宫讨伐。成济抽戈前刺，皇帝殒于车下。'],
  ['唐宪宗','暴崩疑云','服金丹、宦官弑逆之说并见。《通鉴》留下“外人莫能明也”。']
 ];
 $('#storyCards').innerHTML = stories.map(([name,title,description]) => {
  const row = data.rows.find(r => r.name===name);
  if (!row) return '';
  const category = categories.get(row.category);
  return `<button type="button" class="story-card" data-ruler="${row.id}" style="--cause:${category.color}"><span class="story-category">${escapeHtml(category.label)}</span><h3>${escapeHtml(title)}</h3><p class="story-name">${escapeHtml(row.name)} · ${escapeHtml(row.polity)}</p><p class="story-description">${escapeHtml(description)}</p><span class="story-link">读这段原文 ↗</span></button>`;
 }).join('');
}
function renderTable() {
 const current = rows.slice((page-1)*pageSize,page*pageSize);
 $('#rulerRows').innerHTML = current.length ? current.map(row => `<tr data-row-id="${row.id}"><td><button type="button" class="ruler-name" data-ruler="${row.id}">${escapeHtml(row.name)}</button>${row.personalName?`<small>${escapeHtml(row.personalName)}</small>`:''}</td><td>${escapeHtml(row.polity)}<small>${escapeHtml(eraLabels.get(row.era))}</small></td><td class="year-cell">${yearLabel(row.year)}${row.timeNote.startsWith('年份为')?'':'<small>附叙 / 时间说明</small>'}</td><td>${categoryTag(row)}</td><td class="reason-cell">${escapeHtml(row.reason)}</td><td class="source-cell"><button type="button" data-ruler="${row.id}">展开依据</button><a href="${escapeHtml(row.sources[0].href)}" target="_blank" rel="noopener noreferrer">第${row.sources[0].volume}卷 ↗</a></td></tr>`).join('') : '<tr><td colspan="6" class="empty-row">没有符合条件的记录。可尝试清除搜索或重置筛选。</td></tr>';
 const pages = Math.max(1,Math.ceil(rows.length/pageSize));
 $('#pagination').innerHTML = `<button type="button" data-page="${page-1}" ${page===1?'disabled':''}>← 上一页</button><span>第 ${page} / ${pages} 页 · ${rows.length} 条</span><button type="button" data-page="${page+1}" ${page===pages?'disabled':''}>下一页 →</button>`;
 $('#exportCsv').disabled = !rows.length;
}
function openRuler(id) {
 const row = data.rows.find(row => row.id===id);
 if (!row) return;
 selectedId = id;
 $('#lifeSelection').innerHTML = `<strong>${escapeHtml(row.name)}</strong>${escapeHtml(categories.get(row.category).label)} · 记于${yearLabel(row.year)}<button type="button" data-ruler="${row.id}">核对原文 ↗</button>`;
 document.querySelectorAll('.life-dot').forEach(dot => dot.setAttribute('aria-pressed',String(dot.dataset.ruler===id)));
 const quotes = row.sources.map((source,index) => {
  let quote = escapeHtml(source.quote);
  if (!index && row.witness) quote = quote.replace(escapeHtml(row.witness),`<mark>${escapeHtml(row.witness)}</mark>`);
  return `<section class="detail-source"><h3>${index?'补充上下文 · ':''}第${source.volume}卷 · ${yearLabel(source.year)}记载</h3><blockquote>${quote}</blockquote><a href="${escapeHtml(source.href)}" target="_blank" rel="noopener noreferrer">打开通鉴，定位这一段 ↗</a></section>`;
 }).join('');
 $('#detailContent').innerHTML = `<h2 id="detailTitle">${escapeHtml(row.name)}</h2><p class="detail-meta">${escapeHtml(row.polity)} · ${escapeHtml(eraLabels.get(row.era))}${row.personalName?' · '+escapeHtml(row.personalName):''}</p>${categoryTag(row)}<p class="detail-reason">${escapeHtml(row.reason)}</p><p class="detail-time">${escapeHtml(row.timeNote)}</p>${quotes}${row.personHref?`<a class="detail-profile" href="${escapeHtml(row.personHref)}" target="_blank" rel="noopener noreferrer">查看人物档案与时间轴 ↗</a>`:''}<p class="detail-status">引文为上传胡三省注本原文；分类及解释为本站整理。存疑与未述条目不会自动归为自然死亡。</p>`;
 if (!$('#rulerDetail').open) $('#rulerDetail').showModal();
 $('#closeDetail').focus({preventScroll:true});
}
function exportCsv() {
 const fields = ['君主','姓名补充','政权','时代','通鉴记载年','结局','具体因素与处境','时间说明','原文出处'];
 const quote = value => '"'+String(value??'').replace(/"/g,'""')+'"';
 const content = '\uFEFF' + [fields,...rows.map(row => [row.name,row.personalName,row.polity,eraLabels.get(row.era),yearLabel(row.year),categories.get(row.category).label,row.reason,row.timeNote,row.sources.map(s => `第${s.volume}卷 ${yearLabel(s.year)} 段落${s.anchor}`).join('；')])].map(row => row.map(quote).join(',')).join('\r\n');
 const url = URL.createObjectURL(new Blob([content],{type:'text/csv;charset=utf-8;'}));
 const anchor = document.createElement('a');
 anchor.href = url; anchor.download = '通鉴中的君主之死.csv'; anchor.click();
 setTimeout(() => URL.revokeObjectURL(url),1000);
}

document.addEventListener('input',event => {
 if (event.target.id==='rulerSearch' && data) {filters.query=event.target.value; page=1; render();}
});
document.addEventListener('change',event => {
 const keys = {eraFilter:'era',polityFilter:'polity',causeFilter:'cause',sortOrder:'sort'};
 if (keys[event.target.id] && data) {filters[keys[event.target.id]]=event.target.value; page=1; render();}
});
document.addEventListener('click',event => {
 const button = event.target.closest('button');
 if (!button) return;
 if (button.hasAttribute('data-retry')) {load(); return;}
 if (button.id==='closeDetail') {$('#rulerDetail').close(); return;}
 if (!data) return;
 if (button.id==='resetFilters') {filters={query:'',era:'all',polity:'all',cause:'all',sort:'earliest'};page=1;render();return;}
 if (button.id==='exportCsv') {exportCsv();return;}
 if (button.dataset.ruler) {openRuler(button.dataset.ruler);return;}
 if (button.dataset.page) {page=Number(button.dataset.page);renderTable();saveUrl();$('#recordsTitle').scrollIntoView({behavior:'instant',block:'start'});$('#recordsTitle').setAttribute('tabindex','-1');$('#recordsTitle').focus({preventScroll:true});return;}
 if (button.dataset.era || button.dataset.cause) {
  const targetEra = button.dataset.era;
  const targetCause = button.dataset.cause;
  const toggleOff = (!targetEra || filters.era===targetEra) && (!targetCause || filters.cause===targetCause);
  if (targetEra) filters.era=toggleOff?'all':targetEra;
  if (targetCause) filters.cause=toggleOff?'all':targetCause;
  const surface=button.closest('#causeBars,#chartLegend,#eraChart')?.id;
  page=1;render();
  const selector=(targetEra?`[data-era="${targetEra}"]`:'')+(targetCause?`[data-cause="${targetCause}"]`:'');
  if (surface) document.querySelector(`#${surface} ${selector}`)?.focus({preventScroll:true});
 }
});
$('#rulerDetail').addEventListener('click',event => {
 if (event.target!==$('#rulerDetail')) return;
 const box=event.target.getBoundingClientRect();
 if (event.clientX<box.left || event.clientX>box.right || event.clientY<box.top || event.clientY>box.bottom) event.target.close();
});
window.addEventListener('popstate',() => {if (data) {readUrl();render(false);}});
load();
