// Shell wiring for the one map: sidebar / sheet, place card, right column, Map Modes, hash state.
// Skeleton only — no data, no functions. The map itself is globe.js (window.__globe); the shell uses
// ui/shell.js (sheet + stacked card engine) with map:false so it never touches the map.
// Hash state (PLAN-ONE-MAP §4): #z/lat/lng&m=<mode>&sel=<id>  (globe.js owns z/lat/lng and keeps extras)
(function () {
  const $ = id => document.getElementById(id);
  const waitGlobe = () => new Promise(r => { const t = () => window.__globe ? r(window.__globe) : setTimeout(t, 30); t(); });
  const extras = () => { const h = location.hash.replace(/^#/, ''); return new URLSearchParams(h.includes('&') ? h.slice(h.indexOf('&') + 1) : (h.includes('=') ? h : '')); };
  const MODES = ['cost', 'live', 'learn', 'quiz'];
  const PLACES = {   // placeholder card content, one per row
    'osaka': { title: '大阪', sub: '日本 · JPY · 占位' }, 'tokyo': { title: '东京', sub: '日本 · JPY · 占位' }, 'seoul': { title: '首尔', sub: '韩国 · KRW · 占位' },
    'osaka-station': { title: '大阪駅', sub: '大阪市北区 · 占位' }, 'tokyo-station': { title: '東京駅', sub: '千代田区 · 占位' },
  };

  // &ui=0 hides the shell (basemap-only comparisons against App snapshots); index.html sets html.noui in the head
  // before first paint and on hashchange — this is only the fallback
  if (extras().get('ui') === '0') document.documentElement.classList.add('noui');
  waitGlobe().then(G => { try {
    const app = HIGShell.create({ map: false, sheetEl: $('sheet'), listEl: $('list'), cardEl: $('card'), initial: 'medium',
      card: item => ({ title: item.title, sub: item.sub, html: null }),
      onDismiss: () => G.setHashExtra('sel', null) });
    // Mac: ± under the right column (hig.css 11b positions .maplibregl-ctrl-top-right at --bar-h); iPhone: none (Maps has none)
    if (app.wideSplit()) {
      const nav = new maplibregl.NavigationControl({ showCompass: false });
      G.map.addControl(nav, 'top-right');
      // acceptance probes: fixed roles on the ± buttons (MapLibre owns the markup)
      const c = nav._container; if (c) { const [zi, zo] = c.querySelectorAll('button'); if (zi) zi.dataset.role = 'rail-zoom-in'; if (zo) zo.dataset.role = 'rail-zoom-out'; }
    }

    // Mac: the card's material layer (#matCard, hig.css §19) follows the card's hidden attribute
    const matCard = $('matCard');
    if (matCard) { const sync = () => { matCard.hidden = $('card').hidden; }; new MutationObserver(sync).observe($('card'), { attributes: true, attributeFilter: ['hidden'] }); sync(); }

    // ---- rows -> card (placeholder), sel= in the hash
    function select(id, push = true) {
      const p = PLACES[id]; if (!p) return;
      document.querySelectorAll('.mrow[data-sel]').forEach(b => b.setAttribute('aria-current', b.dataset.sel === id ? 'true' : 'false'));
      app.present({ id, ...p });
      if (push) G.setHashExtra('sel', id);
    }
    document.querySelectorAll('.mrow[data-sel]').forEach(b => b.addEventListener('click', () => select(b.dataset.sel)));

    // ---- Map Modes: Mac Popover from the toolbar button (sidebar stays), iPhone Sheet replacing the main one
    let OPT = null;
    const opt = $('optSheet');
    function openModes() {
      // Mac: the popover opens beside the place card (Maps.app keeps the card); iPhone: the modes sheet
      // replaces the main sheet, so the card (stacked in it) goes with it
      if (app.open && !app.wideSplit()) app.dismiss();
      opt.hidden = false; if (!app.wideSplit()) $('sheet').hidden = true; HIG.sf();
      if (!OPT && HIG.sheet) OPT = HIG.sheet(opt, { initial: 'medium', detents: ['medium', 'large'] });
      else if (OPT && OPT.sim) { OPT.sim.layout(); OPT.set('medium'); }
    }
    function closeModes() { opt.hidden = true; $('sheet').hidden = false; }
    $('modeBtn').addEventListener('click', () => (opt.hidden ? openModes() : closeModes()));
    $('optClose').addEventListener('click', closeModes);
    // Mac: Maps.app's Map Modes is a popover — no close button (hidden in map/shell.css), a click anywhere outside
    // it or on the toolbar button closes it; the iPhone modes sheet keeps its X (Maps iOS "Choose Map")
    document.addEventListener('pointerdown', e => {
      if (opt.hidden || !app.wideSplit()) return;
      if (opt.contains(e.target) || $('modeBtn').contains(e.target)) return;
      closeModes();
    }, true);
    function setMode(m, push = true) {
      if (!MODES.includes(m)) return;
      opt.querySelectorAll('.mode').forEach(b => b.setAttribute('aria-checked', b.dataset.mode === m ? 'true' : 'false'));
      document.documentElement.dataset.mode = m;
      if (push) G.setHashExtra('m', m);
    }
    opt.querySelectorAll('.mode').forEach(b => b.addEventListener('click', () => setMode(b.dataset.mode)));

    // ---- restore from the hash
    const q = extras();
    setMode(q.get('m') || 'cost', false);
    if (q.get('sel')) select(q.get('sel'), false);
    HIG.sf();
    window.__shell = { app, select, setMode, openModes, closeModes };
  } catch (e) { (window.__errs = window.__errs || []).push('shell: ' + (e && e.message || e)); console.error(e); } });
})();
