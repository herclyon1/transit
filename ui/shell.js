/* 地图壳骨架（PLAN-v2 §三「改其内」）：地图（MapLibre GL）+ 工具条 + 非模态 Sheet + 叠放的地点卡片，四张图共用。
   页面只提供两样：layers(map) —— 数据 → 图层，返回 {图层 id: 点击回调(feature)}；card(item) —— 要素 → 卡片内容 {title, sub, html}。
   交互（Sheet 物理 ui/sheet.js、按下态 ui/press.js、SF 符号 ui/hig.js）全在壳里，页面的数据代码不碰交互代码。
   结构约定（maa 2026-09-15）：.sheet > .grab + .body；卡片走 HIGSheet.stack(SHEET, cardEl)；onChange 里不做重活；页与页之间的返回是 Safari 自己的手势。 */
window.HIGShell = (function(){
  const wide = () => matchMedia('(min-width: 900px)').matches;
  const wideSplit = () => matchMedia('(min-width: 900px) and (pointer: fine)').matches;
  function create(o){
    const $ = id => document.getElementById(id);
    // ---- 地图：一律 MapLibre GL，不转不倾斜（地图 App 的 2D 手感）；宽屏才给右下缩放钮（iPad/Mac 地图 App 有，手机没有）
    const map = o.map === false ? null : new maplibregl.Map(Object.assign({    // map:false = 页面自己画图（クイズ是 D3 的 SVG），壳只管 Sheet 和卡片
      container: o.mapEl || 'map', attributionControl: { compact: true, customAttribution: o.attribution || '' },
      dragRotate: false, pitchWithRotate: false, touchZoomRotate: true }, o.map || {}));
    if (map && o.wideNav !== false && wide()) map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');
    // ---- Sheet（主抽屉）+ 叠放的地点卡片（地图 App：点搜索结果 = 第二张 Sheet 从底边弹到中档，后面那张退到中档）
    const sheetEl = o.sheetEl || $('sheet'), listEl = o.listEl || $('list');
    const cardEl = o.cardEl !== undefined ? o.cardEl : (($('card') && $('card').querySelector('.grab')) ? $('card') : null);   // 只有带抓手的 #card 才是叠放的第二张 Sheet（学習的 #card 是内联卡）
    const sheet = HIG.sheet(sheetEl, { initial: o.initial || 'medium', onChange: o.onDetent });
    const card = (cardEl && window.HIGSheet && HIGSheet.stack) ? HIGSheet.stack(sheet, cardEl) : null;
    window.SHEET = sheet; window.CARD = card;                                    // accept.js 的物理探针和叠卡探针从这两个全局取
    const cTitle = cardEl && cardEl.querySelector('.tt .t-title2, .tt .t-head'), cSub = cardEl && cardEl.querySelector('.tt .t-sub'), cBody = cardEl && cardEl.querySelector('.body');
    let open = null, seq = 0;
    async function present(item, opts = {}){
      open = item; const my = ++seq;
      if (cardEl){
        if (card) card.present(); else cardEl.hidden = false;
        if (!card && listEl && !wideSplit()) listEl.hidden = true;        // 宽屏分栏：列表留在左边；窄屏无叠放引擎时列表让位
        if (sheet.get && sheet.get() === 'small') sheet.set('medium');
      }
      const c = o.card ? o.card(item) : null; const fill = r => { if (my !== seq || !r) return;
        if (cTitle && r.title != null) cTitle.textContent = r.title; if (cSub && r.sub != null) cSub.textContent = r.sub;
        if (cBody && r.html != null) { cBody.innerHTML = r.html; HIG.sf(); } };
      if (c && typeof c.then === 'function'){ if (cBody && o.loading !== false) cBody.innerHTML = '<div class="mcard"><div class="empty">载入…</div></div>'; fill(await c); }
      else fill(c);
      if (opts.flyTo && map) map.flyTo(opts.flyTo);
      return item;
    }
    function dismiss(){ open = null; if (!cardEl) return; if (card) card.dismiss(); else cardEl.hidden = true; if (listEl) listEl.hidden = false; if (o.onDismiss) o.onDismiss(); }
    if (cardEl){ const x = cardEl.querySelector('.head .btn-glass, .head .close'); if (x) x.addEventListener('click', dismiss); }
    // ---- 图层：页面把数据变成图层，回一张「图层 id → 点击回调」表；壳负责 click 和指针
    const wire = () => { const clicks = (o.layers && o.layers(map)) || {};
      for (const id of Object.keys(clicks)){
        map.on('click', id, e => { if (e.features && e.features[0]) clicks[id](e.features[0], e); });
        map.on('mouseenter', id, () => map.getCanvas().style.cursor = 'pointer');
        map.on('mouseleave', id, () => map.getCanvas().style.cursor = ''); } };
    if (map){ if (o.layersOnLoad === false) wire(); else map.on('load', wire);
      if (o.click) map.on('click', e => o.click(e, map)); }      // 要跨多个图层命中测试的页（学習：都道府県/市区町村/東亜）自己 queryRenderedFeatures
    return { map, sheet, card, present, dismiss, get open(){ return open; }, wide, wideSplit };
  }
  return { create };
})();
