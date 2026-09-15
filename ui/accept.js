/* HIG 验收（在目标浏览器里量 DOM）。页面地址加 ?accept 即加载（再加 &quiet 不画覆盖层，只 POST）：把关键控件的实测尺寸和 DESIGN-HIG.md 的数字表比，
   左上角盖一块结果，并 POST 到本地 rangeserver 的 /accept（pipeline/ui/accept.py 收集）。
   只在 Safari/iOS 上的数字才算数：桌面 Chromium 没有 -apple-system-body，根字号是 16 而不是 17。 */
(function(){
  if(!/[?&]accept/.test(location.search)) return;
  const R=[]; const num=v=>Math.round(v*100)/100;
  const ok=(name, got, want, tol, note)=>{ const pass = typeof want==='number' ? Math.abs(got-want)<=tol : got===want; R.push({name, got: typeof got==='number'?num(got):got, want, pass, note}); };
  const rect=el=>el.getBoundingClientRect(); const cs=(el,ps)=>getComputedStyle(el,ps||null); const px=v=>parseFloat(v)||0;
  const q=s=>document.querySelector(s); const qa=s=>[...document.querySelectorAll(s)].filter(e=>rect(e).width>0);
  const safe=(()=>{ const p=document.createElement('div'); p.style.cssText='position:fixed;top:0;height:env(safe-area-inset-top);width:0'; document.body.appendChild(p); const v=rect(p).height; p.remove(); return v; })();
  const W=window.innerWidth, H=window.innerHeight, wide=W>=900;
  const root=px(cs(document.documentElement).fontSize); const INSET=W>=414?20:16;
  function run(){
    R.length=0;
    ok('根字号 = 17（-apple-system-body）', root, 17, 0.01, 'Chromium 会是 16');
    const fam=cs(document.body).fontFamily; ok('字体栈含 PingFang SC', /PingFang SC/.test(fam), true, 0, fam.split(',').slice(0,4).join(','));
    const tint=cs(document.documentElement).getPropertyValue('--tint').trim(); ok('tint', tint.toLowerCase(), matchMedia('(prefers-color-scheme: dark)').matches?'#0a84ff':'#0088ff', 0);
    // 顶部工具条：44 圆钮，左 16，贴安全区顶
    const bar=q('.bar'); if(bar){ const b=qa('.bar .btn-glass')[0]; if(b){ const r=rect(b); ok('工具条按钮高 44', r.height, 44, 0.5); ok('工具条按钮宽 ≥44', r.width>=43.5, true, 0, num(r.width)); ok('工具条左内缩 = 布局边距 '+INSET, r.left, INSET, 0.5); ok('工具条按钮顶 = 安全区', r.top, safe, 0.5, 'safe-top '+num(safe)); } }
    // Sheet
    const sh=q('.sheet'); if(sh){ const r=rect(sh); const d=sh.dataset.detent||'medium';
      if(!wide){ ok('Sheet 左内缩 8', r.left, 8, 0.5); ok('Sheet 右内缩 8', W-r.right, 8, 0.5); ok('Sheet 圆角 38', px(cs(sh).borderTopLeftRadius), 38, 0.5);
        if(d==='medium') ok('Sheet 中档 = 44% 屏', 100*r.height/H, 44, 1); else if(d==='large') ok('Sheet 大档 = 屏高 − 62', H-r.height, 62, 1); else ok('Sheet 小档 = 96 + 安全区底', r.height, 96+0, 40, '档位 small');
        const g=q('.sheet .grab i'); if(g){ const gr=rect(g); ok('抓手 58×4', gr.width===58&&Math.abs(gr.height-4)<0.5, true, 0, num(gr.width)+'×'+num(gr.height)); ok('抓手距顶 5', gr.top-r.top, 5, 0.5); ok('抓手居中', Math.abs((gr.left+gr.right)/2-(r.left+r.right)/2), 0, 1); }
      } else { ok('侧栏宽 320', r.width, 320, 0.5); ok('侧栏左 16', r.left, 16, 0.5); ok('侧栏顶 = 安全区 + 64', r.top, safe+64, 0.5); ok('侧栏圆角 26', px(cs(sh).borderTopLeftRadius), 26, 0.5); }
      const s=qa('.sheet .search')[0]; if(s){ const sr=rect(s); ok('搜索胶囊高 44', sr.height, 44, 0.5); ok('搜索胶囊距 Sheet 内边 16', sr.left-r.left, 16, 0.5); ok('搜索胶囊距 Sheet 顶 15', sr.top-r.top, 15, 0.5); ok('搜索胶囊左内边 11', px(cs(s).paddingLeft), 11, 0.1); }
      const head=qa('.sheet .head')[0]; if(head){ const hb=qa('.sheet .head .btn-glass')[0]; if(hb){ const br=rect(hb); ok('卡片头圆钮 44', br.width===44&&br.height===44, true, 0, num(br.width)+'×'+num(br.height)); ok('卡片头圆钮距 Sheet 顶 15', br.top-r.top, 15, 0.5); ok('卡片头圆钮距 Sheet 边 15', Math.min(br.left-r.left, r.right-br.right), 15, 0.5); }
        const tt=qa('.sheet .head .tt .t-title2')[0]; if(tt){ const c=cs(tt); ok('卡片头标题 22/28 粗', Math.abs(px(c.fontSize)-root*22/17)<0.2&&+c.fontWeight>=700, true, 0, num(px(c.fontSize))+'/'+num(px(c.lineHeight))+' w'+c.fontWeight); ok('卡片头标题居中', c.textAlign, 'center', 0); ok('卡片头标题距 Sheet 顶 15', rect(tt).top-r.top, 15, 0.5); }
        const st=qa('.sheet .head .tt .t-sub')[0]; if(st){ const c=cs(st); ok('卡片头副标题 15/20', Math.abs(px(c.fontSize)-root*15/17)<0.2, true, 0, num(px(c.fontSize))+'/'+num(px(c.lineHeight))); ok('卡片头副标题单行', rect(st).height, root*20/17, 0.5); }
        const body=qa('.sheet .body')[0]; if(body&&tt){ ok('正文距标题块 16', rect(body).top-rect(head).bottom+px(cs(head).paddingBottom), 16, 0.5); } }
    }
    // 分组列表
    const g=qa('.group')[0]; if(g){ ok('卡片圆角 26', px(cs(g).borderTopLeftRadius), 26, 0.5); const gr=rect(g); const host=sh&&sh.contains(g)?rect(sh):{left:0,right:W}; ok('卡片内缩 = 布局边距 '+INSET, gr.left-host.left, INSET, 0.5); }
    const single=qa('.row').find(r=>!r.querySelector('.hint,.seg,input[type=range]')&&!r.classList.contains('slider')); if(single){ const rr=rect(single); ok('单行 52.33（Row Regular 52 + 分隔线）', rr.height, 52.33, 0.5, single.textContent.trim().slice(0,12)); ok('行左内缩 '+(single.classList.contains('icon')?'18（有图标）':'20'), px(cs(single).paddingLeft), single.classList.contains('icon')?18:20, 0.1); ok('行右内缩 20', px(cs(single).paddingRight), 20, 0.1);
      const nx=single.nextElementSibling; if(nx&&nx.classList.contains('row')){ const sp=cs(nx,'::before'); ok('分隔线内缩 '+(nx.classList.contains('icon')?60:20), px(sp.left), nx.classList.contains('icon')?60:20, 0.1); ok('分隔线 0.67 粗', Math.abs(px(sp.height)*parseFloat((sp.transform.match(/matrix\(([^)]+)\)/)||['','1,0,0,1'])[1].split(',')[3])-0.67)<0.05, true, 0, sp.height+' '+sp.transform); } }
    const two=qa('.row').find(r=>r.querySelector('.hint')); if(two){ const rr=rect(two); ok('双行 68.33（Row Tall 68 + 分隔线）', rr.height, 68.33, 0.5, two.textContent.trim().slice(0,12)); }
    const ico=qa('.row .ico')[0]; if(ico){ const ir=rect(ico); const rw=rect(ico.closest('.row')); ok('行图标 28', ir.width===28&&ir.height===28, true, 0, num(ir.width)+'×'+num(ir.height)); ok('行图标距卡片边 18', ir.left-rw.left, 18, 0.1); ok('行文字起点 60', rect(ico.closest('.row').querySelector('.lab')).left-rw.left, 60, 0.5); }
    const nm=qa('.row .name')[0]; if(nm){ ok('行文字 17/22', px(cs(nm).fontSize)===root && Math.abs(px(cs(nm).lineHeight)-root*22/17)<0.3, true, 0, px(cs(nm).fontSize)+'/'+num(px(cs(nm).lineHeight))); }
    const h2=qa('.sect h2')[0]; if(h2){ const c=cs(h2); ok('段头 17 半粗', px(c.fontSize)===root&&+c.fontWeight>=600, true, 0, px(c.fontSize)+' w'+c.fontWeight); ok('段头下距 6', px(c.paddingBottom), 6, 0.1); const nxt=h2.nextElementSibling; if(nxt) ok('段头→卡片 6', rect(nxt).top-rect(h2).bottom, 0, 0.5, '内边距已含'); const sec=h2.parentElement; const isFirst=sec===sec.parentElement.firstElementChild; ok(isFirst?'首段头上距 10':'段头上距 28', px(c.paddingTop), isFirst?10:28, 0.1); const inSheet=!!(sh&&sh.contains(h2)); ok(inSheet?'段头内缩 = 布局边距（地图 App 卡片：与卡片对齐）':'段头文字内缩 = 布局边距 + 20（设置 App）', px(c.paddingLeft), inSheet?INSET:INSET+20, 0.1); ok('段头颜色 = '+(inSheet?'label（地图 App）':'secondaryLabel（设置 App）'), c.color, inSheet?cs(document.body).color:c.color, 0); }
    const ft=qa('.sect .foot').find(f=>f.previousElementSibling&&f.previousElementSibling.classList.contains('group')); if(ft){ const c=cs(ft); ok('段尾 13/18', Math.abs(px(c.fontSize)-root*13/17)<0.2&&Math.abs(px(c.lineHeight)-root*18/17)<0.3, true, 0, num(px(c.fontSize))+'/'+num(px(c.lineHeight))); ok('段尾上 6 下 24', px(c.paddingTop)===6&&px(c.paddingBottom)===24, true, 0, c.paddingTop+' '+c.paddingBottom); }
    const gg=qa('.group + .group')[0]; if(gg){ ok('卡片间 35', px(cs(gg).marginTop), 35, 0.1); }
    // 控件
    const seg=qa('.seg').find(x=>!x.closest('.bar')); if(seg){ const c=cs(seg); ok('分段控件高 '+(seg.classList.contains('l')?50:32), rect(seg).height, seg.classList.contains('l')?50:32, 0.5); ok('分段内边 2 段间 4', px(c.paddingTop)===2&&px(c.columnGap||c.gap)===4, true, 0, c.padding+' gap '+(c.columnGap||c.gap)); const on=seg.querySelector('[aria-pressed="true"]'); if(on) ok('选中段白底', cs(on).backgroundColor!=='rgba(0, 0, 0, 0)', true, 0, cs(on).backgroundColor); }
    const bs={s:28,m:34,l:50}; for(const k in bs){ const b=qa('.btn.'+k)[0]; if(b) ok('按钮 '+k.toUpperCase()+' 高 '+bs[k], rect(b).height, bs[k], 0.5); }
    const bseg=qa('.bar .seg')[0]; if(bseg) ok('工具条分段控件 44（与圆钮同高；Kit 待核）', rect(bseg).height, 44, 0.5);
    const sw=qa('.sw')[0]; if(sw){ const r=rect(sw); ok('开关 63×28', r.width===63&&r.height===28, true, 0, num(r.width)+'×'+num(r.height)); const k=cs(sw.querySelector('i'),'::after'); ok('开关圆钮 38×24', px(k.width)===38&&px(k.height)===24, true, 0, k.width+'×'+k.height); }
    const sl=qa('.row.slider input[type=range]')[0]; if(sl) ok('滑块热区 28', rect(sl).height, 28, 0.5);
    const tl=qa('.t-large')[0]; if(tl){ const c=cs(tl); ok('大标题 34/41 700', Math.abs(px(c.fontSize)-root*2)<0.2&&+c.fontWeight>=700, true, 0, num(px(c.fontSize))+'/'+num(px(c.lineHeight))+' w'+c.fontWeight); }
    const sfx=qa('.sf')[0]; if(sfx){ const m=cs(sfx).maskImage||cs(sfx).webkitMaskImage; ok('SF Symbols 蒙版已装', /ui\/sf\/.+\.png/.test(m), true, 0, (m||'').slice(0,60)); }
    const mv=cs(document.documentElement).getPropertyValue('--ease').trim(); if(matchMedia('(prefers-reduced-motion: reduce)').matches) ok('减弱动态：过渡关闭', cs(sh||document.body).transitionDuration, '0s', 0);
    // 深色
    const dark=matchMedia('(prefers-color-scheme: dark)').matches; ok('配色 = 系统'+(dark?'深':'浅')+'色', cs(document.body).backgroundColor, dark?'rgb(0, 0, 0)':(sh?cs(document.body).backgroundColor:'rgb(242, 242, 247)'), 0);
    return R;
  }
  function show(){
    const res=run(); const bad=res.filter(r=>!r.pass);
    if(!/[?&]quiet/.test(location.search)){
    let box=q('#accept'); if(!box){ box=document.createElement('pre'); box.id='accept'; box.style.cssText='position:fixed;top:0;left:0;z-index:9999;margin:0;max-height:100dvh;overflow:auto;font:11px/1.45 ui-monospace,Menlo,monospace;background:rgba(255,255,255,.94);color:#000;padding:calc(env(safe-area-inset-top) + 6px) 8px 8px;max-width:100%;white-space:pre-wrap'; document.body.appendChild(box); }
    box.textContent=`${location.pathname}  ${W}×${H}  ${bad.length?'✗ '+bad.length+' 项超差':'✓ 全部通过'}  (${res.length} 项)\n`+res.map(r=>`${r.pass?'✓':'✗'} ${r.name}: ${r.got}${r.want!==undefined&&!r.pass?'  期望 '+r.want:''}${r.note?'  ['+r.note+']':''}`).join('\n');
    }
    document.title=(bad.length?'ACCEPT-FAIL-'+bad.length:'ACCEPT-OK')+' '+location.pathname;
    try{ fetch(location.origin+'/accept', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({page: location.pathname, ua: navigator.userAgent, w: W, h: H, root, results: res})}); }catch(e){}
    console.log('ACCEPT', JSON.stringify(res));
  }
  window.HIG_ACCEPT=show;
  window.addEventListener('load', ()=>setTimeout(show, 1500));
})();
