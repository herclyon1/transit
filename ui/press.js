/* 行按下高亮（UITableViewCell 的 highlighted）。规则：HIG 没给数字；UIScrollView.delaysContentTouches 文档只说「延迟到能判断是不是要滚动」。
   实测（地图 App › 最近搜索 行，iPhone 18 Pro Max iOS 27，09-15 14:34，60fps）：
   · 触到的下一帧就开始变色，没有 150ms 延迟；0.22s 内 ease-out 到位（16%/34%/42%/53%/61%/68%/74%/82%/87%/92%…100%）；
   · 到位颜色 = 白行上 (215,215,220) ≈ systemGray4 (209,209,214) 85%；松手后一帧已回到一半，按 0.1s 淡出；
   · 一开始滚动（移动超过 10pt）就取消高亮（UIKit 行为）。
   作用于 .row / .mrow / .links a / .tiles button（没有 .no-press 的）。样式由本文件注入，不碰 hig.css。
   玻璃圆钮按下（Liquid Glass，地图 App 右上角 44 圆钮，09-15 14:59 逐帧）：按住时整体放大到 ×1.135，走 Spring(duration 0.24, bounce 0.4)
   （第 9 帧过冲到 1.149，0.28s 落定；逐帧对模型误差 ≤0.04），同时 0.1s 内变亮（玻璃 243→252、符号 145→188 ≈ brightness 1.3）；
   松手同一根弹簧回 1（实测有 0.97 的回弹）。填充色按钮（.btn）没量到，不动。 */
(function(){
  const SEL = '.row, .mrow, .links a, .tiles button';
  const st = document.createElement('style');
  st.textContent = SEL + '{-webkit-user-select:none;user-select:none;-webkit-touch-callout:none}' +   /* 长按行不许选字、不弹菜单（原生行就没有） */
                   '.hig-press{background-color:rgba(209,209,214,.85) !important;transition:background-color .2s ease-out}' +
                   '.hig-press.hig-press-out{background-color:transparent !important;transition:background-color .1s ease-out}' +
                   '@media (prefers-color-scheme: dark){.hig-press{background-color:rgba(58,58,60,.85) !important}}';
  document.head.appendChild(st);
  let cur = null, y0 = 0, x0 = 0, t0 = 0, lastClick = 0;
  // Safari 对按住超过约半秒再松开的触摸不发 click；原生行是松手即选，所以松手 60ms 内没等到 click 就自己发一个
  document.addEventListener('click', () => { lastClick = performance.now(); }, true);
  // 轻点太快也让高亮至少露 120ms 再淡出（快速轻点没量到，按 UIButton 的最短高亮习惯）
  const clear = (e) => { if (!cur) return; const el = cur; cur = null; const wait = Math.max(0, 120 - (performance.now() - t0));
    if (e && e.type === 'touchend' && performance.now() - t0 > 400){ const at = performance.now(); setTimeout(() => { if (lastClick < at) el.click(); }, 60); }
    setTimeout(() => { el.classList.add('hig-press-out'); setTimeout(() => el.classList.remove('hig-press', 'hig-press-out'), 120); }, wait); };
  document.addEventListener('touchstart', e => { const el = e.target.closest && e.target.closest(SEL); if (!el || el.classList.contains('no-press') || el.disabled) return; if (cur) clear(); cur = el; t0 = performance.now(); y0 = e.touches[0].clientY; x0 = e.touches[0].clientX; el.classList.remove('hig-press-out'); el.classList.add('hig-press'); }, { passive: true });
  document.addEventListener('touchmove', e => { if (cur && (Math.abs(e.touches[0].clientY - y0) > 10 || Math.abs(e.touches[0].clientX - x0) > 10)){ const el = cur; cur = null; el.classList.remove('hig-press', 'hig-press-out'); } }, { passive: true });
  document.addEventListener('touchend', clear, { passive: true }); document.addEventListener('touchcancel', clear, { passive: true });
  // 玻璃圆钮：scale 用 Web Animations + linear() 缓动（弹簧曲线采样，Safari 17.2+），亮度走 CSS 过渡
  const BTN = '.btn-glass'; const BTN_SCALE = 1.135; const BTN_MS = 360;
  const BTN_STOPS = 'linear(0.0, 0.065, 0.22, 0.411, 0.602, 0.769, 0.902, 0.996, 1.056, 1.086, 1.095, 1.089, 1.074, 1.056, 1.038, 1.022, 1.009, 1.0, 0.995, 0.992, 0.991, 0.992, 0.993, 0.995, 1)';   // Spring(0.24, 0.4)，0.36s 采 24 点
  const st2 = document.createElement('style'); st2.textContent = BTN + '{transition:filter .1s ease-out;-webkit-touch-callout:none;-webkit-user-select:none;user-select:none}.hig-btn-press{filter:brightness(1.3)}'; document.head.appendChild(st2);   // <a> 圆钮长按不许弹 Safari 的链接预览
  const supportsLinear = (() => { try { return CSS.supports('animation-timing-function', 'linear(0, 1)'); } catch (_) { return false; } })();
  let btn = null, btnAnim = null;
  const btnTo = (el, to) => { const from = (el.__scale ?? 1); if (btnAnim) btnAnim.cancel();
    btnAnim = el.animate([{ transform: 'scale(' + from + ')' }, { transform: 'scale(' + to + ')' }], { duration: BTN_MS, easing: supportsLinear ? BTN_STOPS : 'ease-out', fill: 'forwards' });
    el.__scale = to; const a = btnAnim; a.onfinish = () => { if (btnAnim === a && to === 1){ a.cancel(); btnAnim = null; } }; };
  document.addEventListener('touchstart', e => { const el = e.target.closest && e.target.closest(BTN); if (!el || el.disabled) return; btn = el; el.classList.add('hig-btn-press'); btnTo(el, BTN_SCALE); }, { passive: true });
  const btnUp = () => { if (!btn) return; const el = btn; btn = null; el.classList.remove('hig-btn-press'); btnTo(el, 1); };
  document.addEventListener('touchend', btnUp, { passive: true }); document.addEventListener('touchcancel', btnUp, { passive: true });
  document.addEventListener('touchmove', e => { if (btn){ const r = btn.getBoundingClientRect(); const t = e.touches[0]; if (t.clientX < r.left - 30 || t.clientX > r.right + 30 || t.clientY < r.top - 30 || t.clientY > r.bottom + 30) btnUp(); } }, { passive: true });   // 拖出按钮外 = 取消（UIControl 行为）
  window.HIGPress = { SEL, clear, CSS: st.textContent, BTN, BTN_SCALE, BTN_STOPS, BTN_MS };
})();
