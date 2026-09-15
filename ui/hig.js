/* transit 共用行为：Sheet 停靠档（HIG Sheets：拖抓手或点抓手在档位间切换；滚到顶再下拉也能缩），
   SF Symbols 注入。数字依据见 DESIGN-HIG.md。 */
window.HIG = (function(){
  const ROOT = (function(){ const s=[...document.scripts].find(x=>/ui\/hig\.js/.test(x.src)); return s ? s.src.replace(/ui\/hig\.js.*$/,'') : ''; })();
  // <i class="sf" data-sf="magnifyingglass"></i> → 蒙版指向 ui/sf/<name>.png
  function sf(){
    document.querySelectorAll('.sf[data-sf]').forEach(el=>{ el.style.setProperty('--sf', `url(${ROOT}ui/sf/${el.dataset.sf}.png)`); el.setAttribute('aria-hidden','true'); });
  }
  // Sheet：三档 small / medium（默认）/ large。返回 {set(detent), get()}
  function sheet(el, opts={}){
    const detents = opts.detents || ['small','medium','large'];
    let cur = opts.initial || 'medium';
    const apply = d => { cur=d; el.classList.toggle('large', d==='large'); el.classList.toggle('small', d==='small'); el.dataset.detent=d; if(opts.onChange) opts.onChange(d); };
    apply(cur);
    const grab = el.querySelector('.grab'); const body = el.querySelector('.body');
    if(grab){
      grab.addEventListener('click', ()=>{ const i=detents.indexOf(cur); apply(detents[(i+1)%detents.length]); });
      let y0=null, h0=0;
      const down = e=>{ if(window.matchMedia('(min-width: 900px)').matches) return; y0=(e.touches?e.touches[0]:e).clientY; h0=el.getBoundingClientRect().height; el.classList.add('dragging'); };
      const move = e=>{ if(y0==null) return; const y=(e.touches?e.touches[0]:e).clientY; const h=Math.max(80, Math.min(window.innerHeight-62, h0+(y0-y))); el.style.height=h+'px'; e.preventDefault(); };
      const up = ()=>{ if(y0==null) return; const h=el.getBoundingClientRect().height; y0=null; el.classList.remove('dragging'); el.style.height='';
        const H=window.innerHeight; const target = h > H*0.72 ? 'large' : (h < H*0.22 ? 'small' : 'medium'); apply(detents.includes(target)?target:'medium'); };
      grab.addEventListener('touchstart', down, {passive:true}); grab.addEventListener('mousedown', down);
      window.addEventListener('touchmove', move, {passive:false}); window.addEventListener('mousemove', move);
      window.addEventListener('touchend', up); window.addEventListener('mouseup', up);
      // 内容滚到顶再往下拉：从大档退回中档（地图 App 行为）
      if(body){ let ty=null; body.addEventListener('touchstart', e=>{ ty = body.scrollTop<=0 ? e.touches[0].clientY : null; }, {passive:true});
        body.addEventListener('touchmove', e=>{ if(ty!=null && e.touches[0].clientY-ty>40 && cur==='large'){ ty=null; apply('medium'); } }, {passive:true}); }
    }
    return { set: apply, get: ()=>cur, el };
  }
  // 开关：Safari 17.4+ 的 <input type=checkbox switch> 只是 WebKit 自己画的开关——外形像系统的，但动效不是：
  // 圆钮第一帧就跳到对侧、只有轨道颜色淡入，没有按下态/镜片、不跟手（maa 会话 2026-09-15 11:29 在 iPhone 18 Pro Max 上 60fps 逐帧录像，
  // 证据 ~/Claude/hig-kit/evidence/）。所以默认不用它，用 hig.css 模仿的 .sw（kit 里有按住镜片那套）；需要时显式调 HIG.nativeSwitch()。
  function nativeSwitch(){
    const probe=document.createElement('input'); probe.type='checkbox';
    if('switch' in probe && /Apple/.test(navigator.vendor||'')){ document.querySelectorAll('.sw input[type=checkbox]').forEach(i=>i.setAttribute('switch','')); document.documentElement.classList.add('native-switch'); }
  }
  document.addEventListener('DOMContentLoaded', sf);
  // ?accept → 加载验收脚本（DESIGN-HIG.md 验收程序第 2 关）
  if(/[?&]accept/.test(location.search)){ const a=document.createElement('script'); a.src=ROOT+'ui/accept.js?v='+Date.now(); document.head.appendChild(a); }
  // 下拉菜单（UIMenu）：点 anchor 开合，菜单贴在 anchor 下方 6，靠右对齐；点项 → onPick(value)；Esc/点外面关。
  function menu(anchor, el, onPick){
    const close=()=>{ el.hidden=true; anchor.setAttribute('aria-expanded','false'); };
    const open=()=>{ el.hidden=false; anchor.setAttribute('aria-expanded','true');
      const a=anchor.getBoundingClientRect(); el.style.top=(a.bottom+6+window.scrollY)+'px'; el.style.left=Math.max(8, Math.min(a.right-el.offsetWidth, window.innerWidth-el.offsetWidth-8))+'px';
      const first=el.querySelector('[aria-checked="true"]')||el.querySelector('button'); first&&first.focus(); };
    anchor.setAttribute('aria-haspopup','menu'); anchor.setAttribute('aria-expanded','false');
    anchor.addEventListener('click', e=>{ e.stopPropagation(); el.hidden?open():close(); });
    el.addEventListener('click', e=>{ const b=e.target.closest('button'); if(!b) return; el.querySelectorAll('button').forEach(x=>x.setAttribute('aria-checked', x===b?'true':'false')); close(); onPick&&onPick(b.dataset.value, b); });
    document.addEventListener('click', e=>{ if(!el.hidden && !el.contains(e.target)) close(); });
    document.addEventListener('keydown', e=>{ if(el.hidden) return; if(e.key==='Escape'){ close(); anchor.focus(); }
      if(e.key==='ArrowDown'||e.key==='ArrowUp'){ e.preventDefault(); const bs=[...el.querySelectorAll('button')]; const i=bs.indexOf(document.activeElement); bs[(i+(e.key==='ArrowDown'?1:-1)+bs.length)%bs.length].focus(); } });
    return { open, close };
  }
  return { sf, sheet, menu, nativeSwitch, ROOT };
})();
