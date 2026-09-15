/* Sheet 手势与物理（地图 App 那种可调档的非模态 Sheet）。hig.js 的 HIG.sheet() 在本文件已加载时把工作交给这里。

   规则来自苹果公开材料，数字来自实测（NUMBERS.md「Sheet 物理」一节）：
   · 档位、抓手、滚动交接：HIG › Sheets（iOS 26 版）——"A grabber shows people that they can drag the sheet to resize it;
     they can also tap it to cycle through the detents"；UISheetPresentationController.prefersScrollingExpandsWhenScrolledToEdge
     （默认 true）——"scrolling up in the sheet increases its detent instead of scrolling the sheet's content. After the sheet
     reaches its largest detent, scrolling begins."
   · 松手投影：WWDC18 803「Designing Fluid Interfaces」 projectedPosition = position + velocity · k，k = rate/(1−rate)/1000；
     目标 = 离投影点最近的档。k 实测 0.155 s（地图 App 中档上甩 60pt：1250pt/s 到大档、1000/800/300pt/s 留中档，30pt@1250 留中档、
     50pt@1250 到大档 → k 在 0.148–0.164 之间；等价 rate 0.9936，介于 normal .998 和 fast .99 之间，两者都对不上实测）。
     松手速度取最后 50ms 的位移/时间（UIPanGestureRecognizer 的 velocity 是瞬时值：地图 App 录像里手指末尾减速的一次，落回了中档）。
   · 橡皮筋：同上 offset = (1 − 1/(x·c/d + 1))·d，c = 0.55，d = 视口高。
   · 落档弹簧：WWDC23 10158「Animate with springs」的 Spring(duration:bounce:)；地图 App 实测（iPhone 18 Pro Max，iOS 27，
     09-15 60fps 逐帧，五段回弹拟合）：静止松手/轻点抓手 → 阻尼比 1.00（bounce 0）、ω ≈ 18.3/s → duration 0.34 s，均方差 < 0.5pt；
     甩手（1250pt/s）→ 同一个 ω，阻尼比 0.8（bounce 0.2），过冲 6.7pt 再回来；手指松开的速度作为弹簧初速度（WWDC18 803）。
     两者之间按 |v0|/1250 线性插 bounce（只有两个实测点：0 和 0.2）。
   · 拖动跟手 1:1（实测 10.33pt 步进 → Sheet 10.33pt）。
   · 宽度：中档两侧内缩 8，大档满宽；两档之间按位置线性插值（地图 App 逐帧：上沿 469→8、370→6.9、288→5.9、191→1.2、92→0.2）。
   元素：.sheet 里有 .grab（抓手）、可选 .body（滚动区）。位置用 transform 驱动（合成层，不回流）；高度固定为大档高，
   中/小档把多出来的部分推到屏幕下面——和 UIKit 一样，中档时内容要先把 Sheet 推到大档才能滚。 */
