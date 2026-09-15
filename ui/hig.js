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
  document.addEventListener('DOMContentLoaded', sf);
  // ?accept → 加载验收脚本（DESIGN-HIG.md 验收程序第 2 关）
  if(/[?&]accept/.test(location.search)){ const a=document.createElement('script'); a.src=ROOT+'ui/accept.js?v='+Date.now(); document.head.appendChild(a); }
  return { sf, sheet, ROOT };
})();
