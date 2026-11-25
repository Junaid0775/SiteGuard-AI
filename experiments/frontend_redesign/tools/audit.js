(() => {
  const main = document.querySelector('[data-testid="stMain"]'), app = document.querySelector('[data-testid="stApp"]'), vw = innerWidth;
  const key = e => [...e.classList].find(c => c.startsWith('st-key-'));
  const desc = e => (e.dataset.testid || e.tagName.toLowerCase()) + (key(e) ? '.' + key(e) : '') + ':' + ((e.innerText || e.value || '') + '').trim().slice(0, 28).replace(/\s+/g, ' ');
  const scroller = e => (e.closest('[role="tablist"]') && tabScroll(e)) || e.closest('[data-testid="stDataFrame"], iframe, .js-plotly-plot, [data-testid="stPlotlyChart"], pre, [data-testid="stCode"], [data-testid="stImage"], [data-testid="stFileUploaderDropzone"]');
  const tabScroll = e => { const t = e.closest('[role="tablist"]'); return t && ['auto', 'scroll'].includes(getComputedStyle(t).overflowX); };
  const vis = e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; };
  const r = {};
  r.pageOverflow = Math.max(document.documentElement.scrollWidth - vw, main.scrollWidth - main.clientWidth);
  const all = [...main.querySelectorAll('*')].filter(e => !scroller(e) && vis(e));
  r.clipped = all.filter(e => { const cs = getComputedStyle(e); return ['hidden', 'clip'].includes(cs.overflowX) && e.scrollWidth > e.clientWidth + 2 && e.children.length < 3 && (e.innerText || '').trim(); }).map(desc).slice(0, 5);
  r.inputsCut = [...main.querySelectorAll('input')].filter(e => vis(e) && e.type !== 'file' && e.type !== 'radio' && e.type !== 'checkbox' && e.scrollWidth > e.clientWidth + 2).map(e => (e.getAttribute('aria-label') || e.placeholder || '') + '=' + e.value.slice(0, 30));
  r.metricCut = [...main.querySelectorAll('[data-testid="stMetric"]')].filter(m => [...m.querySelectorAll('*')].some(c => c.getBoundingClientRect().right > m.getBoundingClientRect().right + 1 && (c.innerText || '').trim())).map(desc);
  r.beyondViewport = all.filter(e => e.getBoundingClientRect().right > vw + 1 && (e.innerText || '').trim() && !e.closest('[data-testid="stSidebar"]')).map(desc).slice(0, 3);
  r.panelOverflow = [...main.querySelectorAll('[class*="st-key-sg-panel-"]')].map(p => { const pr = p.getBoundingClientRect(); const bad = [...p.querySelectorAll('*')].filter(c => !scroller(c) && vis(c) && !c.closest('[data-testid^="hidden"]') && (c.getBoundingClientRect().right > pr.right + 1 || c.getBoundingClientRect().left < pr.left - 1)); return bad.length ? key(p) + ':' + desc(bad[0]) : null; }).filter(Boolean);
  const rowDiff = sel => { const groups = {}; [...main.querySelectorAll(sel)].filter(vis).forEach(e => { const b = e.getBoundingClientRect(); const row = e.closest('[data-testid="stHorizontalBlock"]'); const k = Math.round(b.top) + '|' + (row ? [...document.querySelectorAll('[data-testid="stHorizontalBlock"]')].indexOf(row) : -1); (groups[k] = groups[k] || []).push(Math.round(b.height)); }); return Math.max(0, ...Object.values(groups).filter(g => g.length > 1).map(g => Math.max(...g) - Math.min(...g))); };
  r.kpiHeightDiff = rowDiff('.sg-kpi'); r.metricHeightDiff = rowDiff('[data-testid="stMetric"]');
  const panelRows = {}; [...main.querySelectorAll('[class*="st-key-sg-panel-"]')].filter(vis).forEach(p => { const col = p.closest('[data-testid="stColumn"]'); if (!col) return; const row = col.parentElement; const cr = col.getBoundingClientRect(); const k = [...document.querySelectorAll('[data-testid="stHorizontalBlock"]')].indexOf(row) + '|' + Math.round(cr.top); (panelRows[k] = panelRows[k] || {})[[...row.children].indexOf(col)] = Math.round(p.getBoundingClientRect().bottom); });
  r.panelBottomDiff = Math.max(0, ...Object.values(panelRows).map(o => Object.values(o)).filter(v => v.length > 1).map(v => Math.max(...v) - Math.min(...v)));
  const k = document.querySelector('.st-key-sg-kpis'), lo = document.querySelector('.st-key-sg-ov-lower');
  if (k && lo) r.kpiGap = Math.round(lo.getBoundingClientRect().top - Math.max(...[...k.querySelectorAll('.sg-kpi')].map(c => c.getBoundingClientRect().bottom)));
  const after = getComputedStyle(app, '::after'); r.boundary = after.display === 'none' ? 'hidden' : Math.round(parseFloat(after.width)) + 'px';
  const pr = document.querySelector('.sg-scene-promise'); r.promise = pr && getComputedStyle(pr).display !== 'none';
  r.bg = getComputedStyle(app).backgroundSize.split(',')[1]?.trim();
  const sb = document.querySelector('[data-testid="stSidebar"]'); const sr = sb && sb.getBoundingClientRect(); r.sidebar = sb ? (sr.right <= 0 || sr.width < 10 || sb.getAttribute('aria-expanded') === 'false' ? 'collapsed' : 'open ' + Math.round(sr.width)) : 'none';
  r.contentW = Math.round(document.querySelector('[data-testid="stMainBlockContainer"]').getBoundingClientRect().width);
  if (vw < 768) { const t = [...document.querySelectorAll('[data-testid^="stBaseButton"]')].filter(vis).map(b => Math.round(b.getBoundingClientRect().height)); r.minButtonH = t.length ? Math.min(...t) : null; }
  const ifr = document.querySelector('iframe[title*="streamlit_webrtc"], iframe'); if (location.search.includes('Live')) r.videoColW = ifr ? Math.round(ifr.getBoundingClientRect().width) : null;
  r.tablists = [...main.querySelectorAll('[role="tablist"]')].filter(vis).map(t => getComputedStyle(t).overflowX + (t.scrollWidth > t.clientWidth + 1 ? ':scrolls' : ''));
  r.h1 = document.querySelectorAll('h1').length;
  r.iconOnlyNoLabel = [...document.querySelectorAll('button, [role="button"], a')].filter(b => vis(b) && !(b.innerText || '').trim() && !b.getAttribute('aria-label') && !b.getAttribute('title') && !b.querySelector('[aria-label]')).map(b => b.dataset.testid || b.className.toString().slice(0, 30)).slice(0, 4);
  r.imgNoAlt = [...main.querySelectorAll('img')].filter(i => !i.hasAttribute('alt')).length;
  r.primaryBtn = (() => { const b = document.querySelector('[data-testid^="stBaseButton-primary"]'); return b ? getComputedStyle(b.querySelector('p') || b).color : null; })();
  return JSON.stringify(r);
})()
