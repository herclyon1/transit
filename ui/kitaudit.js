/* 组件对账（用户 2026-09-15 晚：「做个工具去验收网页上的组件有哪些是官方的，哪些还是原来老的」）。
   页面地址加 ?kitaudit 即加载（再加 &quiet 不画覆盖层，只 POST）。和 accept.js 的区别：accept.js 只量几处关键数字；
   这里把页面上**每一个**看得见的控件和容器都过一遍，逐个对上一个 Kit 组件（数字出自 hig-kit/NUMBERS.md：iOS 27 / macOS 27 UI Kit）：
     ✅ 对上 Kit 且尺寸对          ⚠ 对上了某个 Kit 组件但尺寸/圆角/字号不对（半截）
     ✗ 没对上任何 Kit 规则 = 老样式 / 漏改（KIT-MAP.md 写了每一类该换成什么）   内容 = 地图标记/图例色块/吉祥物，不是控件，不计入
     （2026-09-15 晚用户拍板：「Kit 没有这种组件」不成立，◇ 这一档取消）
   结果：document.title = KIT-OK 或 KIT-FAIL-n；POST /accept，写 .accept/kitaudit_<页>.json（pipeline/ui/kit-audit.py 收集）。
   量之前先把页面「用起来」（打开城市卡片 / 图例 / 完成卡 / 钉子弹出），藏起来的组件才量得到。 */
