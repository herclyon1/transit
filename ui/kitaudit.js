/* 组件对账（用户 2026-09-15 晚：「做个工具去验收网页上的组件有哪些是官方的，哪些还是原来老的」）。
   页面地址加 ?kitaudit 即加载（再加 &quiet 不画覆盖层，只 POST）。和 accept.js 的区别：accept.js 只量几处关键数字；
   这里把页面上**每一个**看得见的控件和容器都过一遍，逐个对上一个 Kit 组件（数字出自 hig-kit/NUMBERS.md：iOS 27 / macOS 27 UI Kit）：
     ✅ 对上 Kit 且尺寸对          ⚠ 对上了某个 Kit 组件但尺寸/圆角/字号不对（半截）
     ◇ Kit 没有这种组件，清单里登记过规则（KIT-INVENTORY 行号）   ✗ 没对上任何规则 = 老样式 / 漏改
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
  const rule=(o)=>RULES.push(o);
  // — Sheet / 侧栏 —
  rule({name:'Sheet（中/大档）', ref:'iOS 27 Kit › Sheets › iPhone：左右内缩 8、四角 34；大档满宽上角 38', plat:'ios', sel:'.sheet:not(.opt)', leaf:false,
    check:el=>{ const r=rect(el); const p=[]; const large=el.classList.contains('large'); if(large){ if(!near(R(el),38)) p.push(`大档上角 ${num(R(el))}≠38`); if(!near(r.left,0)) p.push(`大档应满宽，左 ${num(r.left)}`); } else { if(!near(R(el),34)) p.push(`圆角 ${num(R(el))}≠34`); if(!near(r.left,8)) p.push(`左内缩 ${num(r.left)}≠8`); } return p; }});
  rule({name:'侧栏 / 面板（Windows › Left Pane 256 / Utility Panel 280，圆角 16，内缩 8）', ref:'macOS 27 Kit › Windows', plat:'mac', sel:'.sheet:not(.opt)', leaf:false,
    check:el=>{ const r=rect(el); const p=[]; if(!anyOf(r.width,[256,280])) p.push(`宽 ${num(r.width)}∉{256,280}`); if(!near(R(el),16)) p.push(`圆角 ${num(R(el))}≠16`); if(!near(r.left,8)) p.push(`左 ${num(r.left)}≠8`); return p; }});
  rule({name:'第二面板（大阪图层）= Popover', ref:'macOS 27 Kit › Popovers：r20、白 70% 模糊 30', plat:'mac', sel:'.sheet.opt', leaf:false, check:el=>near(R(el),20)?[]:[`圆角 ${num(R(el))}≠20`]});
  rule({name:'第二张 Sheet（大阪图层）', ref:'iOS 27 Kit › Sheets', plat:'ios', sel:'.sheet.opt', leaf:false, check:el=>near(R(el),34)||near(R(el),38)?[]:[`圆角 ${num(R(el))}∉{34,38}`]});
  rule({name:'抓手 60×4', ref:'iOS 27 Kit › Toolbars › Top - Sheet', plat:'ios', sel:'.sheet .grab i', check:el=>{ const r=rect(el); return near(r.width,60)&&near(r.height,4)?[]:[`${num(r.width)}×${num(r.height)}≠60×4`]; }});
  rule({name:'抓手（桌面不显示）', ref:'Kit 无', plat:'mac', sel:'.sheet .grab', declared:'A5', check:()=>[]});
  rule({name:'抓手块 15（抓手 60×4 @5）', ref:'iOS 27 Kit › Toolbars › Top - Sheet', plat:'ios', sel:'.sheet .grab', leaf:false, check:el=>{ const h=rect(el).height; return near(h,15)?[]:[`抓手块 ${num(h)}≠15`]; }});
  rule({name:'地点面板（Utility Panel 280，贴侧栏右 8）', ref:'macOS 27 Kit › Windows › Utility Panel', plat:'mac', sel:'.sheet.split #card', leaf:false,
    check:el=>{ const r=rect(el); const p=[]; if(!near(r.width,280)) p.push(`宽 ${num(r.width)}≠280`); if(!near(R(el),16)) p.push(`圆角 ${num(R(el))}≠16`); return p; }});
  rule({name:'面板红绿灯（Stoplights 44×10：三个 10 圆 @0/17/34，关不了的灰 15%）', ref:'macOS 27 Kit › Titlebars and Toolbars › Utility Panel › Stoplights', plat:'mac', sel:'.sheet .head .btn-glass',
    check:el=>{ const b=cs(el,'::before'); const w=px(b.width); const p=[]; if(!near(w,10)) p.push(`圆点 ${num(w)}≠10`); const after=cs(el,'::after'); if(!(px(after.width)>0)) p.push('只有一个红点：Kit 组件是三个（关/最小化/缩放，不可用的灰 15%）'); return p; }});
  rule({name:'Sheet 头（Top - Sheet 70 高）', ref:'iOS 27 Kit › Toolbars › Top - Sheet', plat:'ios', sel:'.sheet .head', leaf:false, check:el=>{ const h=rect(el).height; return el.querySelector('.search')?[]:(near(h,54)||near(h,60)?[]:[`头高 ${num(h)}（抓手块外应 1+44+10=55）`]); }});
  rule({name:'侧栏头 / 面板标题栏 24', ref:'macOS 27 Kit › Utility Panel titlebar 24 / Window title', plat:'mac', sel:'.sheet .head', leaf:false, check:el=>{ const h=rect(el).height; return el.closest('.sheet.split #card')?(near(h,24)?[]:[`标题栏 ${num(h)}≠24`]):[]; }});
  rule({name:'建议卡里的 × 和链接（清单 A10）', ref:'清单 A10', plat:'both', sel:'.sugg .x, .sugg .a, .sugg button, .sugg a', declared:'A10', check:()=>[]});
  rule({name:'动作行容器（清单 A12）', ref:'清单 A12', plat:'both', sel:'.actions', leaf:false, declared:'A12', check:el=>{ const r=rect(el); return el.scrollWidth<=r.width+0.5?[]:[`内容 ${el.scrollWidth} 宽超出 ${num(r.width)}（按钮被裁）`]; }});
  rule({name:'Sheet 头圆钮 44', ref:'iOS 27 Kit › Toolbars › Top - Sheet：44 圆 @(16,16)', plat:'ios', sel:'.sheet .head .btn-glass', check:el=>{ const r=rect(el); return near(r.width,44)&&near(r.height,44)?[]:[`${num(r.width)}×${num(r.height)}≠44`]; }});
  rule({name:'Sheet 头标题 Semibold 15/20', ref:'iOS 27 Kit › Toolbars › Top - Sheet › Title 2 Line', plat:'ios', sel:'.sheet .head .t-title2', check:el=>{ const f=font(el); return near(f.size,15,.3)&&near(f.lh,20,.3)&&f.w>=600?[]:[`${num(f.size)}/${num(f.lh)} w${f.w}`]; }});
  rule({name:'Sheet 头副标题 Medium 12/16', ref:'同上', plat:'ios', sel:'.sheet .head .t-sub', check:el=>{ const f=font(el); return near(f.size,12,.3)&&f.w>=500?[]:[`${num(f.size)}/${num(f.lh)} w${f.w}`]; }});
  rule({name:'窗口标题 Bold 15（带侧栏）/ 面板标题 Medium 11', ref:'macOS 27 Kit › Titlebars and Toolbars › Window › Title / Utility Panel › Title', plat:'mac', sel:'.sheet .head .t-title2', check:el=>{ const f=font(el); const inPanel=!!el.closest('.sheet.split #card'); return inPanel?(near(f.size,11,.3)?[]:[`${num(f.size)}≠11`]):(near(f.size,15,.3)&&f.w>=700?[]:[`${num(f.size)} w${f.w}≠15 Bold`]); }});
  rule({name:'侧栏副标题 Medium 11', ref:'macOS 27 Kit › Window › Title › subtitle', plat:'mac', sel:'.sheet .head .t-sub', check:el=>{ const f=font(el); return near(f.size,11,.3)?[]:[`${num(f.size)}≠11`]; }});
  rule({name:'搜索胶囊 44', ref:'iOS 27 Kit › Search 44 r1000', plat:'ios', sel:'.search', check:el=>{ const r=rect(el); return near(r.height,44)&&isCapsule(el,r)?[]:[`高 ${num(r.height)}≠44 或不是胶囊`]; }});
  rule({name:'搜索框 24 / 36 胶囊', ref:'macOS 27 Kit › Search Fields / Toolbar search', plat:'mac', sel:'.search', check:el=>{ const r=rect(el); return anyOf(r.height,[24,36])&&isCapsule(el,r)?[]:[`高 ${num(r.height)}∉{24,36} 或不是胶囊`]; }});
  // — 工具条 —
  rule({name:'工具条圆钮 44（分段条里 48）', ref:'iOS 27 Kit › Toolbars › Buttons 44pt / 48pt', plat:'ios', sel:'.bar .btn-glass, .map-ctl .btn-glass',
    check:el=>{ const r=rect(el); const want=el.closest('.bar')&&el.closest('.bar').querySelector('.seg')?48:44; return near(r.height,want)&&r.width>=want-0.5&&isCapsule(el,r)?[]:[`${num(r.width)}×${num(r.height)}≠${want} 胶囊`]; }});
  rule({name:'工具条玻璃钮 36 胶囊', ref:'macOS 27 Kit › Titlebars and Toolbars › XL 36', plat:'mac', sel:'.bar .btn-glass, .map-ctl .btn-glass', check:el=>{ const r=rect(el); return near(r.height,36)&&isCapsule(el,r)?[]:[`${num(r.width)}×${num(r.height)}≠36 胶囊`]; }});
  rule({name:'工具条分段 Large 48（段 44）/ Small 32（段 28）', ref:'iOS 27 Kit › Segmented Controls', plat:'ios', sel:'.bar .seg', leaf:false,
    check:el=>{ const r=rect(el); const b=el.querySelector('button'); const p=[]; if(!anyOf(r.height,[32,48])) p.push(`高 ${num(r.height)}∉{32,48}`); if(b){ const bh=rect(b).height; if(!anyOf(bh,[28,44])) p.push(`段 ${num(bh)}∉{28,44}`); } return p; }});
  rule({name:'工具条分段 XL 36（段 28，分隔 3×22）', ref:'macOS 27 Kit › Titlebars and Toolbars › Segmented Control', plat:'mac', sel:'.bar .seg', leaf:false,
    check:el=>{ const r=rect(el); const b=el.querySelector('button'); const p=[]; if(!near(r.height,36)) p.push(`高 ${num(r.height)}≠36`); if(b&&!near(rect(b).height,28)) p.push(`段 ${num(rect(b).height)}≠28`); return p; }});
  rule({name:'行内分段 Small 32（段 28）', ref:'iOS 27 Kit › Segmented Controls › Small', plat:'ios', sel:'.seg', leaf:false, check:el=>{ const r=rect(el); return near(r.height,32)?[]:[`高 ${num(r.height)}≠32`]; }});
  rule({name:'行内分段 Regular 24 r6', ref:'macOS 27 Kit › Segmented Controls › Regular', plat:'mac', sel:'.seg', leaf:false, check:el=>{ const r=rect(el); return near(r.height,24)&&near(R(el),6)?[]:[`${num(r.height)} r${num(R(el))}≠24 r6`]; }});
  rule({name:'分段里的段', ref:'随分段控件', plat:'both', sel:'.seg button', check:()=>[]});
  rule({name:'列表行里的图标 / 右侧值（随行：Kit 行图标 24 / iOS 34 圆）', ref:'随列表行（清单 A9/B1）', plat:'both', sel:'.mrow .ico, .mrow .val, .mrow .flag, .ico', check:()=>[]});
  rule({name:'菜单（Menus：r12、行 24、Medium 13）', ref:'macOS 27 Kit › Menus', plat:'mac', sel:'.menu, [role=menu]', leaf:false, check:el=>{ const p=[]; if(!near(R(el),12)) p.push(`圆角 ${num(R(el))}≠12`); const it=el.querySelector('button,[role^=menuitem]'); if(it&&!near(rect(it).height,24)) p.push(`行 ${num(rect(it).height)}≠24`); return p; }});
  rule({name:'菜单（UIMenu：248 宽、r26、行 42）', ref:'NUMBERS：Safari 长按菜单实测（Kit 无 iPhone 菜单尺寸）', plat:'ios', sel:'.menu, [role=menu]', leaf:false, declared:'A3', check:el=>{ const it=el.querySelector('button,[role^=menuitem]'); return it&&!near(rect(it).height,42)?[`行 ${num(rect(it).height)}≠42`]:[]; }});
  rule({name:'菜单项', ref:'随菜单', plat:'both', sel:'.menu button, [role=menuitemradio], [role=menuitem]', check:()=>[]});
  // — 列表 —
  rule({name:'列表段头 Nested 42：Semibold 17 secondaryLabel', ref:'iOS 27 Kit › Lists › Header › Nested', plat:'ios', sel:'.mh', check:el=>{ const f=font(el); const p=[]; if(!near(f.size,17,.3)||f.w<600) p.push(`${num(f.size)} w${f.w}≠17 Semibold`); if(!/rgba\(60, 60, 67, 0\.6\)/.test(f.color)) p.push('颜色不是 secondaryLabel'); return p; }});
  rule({name:'侧栏段头 Bold 11', ref:'macOS 27 Kit › Sidebars › Headers', plat:'mac', sel:'.mh', check:el=>{ const f=font(el); return near(f.size,11,.3)&&f.w>=700?[]:[`${num(f.size)} w${f.w}≠11 Bold`]; }});
  rule({name:'首页行（设置式列表行 52 / 68）', ref:'iOS 27 Kit › Lists › Rows（清单 F2–F4）', plat:'ios', sel:'.row', check:el=>{ const h=rect(el).height; return anyOf(h,[52,68],1.5)?[]:[`行高 ${num(h)}∉{52,68}`]; }});
  rule({name:'首页行 = 侧栏行 Large 40', ref:'macOS 27 Kit › Sidebars › Rows › Large（清单 F2–F4）', plat:'mac', sel:'.row', check:el=>{ const h=rect(el).height; return near(h,40)?[]:[`行高 ${num(h)}≠40`]; }});
  rule({name:'首页说明文字（Subheadline）', ref:'Kit Text styles', plat:'both', sel:'.sub, .t-sub, .mnote, .foot, .hint', check:()=>[]});
  rule({name:'列表行 Large 68 / Default 52', ref:'iOS 27 Kit › Lists › Rows', plat:'ios', sel:'.mrow', check:el=>{ const h=rect(el).height; return anyOf(h,[52,68])?[]:[`行高 ${num(h)}∉{52,68}`]; }});
  rule({name:'侧栏行 Large 40 / Medium 32 / Small 24', ref:'macOS 27 Kit › Sidebars › Rows', plat:'mac', sel:'.mrow', check:el=>{ const h=rect(el).height; return anyOf(h,[24,32,40])?[]:[`行高 ${num(h)}∉{24,32,40}`]; }});
  rule({name:'可展开行（岗位/来源）= 列表行 Large 68 + 展开指示', ref:'iOS 27 Kit › Lists › Rows › Large（清单 A14）', plat:'ios', sel:'.job .jr', check:el=>{ const h=rect(el).height; return h>=52-0.5&&h<=68.5?[]:[`行高 ${num(h)}∉[52,68]`]; }});
  rule({name:'可展开行 = 侧栏行 Large 40 + Disclosure', ref:'macOS 27 Kit › Sidebars › Rows › Large（清单 A14）', plat:'mac', sel:'.job .jr', check:el=>{ const h=rect(el).height; return h<=40.5?[]:[`行高 ${num(h)}>40（内容折行）`]; }});
  rule({name:'设置行 `.r`（Kit 无独立组件：随分组卡片行 47 / Mac 32）', ref:'清单 A13', plat:'both', sel:'.r', declared:'A13', check:el=>{ const h=rect(el).height; if(MAC) return h>=32-0.5?[]:[`行 ${num(h)}<32`]; return h>=44-0.5?[]:[`行 ${num(h)}<44（触控最小 44）`]; }});
  rule({name:'分组卡片 .mcard（Kit 无 → 地图 App r20 / Mac Group Box r12 黑 3%）', ref:'清单 A13', plat:'both', sel:'.mcard, .stat, .sugg, .group', leaf:false, declared:'A13/A11/A10', check:el=>{ const r=R(el); if(MAC) return near(r,12)?[]:[`圆角 ${num(r)}≠12（Group Box）`]; return anyOf(r,[16,20,26])?[]:[`圆角 ${num(r)}∉{16,20,26}`]; }});
  rule({name:'次级折叠 details/summary（HIG Disclosure；Mac Disclosure 24 r6）', ref:'清单 A15', plat:'both', sel:'details, summary', declared:'A15', check:()=>[]});
  rule({name:'四档表（Kit 无表格 → HIG Tables，字号 13）', ref:'清单 A16', plat:'both', sel:'table', leaf:false, declared:'A16', check:el=>{ const f=font(el); return near(f.size,13,.6)||near(f.size,MAC?13:13,.6)?[]:[`字号 ${num(f.size)}≠13`]; }});
  // — 按钮 —
  rule({name:'动作行按钮（清单 A12：等宽 50 高 / Mac 分段 24）', ref:'清单 A12', plat:'both', sel:'.actions .btn', declared:'A12', check:el=>{ const h=rect(el).height; return MAC?(near(h,24)?[]:[`高 ${num(h)}≠24`]):(near(h,50)?[]:[`高 ${num(h)}≠50`]); }});
  rule({name:'文字按钮 Small 28 / Medium 34 / Large 50（提示框里 48）', ref:'iOS 27 Kit › Buttons', plat:'ios', sel:'.btn', check:el=>{ const r=rect(el); return anyOf(r.height,[28,34,48,50])&&isCapsule(el,r)?[]:[`高 ${num(r.height)}∉{28,34,50} 或不是胶囊`]; }});
  rule({name:'按钮 Regular 24 r6 / Large 28 胶囊 / XL 36 胶囊', ref:'macOS 27 Kit › Push buttons', plat:'mac', sel:'.btn', check:el=>{ const r=rect(el); if(near(r.height,24)) return near(R(el),6)?[]:[`24 高但圆角 ${num(R(el))}≠6`]; return anyOf(r.height,[28,36])&&isCapsule(el,r)?[]:[`高 ${num(r.height)}∉{24,28,36}`]; }});
  rule({name:'筛选胶囊 .chips（Kit Button S 28；现按地图 App 实测 32）', ref:'清单 A20', plat:'both', sel:'.chips button', declared:'A20', check:el=>{ const h=rect(el).height; return MAC?(near(h,28)?[]:[`高 ${num(h)}≠28`]):(anyOf(h,[28,32])?[]:[`高 ${num(h)}∉{28,32}`]); }});
  rule({name:'图例小钮 = .btn.s Bordered', ref:'清单 E2', plat:'both', sel:'.lg-jmp, .lg-toggle', check:el=>{ const h=rect(el).height; return MAC?(near(h,24)?[]:[`高 ${num(h)}≠24`]):(near(h,28)?[]:[`高 ${num(h)}≠28`]); }});
  // — 开关 / 滑块 / 勾选 / 输入 —
  rule({name:'开关 63×28', ref:'iOS 27 Kit › Toggles', plat:'ios', sel:'.sw', check:el=>{ const r=rect(el); return near(r.width,63)&&near(r.height,28)?[]:[`${num(r.width)}×${num(r.height)}≠63×28`]; }});
  rule({name:'开关 Regular 54×24', ref:'macOS 27 Kit › Toggles - Switches', plat:'mac', sel:'.sw', check:el=>{ const r=rect(el); return near(r.width,54)&&near(r.height,24)?[]:[`${num(r.width)}×${num(r.height)}≠54×24`]; }});
  rule({name:'开关里的原生 input（隐形）', ref:'随开关', plat:'both', sel:'.sw input', check:()=>[]});
  rule({name:'滑块（轨 4 r2、钮 28）', ref:'iOS 27 Kit › Sliders', plat:'ios', sel:'input[type=range]', check:el=>{ const h=px(cs(el,'::-webkit-slider-runnable-track').height); return near(h,4)?[]:[`轨 ${num(h)}≠4`]; }});
  rule({name:'滑块 Regular（控件 24、轨 6、钮 20×16）', ref:'macOS 27 Kit › Sliders', plat:'mac', sel:'input[type=range]', check:el=>{ const h=px(cs(el,'::-webkit-slider-runnable-track').height); const t=px(cs(el,'::-webkit-slider-thumb').width); const p=[]; if(!near(h,6)) p.push(`轨 ${num(h)}≠6`); if(!near(t,20)) p.push(`钮 ${num(t)}≠20`); return p; }});
  rule({name:'多选圆 22（iOS 无 checkbox → Lists › Rows › Editing）', ref:'iOS 27 Kit › Lists › Rows › Editing（清单 E6）', plat:'ios', sel:'input[type=checkbox]:not(.sw input)', check:el=>{ const r=rect(el); const c=cs(el); if(c.appearance!=='none'&&c.webkitAppearance!=='none') return ['原生 checkbox（不是 Kit 组件）']; return near(r.width,22)&&near(r.height,22)&&isCapsule(el,r)?[]:[`${num(r.width)}×${num(r.height)}≠22 圆`]; }});
  rule({name:'勾选框 Regular 16 r5.5', ref:'macOS 27 Kit › Toggles - Checkboxes（清单 E6）', plat:'mac', sel:'input[type=checkbox]:not(.sw input)', check:el=>{ const r=rect(el); const c=cs(el); if(c.appearance!=='none'&&c.webkitAppearance!=='none') return ['原生 checkbox（不是 Kit 组件）']; return near(r.width,16)&&near(r.height,16)&&near(R(el),5.5,.3)?[]:[`${num(r.width)}×${num(r.height)} r${num(R(el))}≠16 r5.5`]; }});
  rule({name:'原生 <select>（Kit：iOS 用 Menu/Picker，Mac 用 Pop-up Button 24 r6）', ref:'macOS 27 Kit › Pop-up Buttons；iOS 27 Kit › Menus', plat:'both', sel:'select', check:el=>{ const c=cs(el); return (c.appearance==='none'||c.webkitAppearance==='none')&&(MAC?near(rect(el).height,24):true)?[]:['原生 select 外观（不是 Kit 组件）']; }});
  rule({name:'文本输入（Mac Text Field 24 r6；iOS 随搜索胶囊）', ref:'macOS 27 Kit › Text Fields', plat:'both', sel:'input[type=text], input[type=search], input:not([type]), textarea', check:el=>{ if(el.closest('.search')) return []; const r=rect(el); return MAC?(near(r.height,24)&&near(R(el),6)?[]:[`${num(r.height)} r${num(R(el))}≠24 r6`]):(near(r.height,44)?[]:[`高 ${num(r.height)}≠44`]); }});
  // — 浮层 —
  rule({name:'提示框 Alert 300 r34（按钮 48）', ref:'iOS 27 Kit › Alerts', plat:'ios', sel:'#doneCard .box, .alert', leaf:false, check:el=>{ const r=rect(el); const p=[]; if(!near(r.width,300)) p.push(`宽 ${num(r.width)}≠300`); if(!near(R(el),34)) p.push(`圆角 ${num(R(el))}≠34`); return p; }});
  rule({name:'提示框 Alert 260 r26（按钮 28）', ref:'macOS 27 Kit › Alerts', plat:'mac', sel:'#doneCard .box, .alert', leaf:false, check:el=>{ const r=rect(el); const p=[]; if(!near(r.width,260)) p.push(`宽 ${num(r.width)}≠260`); if(!near(R(el),26)) p.push(`圆角 ${num(R(el))}≠26`); return p; }});
  rule({name:'浮层 = Popover r20', ref:'macOS 27 Kit › Popovers（清单 C2/E1/E4）', plat:'mac', sel:'#promptBar, #info, .hpop .maplibregl-popup-content', leaf:false, check:el=>near(R(el),20)?[]:[`圆角 ${num(R(el))}≠20`]});
  rule({name:'钉子弹出 = Sheet 材质 r34（iOS 无 Popover）', ref:'清单 C2', plat:'ios', sel:'.hpop .maplibregl-popup-content', leaf:false, check:el=>near(R(el),34)?[]:[`圆角 ${num(R(el))}≠34`]});
  rule({name:'弹出关闭钮 28 圆 / Mac 24', ref:'清单 C2', plat:'both', sel:'.maplibregl-popup-close-button', check:el=>{ const r=rect(el); return near(r.width,MAC?24:28)?[]:[`${num(r.width)}≠${MAC?24:28}`]; }});
  rule({name:'题目条（Kit 无 → HIG 顶部浮层，玻璃）', ref:'清单 E1', plat:'ios', sel:'#promptBar', leaf:false, declared:'E1', check:()=>[]});
  rule({name:'信息浮层（Kit 无 → 玻璃卡）', ref:'清单 E4', plat:'ios', sel:'#info', leaf:false, declared:'E4', check:()=>[]});
  rule({name:'图例浮层（Kit 无图例）', ref:'清单 E2', plat:'both', sel:'#legend, #lg', leaf:false, declared:'E2', check:()=>[]});
  rule({name:'提示框遮罩', ref:'随 Alert', plat:'both', sel:'#doneCard', leaf:false, check:()=>[]});
  rule({name:'学習 详情内联卡（清单 D3 随 A13：Mac Group Box r12 黑 3% / 手机 r20）', ref:'清单 D3/A13', plat:'both', sel:'#card.on, #cardSect', leaf:false, declared:'D3', check:el=>{ if(!el.matches('#card.on')) return []; const r=R(el); return MAC?(near(r,12)?[]:[`圆角 ${num(r)}≠12（不是 Group Box）`]):(anyOf(r,[16,20,26])?[]:[`圆角 ${num(r)}∉{16,20,26}`]); }});
  rule({name:'提示框图标/文字块', ref:'随 Alert', plat:'both', sel:'#doneCard .ico, #doneCard .txt', check:()=>[]});
  // — 地图控件与杂项（Kit 无，清单登记过） —
  rule({name:'MapLibre ± 控件（Kit 无 ± → Button Group 36 胶囊 / iOS 无）', ref:'清单 A24', plat:'both', sel:'.maplibregl-ctrl-group, .maplibregl-ctrl-group button', declared:'A24', check:()=>[]});
  rule({name:'底图署名 ⓘ（清单 A25：Mac 24）', ref:'清单 A25', plat:'both', sel:'.maplibregl-ctrl-attrib, .maplibregl-ctrl-attrib-button, .maplibregl-ctrl-attrib a', declared:'A25', check:()=>[]});
  rule({name:'置信度胶囊 / 小圆点（Kit 无，24 高 tint 12%）', ref:'清单 A17', plat:'both', sel:'.tag, .chip', declared:'A17', check:el=>{ if(el.classList.contains('chip')) return []; const h=rect(el).height; return MAC?[]:(near(h,24)?[]:[`高 ${num(h)}≠24`]); }});
  rule({name:'枢纽标记 / 标签 / 图例色块（地图 App 实测）', ref:'清单 C3', plat:'both', sel:'.hubmk, .hublbl, .tsw, #legend i, .lg-head b, .pin', declared:'C3', check:()=>[]});
  rule({name:'缩略图块 .tiles（Kit 无 → 地图 App 地图模式块）', ref:'清单 A21', plat:'both', sel:'.tiles, .tiles button, .tiles .tile', declared:'A21', check:()=>[]});
  rule({name:'Claw\'d 吉祥物', ref:'IDEAS.md #65', plat:'both', sel:'.clawd, #clawd', declared:'#65', check:()=>[]});
  rule({name:'来源列表行（清单 B2：平台 · 标题 · 日期）', ref:'清单 B2/A14', plat:'both', sel:'.links a', declared:'B2', check:()=>[]});
  rule({name:'表格里的数字链接（黑字，点开来源；清单 A16）', ref:'清单 A16', plat:'both', sel:'table a', declared:'A16', check:()=>[]});
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
      return {rule:ru, status: probs.length?'off':(ru.declared?'declared':'ok'), probs}; }
    return null;
  }
  function run(){
    const items=[]; const leafMatched=[];
    for(const el of candidates()){
      // 已识别叶子控件里的子元素（按钮里的图标/文字）不再单算
      if(leafMatched.some(p=>p!==el&&p.contains(el))) continue;
      const c=classify(el);
      if(c){ if(c.rule.leaf!==false) leafMatched.push(el); items.push({status:c.status, kit:c.rule.name, ref:c.rule.ref+(c.rule.declared?'（清单 '+c.rule.declared+'）':''), el:desc(el), got:geo(el), probs:c.probs}); }
      else items.push({status:'unknown', kit:'—', ref:'没对上任何 Kit 规则', el:desc(el), got:geo(el), probs:['老样式 / 清单没登记']});
    }
    const n=s=>items.filter(x=>x.status===s).length;
    const summary={ok:n('ok'), declared:n('declared'), off:n('off'), unknown:n('unknown'), total:items.length};
    const bad=summary.off+summary.unknown;
    document.title=(bad?'KIT-FAIL-'+bad:'KIT-OK')+' '+location.pathname;
    const out={page:location.pathname, platform:MAC?'mac':'ios', ua:navigator.userAgent, w:innerWidth, h:innerHeight, summary, items};
    window.__kit=out; window.__kitDone=true;
    if(!/[?&]quiet/.test(location.search)){ let box=document.getElementById('kitaudit'); if(!box){ box=document.createElement('pre'); box.id='kitaudit'; box.style.cssText='position:fixed;top:0;left:0;z-index:9999;margin:0;max-height:100dvh;max-width:100vw;overflow:auto;font:11px/1.45 ui-monospace,Menlo,monospace;background:rgba(255,255,255,.94);color:#000;padding:calc(env(safe-area-inset-top) + 6px) 8px 8px;white-space:pre-wrap'; document.body.appendChild(box); }
      box.textContent=`${location.pathname} ${MAC?'Mac':'iPhone'} ${innerWidth}×${innerHeight}  ✅${summary.ok} ◇${summary.declared} ⚠${summary.off} ✗${summary.unknown}\n`+items.filter(x=>x.status==='off'||x.status==='unknown').map(x=>`${x.status==='off'?'⚠':'✗'} ${x.el}  ${x.got}\n    ${x.kit}  ${x.probs.join('；')}`).join('\n'); }
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
      else if(/\/quiz\//.test(p)){ const dc=document.getElementById('doneCard'); if(dc){ dc.querySelector('.big').textContent='本轮清零'; const ds=document.getElementById('doneSub'); if(ds) ds.textContent='47 县全部答对'; dc.style.display='flex'; }
        const ea=[...document.querySelectorAll('.bar .seg button')].find(b=>/東亜/.test(b.textContent)); if(ea){ ea.click(); await S(1500); } const tg=document.getElementById('lgToggle'); if(tg){ tg.click(); await S(400); }
        const start=[...document.querySelectorAll('button')].find(b=>/^开始/.test(b.textContent.trim())); if(start){ /* 题目条要开考才出现；不开考，留给 #promptBar 显式量 */ } }
    }catch(e){ console.warn('kitaudit exercise', e); }
  }
  window.KIT_AUDIT=async()=>{ await exercise(); await S(400); return run(); };
  window.addEventListener('load', ()=>setTimeout(()=>{ if(/[&?]noauto/.test(location.search)) return; window.KIT_AUDIT(); }, 2500));
  window.addEventListener('touchend', ()=>{ if(window.__kitDone) setTimeout(run, 400); }, {passive:true});   // 手上再点开什么，再量一次（不重跑 exercise）
})();