window.HIGSheet = (function(){
  const RATE = 0.998;                       // UIScrollView.DecelerationRate.normal（推到大档后接着滚的减速）
  const PROJECT_S = 0.155;                  // 松手投影的看前量（秒），实测，见文件头
  const VEL_WINDOW = 50;                    // 松手速度取最后 50ms
  const RUBBER_C = 0.55;                    // WWDC18 803
  const SETTLE = { duration: 0.34, bounce: 0 };   // 实测，见文件头
  const FLICK_BOUNCE = 0.2, FLICK_V = 1250;       // 甩手时的 bounce 与达到它的速度（实测）
  const settleFor = v0 => ({ duration: SETTLE.duration, bounce: FLICK_BOUNCE * Math.max(0, Math.min(1, Math.abs(v0) / FLICK_V)) });
  const LARGE_TOP = 62, MEDIUM_FRAC = 0.4421, SMALL_H = 96;   // NUMBERS.md：大档 = 屏高 − 62；中档 = 422.67/956（kit 说 44%）；小档 = 96 + 安全区底

  // ---- 纯函数（accept.js 直接拿来验） ----
  const project = (v, k = PROJECT_S) => v * k;
  const rubber = (x, dim, c = RUBBER_C) => (1 - 1 / (x * c / dim + 1)) * dim;
  // 弹簧闭式解：位移 d、初速 v0（同向为正）、duration/bounce → 返回 t 秒后的 [位移, 速度]
  function spring(d, v0, t, p = SETTLE){
    const w = 2 * Math.PI / p.duration;
    const z = p.bounce >= 0 ? 1 - p.bounce : 1 / (1 + p.bounce);
    if (Math.abs(z - 1) < 1e-6){ const e = Math.exp(-w * t); const a = v0 + w * d; return [(d + a * t) * e, (a - w * (d + a * t)) * e]; }
    if (z < 1){ const wd = w * Math.sqrt(1 - z * z); const e = Math.exp(-z * w * t); const b = (v0 + z * w * d) / wd;
      const x = e * (d * Math.cos(wd * t) + b * Math.sin(wd * t));
      const v = e * ((-z * w) * (d * Math.cos(wd * t) + b * Math.sin(wd * t)) + wd * (-d * Math.sin(wd * t) + b * Math.cos(wd * t)));
      return [x, v]; }
    const s = w * Math.sqrt(z * z - 1), r1 = -z * w + s, r2 = -z * w - s; const c2 = (v0 - r1 * d) / (r2 - r1), c1 = d - c2;
    return [c1 * Math.exp(r1 * t) + c2 * Math.exp(r2 * t), c1 * r1 * Math.exp(r1 * t) + c2 * r2 * Math.exp(r2 * t)];
  }
  const nearest = (tops, y) => Object.keys(tops).reduce((b, k) => Math.abs(tops[k] - y) < Math.abs(tops[b] - y) ? k : b);

  function create(el, opts = {}){
    const detents = opts.detents || ['small', 'medium', 'large'];
    const grab = el.querySelector('.grab'), body = el.querySelector('.body');
    const now = opts.now || (() => performance.now());
    const raf = opts.raf || (f => requestAnimationFrame(f));
    let cur = opts.initial || 'medium', tops = {}, H = 0, safeB = 0, top = 0, anim = null, elapsed = 0, parked = false;   // parked：停在屏幕底下（叠放卡片没打开时）   // elapsed：弹簧最近一帧算到的时刻（秒，探针对模型用）
    const wide = () => window.matchMedia('(min-width: 900px)').matches;   // 宽屏是侧栏，没有档位（hig.css）

    function layout(){
      H = window.visualViewport ? window.visualViewport.height : window.innerHeight;
      const p = document.createElement('div'); p.style.cssText = 'position:fixed;width:0;height:0;padding-top:env(safe-area-inset-bottom)';
      document.body.appendChild(p); safeB = parseFloat(getComputedStyle(p).paddingTop) || 0; p.remove();
      tops = {}; if (detents.includes('large')) tops.large = LARGE_TOP;
      if (detents.includes('medium')) tops.medium = H - Math.round(H * MEDIUM_FRAC * 3) / 3;
      if (detents.includes('small')) tops.small = H - (SMALL_H + safeB);
      if (wide()){ el.style.transform = el.style.height = el.style.transition = el.style.left = el.style.right = el.style.borderRadius = el.style.clipPath = ''; return; }
      el.style.height = (H - LARGE_TOP) + 'px'; el.style.transition = 'none'; inset = -1;
    }
    // iOS 27 UI Kit › Sheets › iPhone：中档/小档是浮着的卡片——左右底各内缩 8、四角 34；大档满宽贴底、上角 38。内缩和圆角随位置在两者间线性过渡。
    // 元素本身仍是一整块高 H−62 往下滑（不改 height，免得每帧重排）；底边的 8 内缩和下圆角用 clip-path 裁出来：元素在视口底之下多出 (y − LARGE_TOP)，再多裁 v 就是浮起的缝
    const SIDE = 8, R_MID = 34, R_LARGE = 38; let inset = -1;
    const place = y => { top = y; el.style.transform = 'translate3d(0,' + (y - LARGE_TOP).toFixed(2) + 'px,0)';
      const lo = tops.large, hi = tops.medium ?? tops.small; let k = (lo != null && hi != null) ? Math.max(0, Math.min(1, (y - lo) / (hi - lo))) : 1;
      const v = Math.round(SIDE * k * 3) / 3;
      if (v !== inset){ inset = v; el.style.left = el.style.right = v + 'px'; const rt = (R_LARGE + (R_MID - R_LARGE) * k).toFixed(2); el.style.borderRadius = rt + 'px ' + rt + 'px 0 0'; }
      if (k > 0){ const rt = (R_LARGE + (R_MID - R_LARGE) * k).toFixed(2), rb = (R_MID * k).toFixed(2), cut = Math.max(0, y - LARGE_TOP + v).toFixed(2);
        el.style.clipPath = 'inset(0 0 ' + cut + 'px 0 round ' + rt + 'px ' + rt + 'px ' + rb + 'px ' + rb + 'px)'; }
      else el.style.clipPath = ''; };
    // 决定档位时只记 cur、发 onChange；class / data-detent 等落定后再改——改 class 会触发样式重算，第一帧就掉（实测 29–49ms）
    function mark(d){ cur = d; if (opts.onChange) opts.onChange(d); }
    function landed(){ el.classList.toggle('large', cur === 'large'); el.classList.toggle('small', cur === 'small'); el.dataset.detent = cur; }
    function stop(){ anim = null; }
    // 弹簧落档：从当前位置带初速 v0 去 tops[d]
    function settle(d, v0 = 0){
      parked = false; mark(d); if (wide()){ landed(); return; }
      const from = top, target = tops[d]; let t0 = null; const token = anim = {};
      // 第一帧画在 t=0（起点不动），和 Core Animation 一样——地图 App 的曲线比「第一帧就动」晚一帧，见 evidence/sheet-settle-maps-vs-sheetjs.png
      const prm = settleFor(v0);
      const step = () => { if (anim !== token) return; if (t0 == null) t0 = now(); elapsed = (now() - t0) / 1000; const [x, v] = spring(from - target, v0, elapsed, prm);
        if (Math.abs(x) < 0.05 && Math.abs(v) < 2){ place(target); anim = null; landed(); return; }
        place(target + x); raf(step); };
      raf(step);
    }
    // 飞到任意位置（叠放卡片进出屏幕用）：同一根弹簧，落地回调
    function fly(targetY, done){
      if (wide()){ place(targetY); done && done(); return; }
      const from = top; let t0 = null; const token = anim = {};
      const step = () => { if (anim !== token) return; if (t0 == null) t0 = now(); elapsed = (now() - t0) / 1000; const [x, v] = spring(from - targetY, 0, elapsed);
        if (Math.abs(x) < 0.05 && Math.abs(v) < 2){ place(targetY); anim = null; done && done(); return; }
        place(targetY + x); raf(step); };
      raf(step);
    }
    // 松手：投影 → 最近的档 → 弹簧
    function release(v){ const d = nearest(tops, top + project(v)); settle(d, v); return d; }
    // 拖动中的位置：两端之外橡皮筋
    function dragTo(y){
      const lo = tops.large ?? Math.min(...Object.values(tops)), hi = Math.max(...Object.values(tops));
      if (y < lo) y = lo - rubber(lo - y, H); else if (y > hi) y = hi + rubber(y - hi, H);
      place(y); return y;
    }

    // ---- 手势 ----
    // 一次手势：begin(y,t) / move(y,t) / end(t)；velocity 取最后 50ms 的样本（pt/s，向下为正）
    let g = null;
    function begin(y, t, inBody, onGrab){ if (wide()) return; stop(); g = { y0: y, t0: t, top0: top, inBody, onGrab, mode: inBody ? 'undecided' : 'sheet', scroll0: body ? body.scrollTop : 0, samples: [[t, top]] }; el.classList.add('dragging'); }
    function move(y, t){
      if (!g) return false; const dy = y - g.y0;
      if (g.mode === 'undecided'){
        if (dy === 0) return false;
        if (dy > 0 && body.scrollTop <= 0) g.mode = 'sheet';                 // 滚到顶再下拉：Sheet 跟着走
        else if (dy < 0 && opts.scrollExpands !== false && top > tops.large + 0.5 && 'large' in tops) g.mode = 'expand';   // 未到大档就上滑：先推 Sheet
        else { g.mode = 'native'; return false; }                            // 其余交给原生滚动
      }
      if (g.mode === 'native') return false;
      let y1 = g.top0 + dy;
      if (g.mode === 'expand' && y1 < tops.large){ place(tops.large); body.scrollTop = g.scroll0 + (tops.large - y1); g.scrolling = true; }
      else { if (g.scrolling){ body.scrollTop = g.scroll0; } g.scrolling = false; dragTo(y1); }
      g.samples.push([t, g.mode === 'expand' && g.scrolling ? y1 : top]); while (g.samples.length > 2 && t - g.samples[1][0] >= VEL_WINDOW) g.samples.shift();
      if (Math.abs(dy) >= 6) g.moved = true;
      return true;
    }
    function end(t){
      if (!g) return null; const s = g.samples; el.classList.remove('dragging');
      const [ta, ya] = s[0], [tb, yb] = s[s.length - 1]; const v = tb > ta ? (yb - ya) / (tb - ta) * 1000 : 0;
      const gg = g; g = null;
      if (gg.mode === 'native' || gg.mode === 'undecided') return null;
      if (!gg.moved){ if (gg.onGrab) return cycle(); settle(nearest(tops, top)); return cur; }   // 轻点：抓手循环档位，别处原地落定
      if (gg.scrolling){ mark('large'); landed(); fling(-v); return 'large'; }
      return release(v);
    }
    // 推到大档后继续滚：用同一个减速率把剩余速度滚完（UIScrollView 的减速），到边就停
    function fling(v){ let t0 = now(), y = body.scrollTop; const token = anim = {};
      const step = () => { if (anim !== token) return; const t = now(), dt = t - t0; t0 = t; y += v * dt / 1000; v *= Math.pow(RATE, dt);
        body.scrollTop = y; if (Math.abs(v) < 5 || body.scrollTop <= 0 || body.scrollTop >= body.scrollHeight - body.clientHeight){ anim = null; return; } raf(step); };
      raf(step); }

    // 触摸（Safari）：body 里的第一下 move 决定归谁；决定归 Sheet 的就 preventDefault，原生滚动便不会开始
    // 滑块/输入框上的触摸归控件自己（大阪页阈值滑块被 Sheet 手势抢走，09-15 审查 #37）
    el.addEventListener('touchstart', e => { if (e.target.closest && e.target.closest('input, select, textarea, [data-native-touch]')) return; begin(e.touches[0].clientY, e.timeStamp, !!(body && body.contains(e.target)), !!(grab && grab.contains(e.target))); }, { passive: true });
    el.addEventListener('touchmove', e => { if (move(e.touches[0].clientY, e.timeStamp)) e.preventDefault(); }, { passive: false });
    el.addEventListener('touchend', e => { const onGrab = g && g.onGrab && !g.moved; end(e.timeStamp); if (onGrab) e.preventDefault(); });   // 抓手轻点已处理，压掉随后的 click
    el.addEventListener('touchcancel', e => end(e.timeStamp));
    // 鼠标（桌面调试）：只从抓手/头部拖
    el.addEventListener('mousedown', e => { if (body && body.contains(e.target)) return; begin(e.clientY, e.timeStamp, false, !!(grab && grab.contains(e.target)));
      const mm = ev => { move(ev.clientY, ev.timeStamp); ev.preventDefault(); }, mu = ev => { window.removeEventListener('mousemove', mm); window.removeEventListener('mouseup', mu); if (g && !g.moved) g.onGrab = false; end(ev.timeStamp); };
      window.addEventListener('mousemove', mm); window.addEventListener('mouseup', mu); });
    function cycle(){ const d = detents[(detents.indexOf(cur) + 1) % detents.length]; settle(d); return d; }   // HIG：轻点抓手在档位间循环
    if (grab){
      grab.setAttribute('role', 'button'); grab.setAttribute('tabindex', '0'); grab.setAttribute('aria-label', '调整大小');
      grab.addEventListener('click', e => { if (e.detail === 0 || !('ontouchstart' in window)) cycle(); });   // 键盘 / 桌面鼠标（触摸的轻点走 touchend）
      grab.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' '){ e.preventDefault(); cycle(); } });
    }
    const relayout = () => { layout(); if (!wide()) place(parked ? H : (tops[cur] ?? tops.medium ?? Object.values(tops)[0])); };
    const park = () => { parked = true; stop(); if (!wide()) place(H); };
    window.addEventListener('resize', relayout); if (window.visualViewport) window.visualViewport.addEventListener('resize', relayout);
    layout(); mark(cur); landed(); if (!wide()) place(tops[cur] ?? Object.values(tops)[0]);

    return { el, get: () => cur, set: d => { if (detents.includes(d)) settle(d); }, tops: () => ({ ...tops }), top: () => top, elapsed: () => elapsed,
             sim: { begin, move, end, place, fly, park, layout: relayout, H: () => H, parked: () => parked }, physics: { project, rubber, spring, settleFor, nearest, RATE, PROJECT_S, VEL_WINDOW, RUBBER_C, SETTLE, FLICK_BOUNCE } };
  }
  // 叠放卡片（地图 App 点搜索结果）：卡片是第二张 Sheet，从屏幕底下弹到中档，后面那张退到中档；关掉时卡片弹回屏幕底下、后面那张回原档。
  // 实测（09-15 14:34，60fps）：两张用同一根 0.34s 临界阻尼弹簧同时动；进：卡片 956→533、搜索页 62→533；出：卡片 533→956、搜索页 533→62。
  // 窄屏时把 cardEl 挪到 body 下当独立 Sheet（fixed 元素在 transform 的祖先里会跟着祖先动），关掉后放回原处；宽屏只切 hidden。
  create.stack = function(base, cardEl, opts = {}){
    let ctl = null, home = null, prev = null, shown = false, mounted = false;
    const wide = () => window.matchMedia('(min-width: 900px)').matches;
    // 窄屏一开始就把卡片挂到 body 下、放到屏幕底下等着：present 时只剩弹簧要跑，不在第一帧做挪 DOM + 排版（实测那样会掉一帧）
    function mount(){
      if (mounted || wide()) return; mounted = true;
      home = { parent: cardEl.parentNode, next: cardEl.nextSibling };
      document.body.appendChild(cardEl); cardEl.classList.add('sheet', 'glass', 'stacked'); cardEl.hidden = false; cardEl.style.visibility = 'hidden';
      ctl = create(cardEl, { initial: 'medium', detents: opts.detents || ['small', 'medium', 'large'] }); ctl.sim.park();
    }
    function unmount(){
      if (!mounted) return; mounted = false; cardEl.hidden = true; cardEl.classList.remove('sheet', 'glass', 'stacked'); cardEl.style.cssText = ''; home.parent.insertBefore(cardEl, home.next); ctl = null;
    }
    function present(){
      if (shown) return; shown = true;
      if (wide()){ unmount(); cardEl.hidden = false; return; }
      mount(); prev = base.get();
      // 页面通常在同一个任务里同步拼卡片内容（薪资页 show()）；弹簧推迟到下一帧起跑，别让拼 DOM 的那一帧吃掉动画开头
      requestAnimationFrame(() => { if (!shown) return; cardEl.style.visibility = ''; ctl.set('medium'); if (base.get() === 'large') base.set('medium'); });
    }
    function dismiss(){
      if (!shown) return; shown = false;
      if (!mounted){ cardEl.hidden = true; return; }
      ctl.sim.fly(ctl.sim.H(), () => { cardEl.style.visibility = 'hidden'; ctl.sim.park(); });
      if (prev && prev !== base.get()) base.set(prev);
    }
    mount();
    window.addEventListener('resize', () => { if (wide() && mounted){ const was = shown; unmount(); cardEl.hidden = !was; } else if (!wide() && !mounted){ const was = shown; cardEl.hidden = true; mount(); if (was){ cardEl.style.visibility = ''; ctl.sim.place(ctl.tops().medium); } } });
    return { present, dismiss, get shown(){ return shown; }, get ctl(){ return ctl; } };
  };
  create.physics = { project, rubber, spring, settleFor, nearest, RATE, PROJECT_S, VEL_WINDOW, RUBBER_C, SETTLE, FLICK_BOUNCE };
  return create;
})();