(function(){
  if(!/[?&]kitaudit/.test(location.search)) return;
  const MAC=matchMedia('(min-width:900px) and (pointer:fine)').matches;
  const rect=el=>el.getBoundingClientRect(); const cs=(el,ps)=>getComputedStyle(el,ps||null); const px=v=>parseFloat(v)||0;
  const num=v=>Math.round(v*10)/10; const near=(a,b,t=1)=>Math.abs(a-b)<=t; const anyOf=(v,list,t=1)=>list.some(x=>near(v,x,t));
  const R=el=>px(cs(el).borderTopLeftRadius);
  const isCapsule=(el,r)=>R(el)>=Math.min(r.width,r.height)/2-0.75;
  const font=el=>{ const c=cs(el); return {size:px(c.fontSize), lh:px(c.lineHeight), w:+c.fontWeight||400, color:c.color}; };
  const alpha=c=>{ const m=/rgba?\(([^)]+)\)/.exec(c||''); if(!m) return 0; const p=m[1].split(',').map(parseFloat); return p.length>3?p[3]:1; };
  const bg=el=>cs(el).backgroundColor;
  const visible=el=>{ if(el.closest('#accept,#kitaudit,.maplibregl-canvas-container,svg,#map canvas')) return false; const r=rect(el); if(!(r.width>0&&r.height>0)) return false;
    for(let e=el;e;e=e.parentElement){ const c=cs(e); if(c.display==='none'||c.visibility==='hidden'||+c.opacity===0) return false; if(e.hidden) return false; } return true; };
  const desc=el=>{ const t=(el.innerText||el.value||el.getAttribute('aria-label')||'').trim().replace(/\s+/g,' ').slice(0,18); return el.tagName.toLowerCase()+(el.id?'#'+el.id:'')+(el.className&&typeof el.className==='string'?'.'+el.className.trim().split(/\s+/).slice(0,3).join('.'):'')+(t?' “'+t+'”':''); };
  const geo=el=>{ const r=rect(el), f=font(el); return `${num(r.width)}×${num(r.height)} r${num(R(el))} ${num(f.size)}/${num(f.lh)} w${f.w}`; };

  // ---------- 规则表：先匹配的先算；sel 命中 → check 给出问题列表（空 = ✅）。ref = Kit 出处（NUMBERS.md 的行）。 ----------
  // want 写成人话，报告里直接给用户看。
  const RULES=[];
  const clipped=el=>{ const inner=[...el.querySelectorAll('span,div')].concat([el]); return inner.some(x=>x.scrollWidth>x.clientWidth+1)?['文字被裁（'+(el.innerText||'').trim().slice(0,8)+'…）']:[]; };   // 等宽段里长标签被 overflow 切掉也算没做完
  const rule=(o)=>RULES.push(o);
  // — Sheet / 侧栏 —
  rule({name:'Sheet（中/大档）', ref:'iOS 27 Kit › Sheets › iPhone：左右内缩 8、四角 34；大档满宽上角 38', plat:'ios', sel:'.sheet:not(.opt)', leaf:false,
    check:el=>{ const r=rect(el); const p=[]; const large=el.classList.contains('large'); if(large){ if(!near(R(el),38)) p.push(`大档上角 ${num(R(el))}≠38`); if(!near(r.left,0)) p.push(`大档应满宽，左 ${num(r.left)}`); } else { if(!near(R(el),34)) p.push(`圆角 ${num(R(el))}≠34`); if(!near(r.left,8)) p.push(`左内缩 ${num(r.left)}≠8`); } return p; }});
  rule({name:'侧栏 = Windows › Left Pane，按 Maps 组合：200 宽贴左通高、无圆角', ref:'macOS 27 Kit › Windows › Left Pane；NUMBERS.md「macOS 27 地图 App 的组合尺寸」', plat:'mac', sel:'.sheet:not(.opt)', leaf:false,
    check:el=>{ const r=rect(el); const p=[]; if(!near(r.width,200)) p.push(`宽 ${num(r.width)}≠200`); if(!near(R(el),0)) p.push(`圆角 ${num(R(el))}≠0`); if(!near(r.left,0)) p.push(`左 ${num(r.left)}≠0`); if(!near(r.top,0)||!near(r.height,innerHeight)) p.push(`不通高 ${num(r.top)}+${num(r.height)}`); return p; }});
  rule({name:'第二面板 = Popover 320 r20，Maps「Map Modes」位：右缘 1222（右列左 14）、顶 13', ref:'macOS 27 Kit › Popovers；styl-work/native-mapmodes.png（1280×744 @2x，2026-09-16）', plat:'mac', sel:'.sheet.opt', leaf:false, check:el=>{ const r=rect(el); const p=[]; if(!near(R(el),20)) p.push(`圆角 ${num(R(el))}≠20`); if(!near(r.width,320)) p.push(`宽 ${num(r.width)}≠320`); if(!near(innerWidth-r.right,58,1.5)) p.push(`右缘距窗右 ${num(innerWidth-r.right)}≠58（= 右列 8+36+14）`); if(!near(r.top,13,1.5)) p.push(`顶 ${num(r.top)}≠13`); return p; }});
  rule({name:'第二张 Sheet（大阪图层）', ref:'iOS 27 Kit › Sheets', plat:'ios', sel:'.sheet.opt', leaf:false, check:el=>near(R(el),34)||near(R(el),38)?[]:[`圆角 ${num(R(el))}∉{34,38}`]});
  // ---- 材质 = 系统配方（MATERIALS.md §3/§4，hig.css §19；computed 值逐字比，亮色） ----
  const BF=(el,want)=>{ const v=(cs(el).backdropFilter||cs(el).webkitBackdropFilter||'').replace(/\s+/g,' ').trim(); return v===want?[]:[`backdrop-filter「${v}」≠「${want}」`]; };
  const BG=(el,want)=>{ const v=cs(el).backgroundColor; return v===want?[]:[`background「${v}」≠「${want}」`]; };
  rule({name:'侧栏材质 = UIKit 玻璃侧栏（MATERIALS.md §4 sidebar：blur 10，Face 0.4+0.63·in，Sat 1.2，白填 20%，MaxLuma 0.85）', ref:'MATERIALS.md §4「sidebar」行 + §4 CSS 表；合成式见 hig.css §19', plat:'mac', sel:'#matSidebar', leaf:false,
    check:el=>[...BF(el,'blur(10px) contrast(0.326) brightness(1.544) saturate(1.2)'),...BG(el,'rgb(224, 224, 224)'),...(cs(el).mixBlendMode==='darken'?[]:['MaxLuma 需 mix-blend-mode: darken']),...(cs(document.getElementById('sheet')).backgroundColor==='rgba(0, 0, 0, 0)'?[]:['侧栏本体应透明（材质在 #matSidebar）'])]});
  rule({name:'地点卡材质 = NSVisualEffectMaterial popover(6)（MATERIALS.md §3：blur 30，sat 2.0，rgba(246,246,246,.6)，#f1f1f1 darken）', ref:'MATERIALS.md §3 popover 行、§6（systemMaterial 默认）', plat:'mac', sel:'#matCard', leaf:false,
    check:el=>[...BF(el,'blur(30px) saturate(2) contrast(0.257) brightness(1.558)'),...BG(el,'rgb(241, 241, 241)'),...(cs(el).mixBlendMode==='darken'?[]:['darken 填充缺'])]});
  rule({name:'Map Modes 弹窗材质 = NSPopover 玻璃（MATERIALS.md §4：blur 10，Face 0.2+0.75·in，白填 10%，ring 6%）', ref:'MATERIALS.md §4「NSPopover frame」行', plat:'mac', sel:'.sheet.opt', leaf:false,
    check:el=>[...BF(el,'blur(10px) contrast(0.65) brightness(1.15)'),...BG(el,'rgba(255, 255, 255, 0.1)')]});
  rule({name:'右列玻璃钮材质 = UIGlassEffect clear（MATERIALS.md §4：blur 10，Face 0.2+0.75·in，白填 10%，顶光 0.4）', ref:'MATERIALS.md §4「clear, light」行；App 黑底实测 #282828 对 clear 近于 regular', plat:'mac', sel:'.bar button.btn-glass, .maplibregl-ctrl-group', leaf:false,
    check:el=>[...BF(el,'blur(10px) contrast(0.65) brightness(1.15)'),...BG(el,'rgba(255, 255, 255, 0.1)')]});
  rule({name:'搜索框材质 = 玻璃搜索框参数（MATERIALS.md §4 search field：blur 5，Face 0.4+0.56·in，Sat 1.2，白填 20%）', ref:'MATERIALS.md §4「search field」行（BlurOpacity 0.4 / Bleed / 折射略）', plat:'mac', sel:'#list .head .search', leaf:false,
    check:el=>[...BF(el,'blur(5px) contrast(0.41) brightness(1.36) saturate(1.2)'),...BG(el,'rgba(255, 255, 255, 0.2)')]});
  // ---- iPhone 材质（MATERIALS.md §2 / §4，hig.css §20） ----
  rule({name:'Sheet 材质 = UIGlassEffect regular（MATERIALS.md §4 基线：blur 5，Face 0.4+0.56·in，Sat 1.2，白填 20%；模拟器 Maps 黑底 #858585 = 0.52 对上）', ref:'MATERIALS.md §4「Baseline — regular glass, light」；raw/renders/ios-maps-globe-sheet.png', plat:'ios', sel:'.sheet', leaf:false,
    check:el=>[...BF(el,'blur(5px) contrast(0.41) brightness(1.36) saturate(1.2)'),...BG(el,'rgba(255, 255, 255, 0.2)')]});
  rule({name:'44 圆钮材质 = UIGlassEffect regular（MATERIALS.md §4 基线：blur 5，Face 0.4+0.56·in，Sat 1.2，白填 20%，顶光 .5）', ref:'MATERIALS.md §4「Baseline — regular glass, light」', plat:'ios', sel:'.bar button.btn-glass, .map-ctl .btn-glass', leaf:false,
    check:el=>[...BF(el,'blur(5px) contrast(0.41) brightness(1.36) saturate(1.2)'),...BG(el,'rgba(255, 255, 255, 0.2)')]});
  rule({name:'搜索胶囊材质 = 玻璃搜索框参数（MATERIALS.md §4 search field：regular 脸 + blur 5 + 白填 20%）', ref:'MATERIALS.md §4「search field」行', plat:'ios', sel:'.sheet .head .search', leaf:false,
    check:el=>[...BF(el,'blur(5px) contrast(0.41) brightness(1.36) saturate(1.2)'),...BG(el,'rgba(255, 255, 255, 0.2)')]});
  rule({name:'Map Modes 弹窗无关闭钮（点外部关闭）', ref:'styl-work/native-mapmodes.png（Maps.app 2026-09-16）', plat:'mac', sel:'.sheet.opt', leaf:false, check:el=>{ const x=el.querySelector('#optClose'); return !x||rect(x).width===0?[]:['弹窗上有 × 钮，Maps.app 的 Map Modes 没有']; }});
  rule({name:'抓手 60×4', ref:'iOS 27 Kit › Toolbars › Top - Sheet', plat:'ios', sel:'.sheet .grab i', check:el=>{ const r=rect(el); return near(r.width,60)&&near(r.height,4)?[]:[`${num(r.width)}×${num(r.height)}≠60×4`]; }});
  rule({name:'抓手（桌面不显示）', ref:'macOS 无 Sheet 抓手', plat:'mac', sel:'.sheet .grab', check:()=>[]});
  rule({name:'抓手块 15（抓手 60×4 @5）', ref:'iOS 27 Kit › Toolbars › Top - Sheet', plat:'ios', sel:'.sheet .grab', leaf:false, check:el=>{ const h=rect(el).height; return near(h,15)?[]:[`抓手块 ${num(h)}≠15`]; }});
  rule({name:'地点卡片 = Maps 浮动卡 320（左距侧栏 8、上下 8）+ Popover 材质 r20', ref:'NUMBERS.md「macOS 27 地图 App 的组合尺寸」；macOS 27 Kit › Popovers', plat:'mac', sel:'.sheet.split #card', leaf:false,
    check:el=>{ const r=rect(el); const p=[]; if(!near(r.width,320)) p.push(`宽 ${num(r.width)}≠320`); if(!near(R(el),20)) p.push(`圆角 ${num(R(el))}≠20`); if(!near(r.left,208)) p.push(`左 ${num(r.left)}≠208`); if(!near(r.top,8)||!near(innerHeight-r.bottom,8)) p.push(`上下 ${num(r.top)}/${num(innerHeight-r.bottom)}≠8`); return p; }});
  rule({name:'卡片/面板/弹出窗的关闭 = 工具条玻璃钮 Medium 24；地点卡片 28（Maps，Kit XL 内钮）', ref:'macOS 27 Kit › Titlebars and Toolbars › Buttons › Medium 24 / XL 内钮 28', plat:'mac', sel:'.sheet .head .btn-glass', check:el=>{ const r=rect(el); const want=el.closest('.sheet.split #card')?28:24; return near(r.width,want)&&near(r.height,want)?[]:[`${num(r.width)}×${num(r.height)}≠${want}`]; }});
  rule({name:'Sheet 头（Top - Sheet 70 高）', ref:'iOS 27 Kit › Toolbars › Top - Sheet', plat:'ios', sel:'.sheet .head', leaf:false, check:el=>{ const h=rect(el).height; return el.querySelector('.search')?[]:(near(h,54)||near(h,60)?[]:[`头高 ${num(h)}（抓手块外应 1+44+10=55）`]); }});
  rule({name:'侧栏头 = Kit 标题栏 52；地点卡片头 = Maps（28 钮 @12，标题距卡顶 48）', ref:'macOS 27 Kit › Windows › Titlebar 52；NUMBERS.md 地图 App 组合', plat:'mac', sel:'.sheet .head', leaf:false, check:el=>{ const h=rect(el).height; if(el.closest('.sheet.split #card')){ const t=el.querySelector('.t-title2'); const card=el.closest('#card'); return t&&near(rect(t).top-rect(card).top,48,1)?[]:[`标题距卡顶 ${t?num(rect(t).top-rect(card).top):'?'}≠48`]; } if(el.closest('.sheet.opt')){ const t=el.querySelector('.t-head'); const f=t&&font(t); return f&&near(f.size,17,.3)&&f.w>=700?[]:[`弹窗标题应 17 Bold（Maps「Map Modes」实机）`]; } const sf=el.querySelector('.search'); if(sf){ const r=rect(sf); return near(r.left,15)&&near(r.top,47)&&near(r.width,170)&&near(r.height,36)?[]:[`搜索框 ${num(r.width)}×${num(r.height)} @(${num(r.left)},${num(r.top)})≠170×36 @(15,47)（Maps.app 侧栏搜索，NUMBERS.md 组合尺寸）`]; } return near(h,52)?[]:[`标题栏 ${num(h)}≠52`]; }});
  rule({name:'建议卡里的 × 和链接（随 .sugg，老样式）', ref:'KIT-MAP', plat:'both', sel:'.sugg .x, .sugg .a, .sugg button, .sugg a', check:()=>['老样式：随 .sugg 一起改成 Header Prominent 的 trailing Action']});
  rule({name:'段头里的 Action（Header › Prominent › Trailing › Action）', ref:'iOS 27 Kit › Lists › Headers', plat:'both', sel:'.mh .act', check:()=>[]});
  rule({name:'动作行容器', ref:'随动作行', plat:'both', sel:'.actions', leaf:false, check:el=>{ const r=rect(el); return el.scrollWidth<=r.width+0.5?[]:[`内容 ${el.scrollWidth} 宽超出 ${num(r.width)}（按钮被裁）`]; }});
  rule({name:'Sheet 头圆钮 44', ref:'iOS 27 Kit › Toolbars › Top - Sheet：44 圆 @(16,16)', plat:'ios', sel:'.sheet .head .btn-glass', check:el=>{ const r=rect(el); return near(r.width,44)&&near(r.height,44)?[]:[`${num(r.width)}×${num(r.height)}≠44`]; }});
  rule({name:'Sheet 头标题 Semibold 15/20', ref:'iOS 27 Kit › Toolbars › Top - Sheet › Title 2 Line', plat:'ios', sel:'.sheet .head .t-title2', check:el=>{ const f=font(el); return near(f.size,15,.3)&&near(f.lh,20,.3)&&f.w>=600?[]:[`${num(f.size)}/${num(f.lh)} w${f.w}`]; }});
  rule({name:'Sheet 头副标题 Medium 12/16', ref:'同上', plat:'ios', sel:'.sheet .head .t-sub', check:el=>{ const f=font(el); return near(f.size,12,.3)&&f.w>=500?[]:[`${num(f.size)}/${num(f.lh)} w${f.w}`]; }});
  rule({name:'窗口标题 Bold 15（带侧栏）/ 地点卡片标题 Title 1 22 Bold（Maps）', ref:'macOS 27 Kit › Titlebars and Toolbars › Window › Title；Kit 文本样式 Title 1', plat:'mac', sel:'.sheet .head .t-title2', check:el=>{ const f=font(el); const inCard=!!el.closest('.sheet.split #card'); return inCard?(near(f.size,22,.3)&&f.w>=700?[]:[`${num(f.size)} w${f.w}≠22 Bold`]):(near(f.size,15,.3)&&f.w>=700?[]:[`${num(f.size)} w${f.w}≠15 Bold`]); }});
  rule({name:'侧栏副标题 Medium 11', ref:'macOS 27 Kit › Window › Title › subtitle', plat:'mac', sel:'.sheet .head .t-sub', check:el=>{ const f=font(el); return near(f.size,11,.3)?[]:[`${num(f.size)}≠11`]; }});
  rule({name:'搜索胶囊 44', ref:'iOS 27 Kit › Search 44 r1000', plat:'ios', sel:'.search', check:el=>{ const r=rect(el); return near(r.height,44)&&isCapsule(el,r)?[]:[`高 ${num(r.height)}≠44 或不是胶囊`]; }});
  rule({name:'搜索框 24 / 36 胶囊', ref:'macOS 27 Kit › Search Fields / Toolbar search', plat:'mac', sel:'.search', check:el=>{ const r=rect(el); return anyOf(r.height,[24,36])&&isCapsule(el,r)?[]:[`高 ${num(r.height)}∉{24,36} 或不是胶囊`]; }});
  // — 工具条 —
  rule({name:'工具条圆钮 44（分段条里 48）', ref:'iOS 27 Kit › Toolbars › Buttons 44pt / 48pt', plat:'ios', sel:'.bar .btn-glass, .map-ctl .btn-glass',
    check:el=>{ const r=rect(el); const want=el.closest('.bar')&&el.closest('.bar').querySelector('.seg')?48:44; return near(r.height,want)&&r.width>=want-0.5&&isCapsule(el,r)?[]:[`${num(r.width)}×${num(r.height)}≠${want} 胶囊`]; }});
  rule({name:'工具条玻璃钮 36 胶囊（右列 @右 8）；返回目录 = 侧栏底灰 Footnote「目录 ›」14 高（Maps Terms 位）', ref:'macOS 27 Kit › Titlebars and Toolbars › XL 36；Buttons › Regular 24', plat:'mac', sel:'.bar .btn-glass, .map-ctl .btn-glass', check:el=>{ const r=rect(el); if(el.matches('.bar > a:first-child')) return near(r.height,14)&&near(r.left,16)&&near(innerHeight-r.bottom,13)?[]:[`${num(r.width)}×${num(r.height)} @(${num(r.left)},底 ${num(innerHeight-r.bottom)})≠14 高 @(16,底 13)（Maps「Terms & Conditions ›」实机）`]; return near(r.height,36)&&isCapsule(el,r)&&near(innerWidth-r.right,8)?[]:[`${num(r.width)}×${num(r.height)} 右 ${num(innerWidth-r.right)}≠36 胶囊 @右 8`]; }});
  rule({name:'工具条分段 Large 48（段 44）/ Small 32（段 28）', ref:'iOS 27 Kit › Segmented Controls', plat:'ios', sel:'.bar .seg', leaf:false,
    check:el=>{ const r=rect(el); const b=el.querySelector('button'); const p=[]; if(!anyOf(r.height,[32,48])) p.push(`高 ${num(r.height)}∉{32,48}`); if(b){ const bh=rect(b).height; if(!anyOf(bh,[28,44])) p.push(`段 ${num(bh)}∉{28,44}`); } return p; }});
  rule({name:'工具条分段 XL 36（段 28，分隔 3×22）', ref:'macOS 27 Kit › Titlebars and Toolbars › Segmented Control', plat:'mac', sel:'.bar .seg', leaf:false,
    check:el=>{ const r=rect(el); const b=el.querySelector('button'); const p=[]; if(!near(r.height,36)) p.push(`高 ${num(r.height)}≠36`); if(b&&!near(rect(b).height,28)) p.push(`段 ${num(rect(b).height)}≠28`); return p; }});
  rule({name:'行内分段 Small 32（段 28）', ref:'iOS 27 Kit › Segmented Controls › Small', plat:'ios', sel:'.seg', leaf:false, check:el=>{ const r=rect(el); return near(r.height,32)?[]:[`高 ${num(r.height)}≠32`]; }});
  rule({name:'行内分段 Regular 24 r6', ref:'macOS 27 Kit › Segmented Controls › Regular', plat:'mac', sel:'.seg', leaf:false, check:el=>{ const r=rect(el); return near(r.height,24)&&near(R(el),6)?[]:[`${num(r.height)} r${num(R(el))}≠24 r6`]; }});
  rule({name:'分段里的段', ref:'随分段控件', plat:'both', sel:'.seg button', check:el=>clipped(el)});
  rule({name:'列表行里的图标 / 右侧值（随行：Kit 行图标 24 / iOS 34 圆）', ref:'随列表行（清单 A9/B1）', plat:'both', sel:'.mrow .ico, .mrow .val, .mrow .flag, .ico', check:()=>[]});
  rule({name:'菜单（Menus：r12、行 24、Medium 13）', ref:'macOS 27 Kit › Menus', plat:'mac', sel:'.menu, [role=menu]', leaf:false, check:el=>{ const p=[]; if(!near(R(el),12)) p.push(`圆角 ${num(R(el))}≠12`); const it=el.querySelector('button,[role^=menuitem]'); if(it&&!near(rect(it).height,24)) p.push(`行 ${num(rect(it).height)}≠24`); return p; }});
  rule({name:'菜单 = Menus › iPhone（250 宽、项 42、字 @68）', ref:'iOS 27 Kit › Menus › iPhone', plat:'ios', sel:'.menu, [role=menu]', leaf:false, check:el=>{ const p=[]; if(!near(rect(el).width,250)) p.push(`宽 ${num(rect(el).width)}≠250`); const it=el.querySelector('button,[role^=menuitem]'); if(it){ if(!near(rect(it).height,42)) p.push(`项 ${num(rect(it).height)}≠42`); if(!near(px(cs(it).paddingLeft),68)) p.push(`字起点 ${num(px(cs(it).paddingLeft))}≠68`); } return p; }});
  rule({name:'菜单项', ref:'随菜单', plat:'both', sel:'.menu button, [role=menuitemradio], [role=menuitem]', check:()=>[]});
  // — 列表 —
  rule({name:'段头 Prominent 45：Semibold 20 label + trailing Action', ref:'iOS 27 Kit › Lists › Header › Prominent', plat:'ios', sel:'.mh.prominent', check:el=>{ const f=font(el); return near(f.size,20,.3)&&f.w>=600?[]:[`${num(f.size)} w${f.w}≠20 Semibold`]; }});
  rule({name:'侧栏段头 Large Bold 13', ref:'macOS 27 Kit › Sidebars › Headers › Large', plat:'mac', sel:'.mh.prominent', check:el=>{ const f=font(el); return near(f.size,13,.3)&&f.w>=700?[]:[`${num(f.size)} w${f.w}≠13 Bold`]; }});
  rule({name:'列表段头 Nested 42：Semibold 17 secondaryLabel', ref:'iOS 27 Kit › Lists › Header › Nested', plat:'ios', sel:'.mh', check:el=>{ const f=font(el); const p=[]; if(!near(f.size,17,.3)||f.w<600) p.push(`${num(f.size)} w${f.w}≠17 Semibold`); if(!/rgba\(60, 60, 67, 0\.6\)/.test(f.color)) p.push('颜色不是 secondaryLabel'); return p; }});
  rule({name:'侧栏段头 Bold 11；地点卡片段头 Title 3 15 Semibold（Maps「Details」）', ref:'macOS 27 Kit › Sidebars › Headers；Kit 文本样式 Title 3', plat:'mac', sel:'.mh', check:el=>{ const f=font(el); if(el.closest('.sheet.split #card')) return near(f.size,15,.3)&&f.w>=600?[]:[`${num(f.size)} w${f.w}≠15 Semibold`]; return near(f.size,11,.3)&&f.w>=700?[]:[`${num(f.size)} w${f.w}≠11 Bold`]; }});
  rule({name:'首页行（设置式列表行 52 / 68）', ref:'iOS 27 Kit › Lists › Rows（清单 F2–F4）', plat:'ios', sel:'.row', check:el=>{ const h=rect(el).height; return anyOf(h,[52,68],1.5)?[]:[`行高 ${num(h)}∉{52,68}`]; }});
  rule({name:'首页行 = 侧栏行 Large 40', ref:'macOS 27 Kit › Sidebars › Rows › Large（清单 F2–F4）', plat:'mac', sel:'.row', check:el=>{ const h=rect(el).height; return near(h,40)?[]:[`行高 ${num(h)}≠40`]; }});
  rule({name:'首页说明文字（Subheadline）', ref:'Kit Text styles', plat:'both', sel:'.sub, .t-sub, .mnote, .foot, .hint', check:()=>[]});
  rule({name:'列表行 Large 68 / Default 52', ref:'iOS 27 Kit › Lists › Rows', plat:'ios', sel:'.mrow', check:el=>{ const h=rect(el).height; return anyOf(h,[52,68])?[]:[`行高 ${num(h)}∉{52,68}`]; }});
  rule({name:'侧栏行 Large 40 / Medium 32 / Small 24', ref:'macOS 27 Kit › Sidebars › Rows', plat:'mac', sel:'.mrow', check:el=>{ const h=rect(el).height; return anyOf(h,[24,32,40])?[]:[`行高 ${num(h)}∉{24,32,40}`]; }});
  rule({name:'可展开行（岗位/来源）= 列表行 Large 68 + 展开指示', ref:'iOS 27 Kit › Lists › Rows › Large（清单 A14）', plat:'ios', sel:'.job .jr', check:el=>{ const h=rect(el).height; return h>=52-0.5&&h<=68.5?[]:[`行高 ${num(h)}∉[52,68]`]; }});
  rule({name:'可展开行 = 侧栏行 Large 40 + Disclosure', ref:'macOS 27 Kit › Sidebars › Rows › Large（清单 A14）', plat:'mac', sel:'.job .jr', check:el=>{ const h=rect(el).height; return h<=40.5?[]:[`行高 ${num(h)}>40（内容折行）`]; }});
  rule({name:'列表行 Default 52 / Large 68（Lists › Rows）', ref:'iOS 27 Kit › Lists › Rows', plat:'ios', sel:'.r', check:el=>{ const h=rect(el).height; if(el.matches('.slider')) return h>=52-0.5?[]:[`滑块行 ${num(h)}<52`]; return anyOf(h,[52,68],1.5)?[]:[`行高 ${num(h)}∉{52,68}（副题折行了？Kit 行的副题只有一行）`]; }});
  rule({name:'勾选框行 = Kit Checkbox 16 在 24 行里 @y4（Maps「Map Modes」白盒 Traffic/Labels 行点击区 23–24，PLAN-MAC-LOOK §0 #26）', ref:'macOS 27 Kit › Toggles - Checkboxes › Regular', plat:'mac', sel:'.r:has(.cb)', leaf:false, check:el=>{ const h=rect(el).height; return near(h,24)?[]:[`行高 ${num(h)}≠24`]; }});
  rule({name:'表单行 40 / 48 / 56（Forms › Row）', ref:'macOS 27 Kit › Forms', plat:'mac', sel:'.r', check:el=>{ const h=rect(el).height; return anyOf(h,[40,48,56],1)?[]:[`行高 ${num(h)}∉{40,48,56}（副题折行了？Kit 行的副题只有一行）`]; }});
  rule({name:'分组列表容器（Grouped Table View r26 白底）', ref:'iOS 27 Kit › Lists › Grouped Table View', plat:'ios', sel:'.mcard, .group', leaf:false, check:el=>near(R(el),26)?[]:[`圆角 ${num(R(el))}≠26`]});
  rule({name:'分组框（Group Boxes r12 黑 3%）；地点卡里的键值组无框 + 发丝线（Maps「Details」实机 2026-09-16）', ref:'macOS 27 Kit › Group Boxes；PLAN-MAC-LOOK 第 0 节 #17', plat:'mac', sel:'.mcard, .group', leaf:false, check:el=>{ if(el.closest('.sheet.split #card')){ const boxed=!!el.querySelector('.job'); const bg=cs(el).backgroundColor; return boxed?(near(R(el),12)&&bg!=='rgba(0, 0, 0, 0)'?[]:[`列表组应是 r12 白盒（${bg} r${num(R(el))}）`]):(bg==='rgba(0, 0, 0, 0)'?[]:[`键值组不该有底色（${bg}）`]); } return near(R(el),12)?[]:[`圆角 ${num(R(el))}≠12`]; }});
  rule({name:'地点卡底部工具条 = Maps 36 胶囊 @底 8（Kit XL 工具条钮组）', ref:'PLAN-MAC-LOOK 第 0 节 #19', plat:'mac', sel:'.cardbar', leaf:false, check:el=>{ const r=rect(el), c=el.closest('#card'); return near(r.height,36)&&isCapsule(el,r)&&c&&near(rect(c).bottom-r.bottom,8)?[]:[`${num(r.height)} 底距 ${c?num(rect(c).bottom-r.bottom):'?'}≠36 胶囊 @底 8`]; }});
  rule({name:'地点卡底部工具条钮 = Maps 3 颗 28 圆钮（Kit XL 内钮 28）', ref:'PLAN-MAC-LOOK 第 0 节 #19', plat:'mac', sel:'.cardbar button', check:el=>{ const r=rect(el); return near(r.width,28)&&near(r.height,28)?[]:[`${num(r.width)}×${num(r.height)}≠28`]; }});
  rule({name:'地图模式 tile = Maps「Map Modes」65 方块 r14（iOS 84 r18）', ref:'PLAN-MAC-LOOK 第 0 节 #26（隔壁实机截图）', plat:'both', sel:'.mode', check:el=>{ const t=el.querySelector('.thumb'); if(!t) return ['没有缩略图']; const r=rect(t); const want=MAC?65:84, rad=MAC?14:18; return near(r.width,want)&&near(r.height,want)&&near(R(t),rad)?[]:[`${num(r.width)}×${num(r.height)} r${num(R(t))}≠${want} r${rad}`]; }});
  rule({name:'统计卡 .stat（Kit 没有 → KIT-MAP：改成分组列表的行）', ref:'KIT-MAP', plat:'both', sel:'.stats, .stat', leaf:false, check:()=>['老样式：要换成 .mcard 里的 .r 行（trailing Detail 放数字）']});
  rule({name:'建议卡 .sugg（Kit 没有 → KIT-MAP：Header Prominent + Footer）', ref:'KIT-MAP', plat:'both', sel:'.sugg', leaf:false, check:()=>['老样式：改成 .mh.prominent + .mfoot']});
  rule({name:'段脚 Footer 30：Regular 13 secondaryLabel', ref:'iOS 27 Kit › Lists › Footer', plat:'ios', sel:'.mfoot', check:el=>{ const f=font(el); return near(f.size,13,.3)?[]:[`${num(f.size)}≠13`]; }});
  rule({name:'段脚 Subheadline 11', ref:'macOS 27 Kit › Text styles', plat:'mac', sel:'.mfoot', check:el=>{ const f=font(el); return near(f.size,11,.3)?[]:[`${num(f.size)}≠11`]; }});
  rule({name:'可展开行（Disclosure 配件）', ref:'iOS 27 Kit › Lists › Accessories › Disclosure；macOS Disclosure Buttons Small 20 r5', plat:'both', sel:'summary:not(.maplibregl-ctrl-attrib-button), [aria-expanded]:not(.maplibregl-ctrl-attrib-button)', check:el=>{ if(!el.matches('.r.disc, .jr[aria-expanded], .mrow[aria-expanded]')) return ['折叠行没用 Kit 的 Disclosure 配件（加 .r.disc）']; const h=rect(el).height; return MAC?(anyOf(h,[40,48,56],1)?[]:[`行高 ${num(h)}∉{40,48,56}`]):(anyOf(h,[52,68],1.5)?[]:[`行高 ${num(h)}∉{52,68}`]); }});
  rule({name:'折叠容器', ref:'随可展开行', plat:'both', sel:'details', leaf:false, check:()=>[]});
  rule({name:'表格（Kit 没有 → KIT-MAP：每档一组 .mcard，四行 .r + trailing Detail）', ref:'KIT-MAP', plat:'both', sel:'table', leaf:false, check:el=>el.closest('.hpop')?[]:['老样式：表格要换成分组列表']});
  // — 按钮 —
  rule({name:'动作行按钮 = Buttons › Medium 34（Mac 地点卡片：主钮 288×45 / 次钮 288×36 胶囊，Maps；卡片外 Regular 24）', ref:'iOS 27 Kit › Buttons › Medium；NUMBERS.md 地图 App 组合；macOS Buttons', plat:'both', sel:'.actions .btn', check:el=>{ const r=rect(el); const p=MAC?(el.closest('.sheet.split #card')?(near(r.width,288)&&anyOf(r.height,[36,45])&&isCapsule(el,r)?[]:[`${num(r.width)}×${num(r.height)}≠288×{36,45} 胶囊`]):(near(r.height,24)?[]:[`高 ${num(r.height)}≠24`])):(near(r.height,34)&&isCapsule(el,r)?[]:[`高 ${num(r.height)}≠34 胶囊`]); return p.concat(clipped(el)); }});
  rule({name:'文字按钮 Small 28 / Medium 34 / Large 50（提示框里 48）', ref:'iOS 27 Kit › Buttons', plat:'ios', sel:'.btn', check:el=>{ const r=rect(el); return anyOf(r.height,[28,34,48,50])&&isCapsule(el,r)?[]:[`高 ${num(r.height)}∉{28,34,50} 或不是胶囊`]; }});
  rule({name:'按钮 Regular 24 r6 / Large 28 胶囊 / XL 36 胶囊', ref:'macOS 27 Kit › Push buttons', plat:'mac', sel:'.btn', check:el=>{ const r=rect(el); if(near(r.height,24)) return near(R(el),6)?[]:[`24 高但圆角 ${num(R(el))}≠6`]; return anyOf(r.height,[28,36])&&isCapsule(el,r)?[]:[`高 ${num(r.height)}∉{24,28,36}`]; }});
  rule({name:'胶囊排（随里面的按钮）', ref:'iOS 27 Kit › Buttons › Small；提醒事项「标签」', plat:'both', sel:'.chips', leaf:false, check:()=>[]});
  rule({name:'筛选胶囊 = Buttons › Small 28 Bordered（Mac Push button 24 r6 / 28 胶囊）', ref:'iOS 27 Kit › Buttons › Small；macOS Push buttons', plat:'both', sel:'.chips button', check:el=>{ const h=rect(el).height; return MAC?(anyOf(h,[24,28])?[]:[`高 ${num(h)}∉{24,28}`]):(near(h,28)?[]:[`高 ${num(h)}≠28`]); }});
  rule({name:'图例小钮 = .btn.s Bordered', ref:'清单 E2', plat:'both', sel:'.lg-jmp, .lg-toggle', check:el=>{ const h=rect(el).height; return MAC?(near(h,24)?[]:[`高 ${num(h)}≠24`]):(near(h,28)?[]:[`高 ${num(h)}≠28`]); }});
  // — 开关 / 滑块 / 勾选 / 输入 —
  rule({name:'开关 63×28', ref:'iOS 27 Kit › Toggles', plat:'ios', sel:'.sw', check:el=>{ const r=rect(el); return near(r.width,63)&&near(r.height,28)?[]:[`${num(r.width)}×${num(r.height)}≠63×28`]; }});
  rule({name:'开关 Regular 54×24', ref:'macOS 27 Kit › Toggles - Switches', plat:'mac', sel:'.sw', check:el=>{ const r=rect(el); return near(r.width,54)&&near(r.height,24)?[]:[`${num(r.width)}×${num(r.height)}≠54×24`]; }});
  rule({name:'开关里的原生 input（隐形）', ref:'随开关', plat:'both', sel:'.sw input', check:()=>[]});
  rule({name:'滑块（轨 4 r2、钮 28）', ref:'iOS 27 Kit › Sliders', plat:'ios', sel:'input[type=range]', check:el=>{ const h=px(cs(el,'::-webkit-slider-runnable-track').height); return near(h,4)?[]:[`轨 ${num(h)}≠4`]; }});
  rule({name:'滑块 Regular（控件 24、轨 6、钮 20×16）', ref:'macOS 27 Kit › Sliders', plat:'mac', sel:'input[type=range]', check:el=>{ const h=px(cs(el,'::-webkit-slider-runnable-track').height); const t=px(cs(el,'::-webkit-slider-thumb').width); const p=[]; if(!near(h,6)) p.push(`轨 ${num(h)}≠6`); if(!near(t,20)) p.push(`钮 ${num(t)}≠20`); return p; }});
  rule({name:'多选圆 22（iOS 无 checkbox → Lists › Rows › Editing）', ref:'iOS 27 Kit › Lists › Rows › Editing（清单 E6）', plat:'ios', sel:'input[type=checkbox]:not(.sw input)', check:el=>{ const r=rect(el); const c=cs(el); if(c.appearance!=='none'&&c.webkitAppearance!=='none') return ['原生 checkbox（不是 Kit 组件）']; return near(r.width,22)&&near(r.height,22)&&isCapsule(el,r)?[]:[`${num(r.width)}×${num(r.height)}≠22 圆`]; }});
  rule({name:'勾选框 Regular 16 r5.5', ref:'macOS 27 Kit › Toggles - Checkboxes（清单 E6）', plat:'mac', sel:'input[type=checkbox]:not(.sw input)', check:el=>{ const r=rect(el); const c=cs(el); if(c.appearance!=='none'&&c.webkitAppearance!=='none') return ['原生 checkbox（不是 Kit 组件）']; return near(r.width,16)&&near(r.height,16)&&near(R(el),5.5,.3)?[]:[`${num(r.width)}×${num(r.height)} r${num(R(el))}≠16 r5.5`]; }});
  rule({name:'原生 <select>（KIT-MAP：换成行里的 Pop-up 配件 .r .pop）', ref:'iOS 27 Kit › Lists › Accessories › Pop-up Button；macOS Pop-up Buttons 24 r6', plat:'both', sel:'select', check:()=>['老样式：原生 select，换成 .r .pop']});
  rule({name:'行里的选择 = Pop-up 配件', ref:'iOS 27 Kit › Lists › Accessories › Pop-up Button；macOS Pop-up Buttons › Regular 24 r6', plat:'both', sel:'.r .pop, .pop', check:el=>MAC?(near(rect(el).height,24)&&near(R(el),6)?[]:[`${num(rect(el).height)} r${num(R(el))}≠24 r6`]):[]});
  rule({name:'文本输入（Mac Text Field 24 r6；iOS 随搜索胶囊）', ref:'macOS 27 Kit › Text Fields', plat:'both', sel:'input[type=text], input[type=search], input:not([type]), textarea', check:el=>{ if(el.closest('.search')) return []; const r=rect(el); return MAC?(near(r.height,24)&&near(R(el),6)?[]:[`${num(r.height)} r${num(R(el))}≠24 r6`]):(near(r.height,44)?[]:[`高 ${num(r.height)}≠44`]); }});
  // — 浮层 —
  rule({name:'提示框 Alert 300 r34（按钮 48）', ref:'iOS 27 Kit › Alerts', plat:'ios', sel:'#doneCard .box, .alert', leaf:false, check:el=>{ const r=rect(el); const p=[]; if(!near(r.width,300)) p.push(`宽 ${num(r.width)}≠300`); if(!near(R(el),34)) p.push(`圆角 ${num(R(el))}≠34`); return p; }});
  rule({name:'提示框 Alert 260 r26（按钮 28）', ref:'macOS 27 Kit › Alerts', plat:'mac', sel:'#doneCard .box, .alert', leaf:false, check:el=>{ const r=rect(el); const p=[]; if(!near(r.width,260)) p.push(`宽 ${num(r.width)}≠260`); if(!near(R(el),26)) p.push(`圆角 ${num(R(el))}≠26`); return p; }});
  rule({name:'浮层 = Popover r20', ref:'macOS 27 Kit › Popovers（清单 C2/E1/E4）', plat:'mac', sel:'#promptBar, #info, .hpop .maplibregl-popup-content', leaf:false, check:el=>near(R(el),20)?[]:[`圆角 ${num(R(el))}≠20`]});
  rule({name:'钉子弹出 = Sheet 材质 r34（iOS 无 Popover）', ref:'清单 C2', plat:'ios', sel:'.hpop .maplibregl-popup-content', leaf:false, check:el=>near(R(el),34)?[]:[`圆角 ${num(R(el))}≠34`]});
  rule({name:'弹出关闭钮 28 圆 / Mac 24', ref:'清单 C2', plat:'both', sel:'.maplibregl-popup-close-button', check:el=>{ const r=rect(el); return near(r.width,MAC?24:28)?[]:[`${num(r.width)}≠${MAC?24:28}`]; }});
  rule({name:'题目条 / 信息浮层 = Sheet 材质 r34（iOS 无 Popover）', ref:'iOS 27 Kit › Sheets（Inspector r34）', plat:'ios', sel:'#promptBar, #info', leaf:false, check:el=>near(R(el),34)?[]:[`圆角 ${num(R(el))}≠34`]});
  rule({name:'图例浮层（KIT-MAP：iOS 第二张 Sheet / Mac Popover r20）', ref:'iOS 27 Kit › Sheets；macOS Popovers', plat:'both', sel:'#legend', leaf:false, check:el=>MAC?(near(R(el),20)?[]:[`圆角 ${num(R(el))}≠20`]):(el.matches('.sheet')&&anyOf(R(el),[34,38])?[]:['老样式：图例要做成 .sheet（r34）'])});
  rule({name:'大阪图例（在 Sheet 里的列表行）', ref:'随列表', plat:'both', sel:'#lg', leaf:false, check:()=>[]});
  rule({name:'提示框遮罩', ref:'随 Alert', plat:'both', sel:'#doneCard', leaf:false, check:()=>[]});
  rule({name:'学習 详情内联卡内容（外层 #cardSect.mcard 是分组列表）', ref:'iOS 27 Kit › Lists', plat:'both', sel:'#card.on', leaf:false, check:()=>[]});
  rule({name:'列表分组容器 .mlist（Grouped Table View r26 / Mac 侧栏组）', ref:'iOS 27 Kit › Lists › Grouped Table View', plat:'both', sel:'.mlist', leaf:false, check:el=>MAC?[]:(near(R(el),26)?[]:[`圆角 ${num(R(el))}≠26`])});
  rule({name:'提示框图标/文字块', ref:'随 Alert', plat:'both', sel:'#doneCard .ico, #doneCard .txt', check:()=>[]});
  // — 地图控件与杂项（Kit 无，清单登记过） —
  rule({name:'MapLibre ± 控件（iOS 地图 App 没有 → 隐藏；Mac = Toolbar 玻璃钮 24/36）', ref:'iOS 27 Kit 无 ±；macOS Titlebars and Toolbars › Buttons', plat:'both', sel:'.maplibregl-ctrl-group', leaf:false, check:el=>{ if(!MAC) return ['iOS 上应隐藏（地图 App 捏合缩放）']; const w=rect(el).width; const b=el.querySelector('button'); const h=b?rect(b).height:0; return anyOf(w,[24,36])&&anyOf(h,[20,28])?[]:[`外框 ${num(w)}∉{24,36} 或钮 ${num(h)}∉{20,28}（XL 36 内钮 28 / Medium 24 内钮 20）`]; }});
  rule({name:'± 钮', ref:'随 ± 控件', plat:'both', sel:'.maplibregl-ctrl-group button', check:()=>[]});
  rule({name:'底图署名 ⓘ = 工具条圆钮（iOS 44 / Mac 24）', ref:'iOS 27 Kit › Toolbars › Buttons；macOS Toolbar Medium 24', plat:'both', sel:'.maplibregl-ctrl-attrib', leaf:false, check:el=>{ const b=el.querySelector('.maplibregl-ctrl-attrib-button'); if(!b||rect(b).width===0) return []; const h=rect(b).height; return MAC?(anyOf(h,[24,36])?[]:[`ⓘ ${num(h)}∉{24,36}`]):(near(h,44)?[]:[`ⓘ ${num(h)}≠44`]); }});
  rule({name:'署名钮/链接', ref:'随署名', plat:'both', sel:'.maplibregl-ctrl-attrib-button, .maplibregl-ctrl-attrib a', check:()=>[]});
  rule({name:'置信度胶囊 / 小圆点（Kit 没有 → KIT-MAP：写进行的副题）', ref:'KIT-MAP', plat:'both', sel:'.tag, .chip', check:()=>['老样式：删掉，置信度写进副题']});
  rule({name:'勾选框 = Kit Toggles - Checkboxes › Regular 16 r5.5', ref:'macOS 27 Kit › Toggles - Checkboxes › Regular；NUMBERS.md「Checkbox」', plat:'mac', sel:'.cb', check:el=>{ const r=rect(el); const i=el.querySelector('i'); return near(r.width,16)&&near(r.height,16)&&i&&near(R(i),5.5,.3)?[]:[`${num(r.width)}×${num(r.height)} r${i?num(R(i)):'?'}≠16 r5.5`]; }});
  rule({name:'多选圆 22（iOS 无方形勾选框）', ref:'iOS 27 Kit › Lists › Rows › Editing', plat:'ios', sel:'.cb', check:el=>{ const r=rect(el); return near(r.width,22)&&near(r.height,22)?[]:[`${num(r.width)}×${num(r.height)}≠22`]; }});
  rule({name:'地图标记 / 图例色块（内容，不是控件）', ref:'内容', plat:'both', sel:'.hubmk, .hublbl, .tsw, #legend i, .lg-head b, .pin, .marker, .lbl, .maplibregl-marker', content:true, check:()=>[]});
  rule({name:'缩略图块 .tiles（KIT-MAP：换成分段控件）', ref:'KIT-MAP', plat:'both', sel:'.tiles, .tiles button, .tiles .tile', check:el=>el.matches('.seg, .seg button')?[]:['老样式：底图选择用 .seg']});
  rule({name:'Claw\'d 吉祥物（内容）', ref:'IDEAS.md #65', plat:'both', sel:'.clawd, #clawd', content:true, check:()=>[]});
  rule({name:'来源列表行（KIT-MAP：换成 .mrow Large 68）', ref:'KIT-MAP', plat:'both', sel:'.links a', check:el=>el.matches('.mrow')?[]:['老样式：来源行要用 .mrow（标题 + 平台·日期）']});
  rule({name:'表格里的链接（随表格）', ref:'KIT-MAP', plat:'both', sel:'table a', check:()=>[]});
  rule({name:'文内链接（tint）', ref:'Kit Colors', plat:'both', sel:'a:not(.btn):not(.btn-glass):not(.mrow)', check:el=>/rgb\(0, 136, 255\)|rgb\(10, 132, 255\)|rgb\(0, 122, 255\)/.test(cs(el).color)?[]:[`链接色 ${cs(el).color} 不是 tint`]});
  rule({name:'玻璃工具条容器', ref:'清单 A1/A26', plat:'both', sel:'.bar, .map-ctl, .btn-group', leaf:false, check:()=>[]});
  rule({name:'工具条文字钮 36（Kit 文本钮 Medium 17 在 44 里）', ref:'iOS 27 Kit › Toolbars › text button', plat:'ios', sel:'.bar .btn-glass.text', check:()=>[]});

  // ---------- 候选：所有可交互元素 + 所有「有底色/圆角的盒子」 ----------
  const INTERACTIVE='button, a[href], input, select, textarea, summary, [role=button], [role=switch], [role=menuitemradio], [role=menuitem], [tabindex]:not([tabindex="-1"])';
  const CONTAINERS='.sheet, .sheet .head, #card, .mh, .mcard, .stat, .sugg, .group, .seg, .chips, .menu, [role=menu], table, details, .glass, .bar, .map-ctl, .maplibregl-ctrl-group, .maplibregl-ctrl-attrib, .maplibregl-popup-content, #doneCard, #doneCard .box, #promptBar, #legend, #lg, #info, .tiles, .r, .mrow, .job .jr, .sw, .tag, .chip, .hubmk, .hublbl, .tsw, .clawd, .grab, .grab i, .t-title2, .t-sub, .search, .actions';
  function candidates(){
    const set=new Set();
    document.querySelectorAll(INTERACTIVE+', '+CONTAINERS).forEach(e=>{ if(visible(e)) set.add(e); });
    // 有底色 + 圆角的盒子（老样式最容易躲在这里）：不在上面的集合里、也不在某个已识别的叶子控件里
    document.querySelectorAll('body *').forEach(e=>{ if(set.has(e)||!visible(e)) return; if(e.closest('svg,.maplibregl-canvas-container,.maplibregl-ctrl,#accept,#kitaudit')) return; const c=cs(e); const r=rect(e);
      if(alpha(c.backgroundColor)>0.02&&px(c.borderTopLeftRadius)>=4&&r.width>=24&&r.height>=16) set.add(e); });
    return [...set];
  }
  function classify(el){
    for(const ru of RULES){ if(ru.plat!=='both'&&ru.plat!==(MAC?'mac':'ios')) continue; if(!el.matches(ru.sel)) continue;
      let probs=[]; try{ probs=ru.check(el)||[]; }catch(e){ probs=['量不到：'+e.message]; }
      return {rule:ru, status: probs.length?'off':(ru.content?'content':'ok'), probs}; }
    return null;
  }
  function run(){
    const items=[]; const leafMatched=[];
    for(const el of candidates()){
      // 已识别叶子控件里的子元素（按钮里的图标/文字）不再单算
      if(leafMatched.some(p=>p!==el&&p.contains(el))) continue;
      const c=classify(el);
      if(c){ if(c.rule.leaf!==false) leafMatched.push(el); items.push({status:c.status, kit:c.rule.name, ref:c.rule.ref, el:desc(el), got:geo(el), probs:c.probs}); }
      else items.push({status:'unknown', kit:'—', ref:'没对上任何 Kit 规则', el:desc(el), got:geo(el), probs:['老样式 / 清单没登记']});
    }
    const n=s=>items.filter(x=>x.status===s).length;
    const summary={ok:n('ok'), content:n('content'), off:n('off'), unknown:n('unknown'), total:items.length};
    const bad=summary.off+summary.unknown;
    document.title=(bad?'KIT-FAIL-'+bad:'KIT-OK')+' '+location.pathname;
    const out={page:location.pathname, platform:MAC?'mac':'ios', ua:navigator.userAgent, w:innerWidth, h:innerHeight, summary, items};
    window.__kit=out; window.__kitDone=true;
    if(!/[?&]quiet/.test(location.search)){ let box=document.getElementById('kitaudit'); if(!box){ box=document.createElement('pre'); box.id='kitaudit'; box.style.cssText='position:fixed;top:0;left:0;z-index:9999;margin:0;max-height:100dvh;max-width:100vw;overflow:auto;font:11px/1.45 ui-monospace,Menlo,monospace;background:rgba(255,255,255,.94);color:#000;padding:calc(env(safe-area-inset-top) + 6px) 8px 8px;white-space:pre-wrap'; document.body.appendChild(box); }
      box.textContent=`${location.pathname} ${MAC?'Mac':'iPhone'} ${innerWidth}×${innerHeight}  ✅${summary.ok} ⚠${summary.off} ✗${summary.unknown} 内容${summary.content}\n`+items.filter(x=>x.status==='off'||x.status==='unknown').map(x=>`${x.status==='off'?'⚠':'✗'} ${x.el}  ${x.got}\n    ${x.kit}  ${x.probs.join('；')}`).join('\n'); }
    try{ fetch(location.origin+'/accept',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(Object.assign({},out,{page:'kitaudit_'+(location.pathname.replace(/\/index\.html$/,'').replace(/^\/|\/$/g,'')||'index')+'_'+out.platform}))}); }catch(e){}
    console.log('KITAUDIT',JSON.stringify(summary));
    return out;
  }
  // ---------- 先把页面用起来（每页的隐藏组件），再量 ----------
  const S=ms=>new Promise(r=>setTimeout(r,ms));
  async function exercise(){
    const p=location.pathname;
    try{
      if(/\/cost\//.test(p)){ const row=document.querySelector('.mrow[data-id=osaka]'); if(row){ row.click(); await S(2500); } const d=document.querySelector('#card details'); if(d) d.open=true; const jr=document.querySelector('#card .job .jr:not(.static)'); if(jr){ jr.click(); await S(300); }
        const cm=document.getElementById('curMenu'); if(cm&&cm.hidden===true){ cm.hidden=false; } }
      else if(/\/osaka\//.test(p)){ for(let i=0;i<30&&!(window.DATA&&DATA.stations);i++) await S(500); if(window.dropPin&&window.map){ try{ dropPin(map.unproject([innerWidth*0.55, innerHeight*0.4])); await S(1200); }catch(e){} }
        const opt=document.getElementById('optSheet'); const ob=document.querySelector('[aria-controls=optSheet], #optBtn, .bar .btn-glass[data-sf="square.stack.3d.up"]'); if(ob){ ob.click(); await S(600); } }
      else if(/\/japan\//.test(p)){ for(let i=0;i<40&&!(window.map&&map.loaded&&map.loaded()&&map.getLayer('jp-fill')&&map.queryRenderedFeatures({layers:['jp-fill']}).length);i++) await S(500);
        if(window.onMapClick&&window.map){ const pt=map.project([135.5,34.7]); try{ onMapClick({point:pt,lngLat:{lng:135.5,lat:34.7}}); await S(800); }catch(e){} } }
      else if(/\/map\//.test(p)){ for(let i=0;i<40&&!(window.__shell&&window.__globe&&__globe.map.loaded());i++) await S(500);
        __shell.select('osaka-station'); await S(600); if(matchMedia('(min-width:900px) and (pointer:fine)').matches){ __shell.openModes(); await S(600); } }
      else if(/\/quiz\//.test(p)){ const dc=document.getElementById('doneCard'); if(dc){ dc.querySelector('.big').textContent='本轮清零'; const ds=document.getElementById('doneSub'); if(ds) ds.textContent='47 县全部答对'; dc.style.display='flex'; }
        const ea=[...document.querySelectorAll('.bar .seg button')].find(b=>/東亜/.test(b.textContent)); if(ea){ ea.click(); await S(1500); } const tg=document.getElementById('lgToggle'); if(tg){ tg.click(); await S(400); }
        const start=[...document.querySelectorAll('button')].find(b=>/^开始/.test(b.textContent.trim())); if(start){ /* 题目条要开考才出现；不开考，留给 #promptBar 显式量 */ } }
    }catch(e){ console.warn('kitaudit exercise', e); }
  }
  window.KIT_AUDIT=async()=>{ await exercise(); await S(400); return run(); };
  window.addEventListener('load', ()=>setTimeout(()=>{ if(/[&?]noauto/.test(location.search)) return; window.KIT_AUDIT(); }, 2500));
  window.addEventListener('touchend', ()=>{ if(window.__kitDone) setTimeout(run, 400); }, {passive:true});   // 手上再点开什么，再量一次（不重跑 exercise）
})();
