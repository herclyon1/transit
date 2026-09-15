# 控件清单 · 五页 × (iOS 27 Kit / macOS 27 Kit)

2026-09-15 用户令（经 maa 会话）：「按 Kit 重做」= 页面上每一个可见控件都对上 Kit 组件，不是挑几个数字换。先出清单再动手；
改完的行标「已按 Kit + commit」；全部改完才许说「按 Kit 重做完成」。推送前 Mac 1440 / 手机 375 每个标签、每个可展开项点开截图自己看，探针只是底线。

状态：**✅ 已按 Kit（commit）** · **⛔ 未按 Kit → 计划** · **◇ Kit 没有此组件 → 按 HIG/系统 App 实测，写明规则**。
数字出处：iOS = Figma 「Apple iOS and iPadOS 27 UI Kit」节点 id（NUMBERS.md 上半），macOS = Sketch 「Apple macOS 27 UI Kit」页›artboard（NUMBERS.md「macOS 27 UI Kit」）。
分工：cost/index.html、ui/hig.css、ui/shell.js、本清单 = 本会话；osaka/japan/quiz 三个文件 = maa 会话（interaction 分支），它们页内的项本会话只在 hig.css 里改，页内改动等分支合并。

## A. 共用（cost / osaka / japan / quiz）

| # | 控件 | 手机 = iOS 27 Kit | Mac = macOS 27 Kit | 数字出处 | 状态 / 计划 |
|---|---|---|---|---|---|
| A1 | 顶部工具条玻璃圆钮 `.bar .btn-glass`（返回 / 图层 / 货币） | Toolbar - Top - iPhone `1:54472`：44 圆、距边 16/20 | Titlebars and Toolbars › XL › Buttons：36×36 胶囊、内 28、间 8、距边 8 | NUMBERS 两节 | 尺寸 ✅（3820172）；材质 ✅（本批）：Kit 四层填充（黑 25% + 白 25% + #444 60% plus-lighter + #f8f8f8 20% luminosity）合成 ≈ 白 50%，背景模糊 6、饱和 2、0.5 边 #dbdbdb、投影 0 8 15 黑 2%——混合模式/折射 CSS 做不了，按合成结果近似，写在 11b 注释 |
| A2 | 工具条分段控件 `.bar .seg`（japan 現代日本/東亜、quiz 模式） | Segmented Control `10460:145`：S 32 / L 50 —— **现用 44 与圆钮同高，Kit 未核**（NUMBERS「Open」） | Titlebars and Toolbars › XL › Segmented Control：36 高、段 32×28、分隔 3×22 | 同上 | 手机 ✅（本批：iOS 27 Sketch Kit › Segmented Controls › Large 48，段 44 内边 2 间 4，标签 13.33；japan/quiz 页内的 `.bar .seg{height:44px}` 被 hig.css `html .bar .seg` 盖掉，maa 合并时删）；Mac ✅（3820172 + 1277f1e 分隔线/玻璃） |
| A3 | 货币下拉菜单 `.menu`（cost） | Menu（UIMenu）：248 宽、r26、行 42、内边 5 —— Safari 长按菜单实测 | Menus › Light › Regular：容器 r12、内缩 16、行 24 Medium 13、悬停底 r8 外扩 11、分隔 11 高 | NUMBERS | 手机 ◇（Kit 无 UIMenu 组件，按系统实测）；Mac ✅（本批：r12、内边 5/12、行 24 Medium 13、文字起点 31、悬停 tint 白字 r8、无行分隔、Popover 材质） |
| A4 | Sheet（手机）/ 侧栏（Mac）`.sheet` | iOS 27 Sketch Kit › Sheets › iPhone：中档/Inspector 左右底内缩 8、四角 34；大档满宽贴底上角 38（Figma 节点 `10525:1632` 写 38 是旧值） | Windows › Left Pane：256 宽、内边 8、窗口圆角 16、材质 #fafafa 80% + 模糊 100 | NUMBERS | 手机 ✅（本批：四角 34 + 底内缩 8 用 clip-path 随档位过渡，大档 38；sheet.js）；Mac ✅（3820172） |
| A5 | 抓手 `.grab` | Kit Toolbars › Top - Sheet：抓手 60×4 距顶 5（地图 App 实测 58 作废） | Kit 无（桌面不拖） | NUMBERS | 手机 ✅（本批 60）；Mac 隐藏 ✅ |
| A6 | Sheet 头搜索胶囊 `.head .search`（cost 列表） | Search `5720:33677`：44、r1000、11/10 内边 | Titlebars and Toolbars › XL › Search：159×36；Search Fields › Regular：白底 + 1px 黑 5% 描边、图标槽 @8 | NUMBERS | ✅（3820172） |
| A7 | 地点卡片头 `#card .head`（标题 / 副标题 / 关闭）；侧栏头 `.sheet .head .tt`（osaka/japan/quiz 的标题） | iOS 27 Sketch Kit › Toolbars › iPhone › Top - Sheet › Title 2 Line：44 圆钮 @(16,16)，标题块 @y19 = Semibold 15 + Medium 12 居中（地图 App 实测 15/15 + 22 粗作废） | Windows › Utility Panel › Titlebar：24 高、红灯 10⌀ #ff5c60 @(8,8)、标题 Medium 11 居中 | NUMBERS | 手机 ✅（本批：16/16、Semibold 15 + Medium 12、头高 70）；Mac ✅（05a19ca 卡片头；1277f1e 侧栏头 Bold 15 + Medium 11） |
| A8 | 列表段头 `.mh` | iOS 27 Sketch Kit › Lists › Header › Nested 42：Semibold 17 secondaryLabel @(16,10)，下 10；组间 28 = 设置 App 实测（Kit 头组件不含组间距） | Sidebars › Headers › Medium：18 高、Bold 11、距边 14 | NUMBERS | 手机 ✅（本批：`.mh` 改 secondaryLabel、下 10；上 28 记为 App 布局）；Mac ✅（3820172） |
| A9 | 列表行 `.mlist .mrow`（cost 城市行、osaka 图例行） | iOS 27 Sketch Kit › Lists › Rows › Large 68：Title 17/22 @14 + Subtitle 15/18 @36；圆图标 34 = 地图 App（Kit 前导是方形缩略图，圆图标是 App 布局） | Sidebars › Items › Large：40 高、图标 24 @14、标题 Regular 13、选中底 r8 黑 11% | NUMBERS | 手机 ✅（本批：行 68、副题 15/18，`.mrow`；`.job .jr` 同）；Mac ✅（3820172） |
| A10 | 建议卡 `.sugg`（cost 首屏介绍卡） | Kit 无 → 地图 App「附近的公共交通」建议卡实测：白 55% r16、圆图标 36 | Kit 无建议卡 → Group Boxes：r12 黑 3%；图标 24 | NUMBERS | 手机 ◇；Mac ✅（本批：Group Box r12 黑 3%、图标 24、Body 13 / Subheadline 11） |
| A11 | 统计卡 `.stats .stat` | Kit 无 → 健身 › 摘要 实测：两列 195、r20、内边 16 | Group Boxes：r12 黑 3%；数字 Title 1 22 | NUMBERS | 手机 ◇；Mac ✅（3820172） |
| A12 | 动作行 `.actions .btn`（换算成工时 / 来源） | Kit 无 → 地图 App 地点卡片动作行实测：等宽 50 高 | Segmented Controls › Regular：24 r6、轨道黑 8%、Medium 13 | NUMBERS | 手机 ◇；Mac ✅（05a19ca）；「可达性图」没做不显示 ✅ |
| A13 | 卡片分组 `.mcard` + 行 `.r` | Kit 无 → 地图 App 地点卡片实测：r20 半透明、行 47 | Group Boxes r12 黑 3%；行 = Sidebars › Items › Medium 32 | NUMBERS | 手机 ◇；Mac ✅（3820172） |
| A14 | 可展开行 `.job .jr` + 展开区 `.det`（岗位 / 来源行） | 行同 A9（69）；展开 = 点行 | 行 = Sidebars › Large 40；展开指示 = **Disclosure Controls**（Kit 有 120 个 artboard，未解） | NUMBERS | 手机 ◇；Mac ✅（05a19ca 行 + 本批展开指示 = Kit Disclosure Buttons › Small 20 r5 黑 8%、chevron down/up，按下 16%；NUMBERS 已记） |
| A15 | 次级列表 `details.sublist`「看 8 家店」 | Kit 无 → HIG Disclosure | Disclosure Controls | — | Mac ✅（本批，summary 右端同 A14 的 Small 钮，chevron right/down）；手机 ◇ |
| A16 | 四档表 `table.tiers` | Kit 无表格控件 → HIG Tables；字号 Footnote 13 | Kit 无 Table View 页 → 字号 Body 13 / Subheadline 11，分隔 separator | — | ◇（字号已随根字号） |
| A17 | 置信度胶囊 `.tag` / 小圆点 `.chip` | Kit 无 → 24 高 tint 12%（未量，NUMBERS 记「unmeasured」） | Kit 无 | NUMBERS | ◇（保留，标未量） |
| A18 | 开关 `.sw` | Toggles `5433:19059` 63×28（设置 App 同） | Toggles - Switches › Regular 54×24、圆钮 32×20、按下 50×31 | NUMBERS | ✅ 两端（3820172） |
| A19 | 滑块 `.r.slider`（osaka 阈值 / 步行） | Sliders `7:53847`：轨道 4 r2、圆钮 28 | Sliders 页（836 artboard）**未解** | NUMBERS | 手机 ✅；Mac ✅（本批：Kit Sliders › Regular 控件 24、轨道 6 胶囊黑 10% / #0088ff、圆钮 20×16 白胶囊阴影 0 .5 6 12%，按下 25×20；NUMBERS 已记） |
| A20 | 筛选胶囊 `.chips button`（osaka 枢纽数、quiz 地方跳转） | Kit Button S 28 —— 现按地图 App 筛选胶囊实测 32 | Buttons › Large：28 胶囊、Medium 13、内边 16 | NUMBERS | 手机 ◇（App 实测，DESIGN-HIG 记）；Mac ✅（3820172） |
| A21 | 缩略图块 `.tiles`（japan 底图） | Kit 无 → 地图 App 地图模式块实测 91 | Kit 无 → 三块各 78 塞 280 面板（推算） | NUMBERS | ◇ 两端（Mac 推算已注明） |
| A22 | 行内分段控件 `.mcard .seg`（japan/quiz 题型等） | Segmented S 32 | Segmented Controls › Regular 24 r6 | NUMBERS | ✅ 两端 |
| A23 | 按钮 `.btn.s/.m/.l`（quiz 再来一轮 / 开始 / 不会） | Button - Liquid Glass - Text `5473:21667`：28 / 34 / 50 | Buttons › Regular 24 r6 / Large 28 胶囊 / XL 36 胶囊 | NUMBERS | ✅ 两端（3820172） |
| A24 | MapLibre 缩放 ± 控件（地图右下） | iOS 地图 App 没有 ± 按钮（捏合缩放） | Kit 无 ± → Titlebars and Toolbars › XL › Button Group（36 胶囊内两颗 28） | — | 手机 ✅（shell.js 只在宽屏加 ±，手机本来没有）；Mac ✅（本批：36 胶囊、两颗 28 距 4、分隔 22×3、距右/底 8） |
| A25 | 底图署名 ⓘ（MapLibre attribution 折叠钮） | Kit 无 → 地图 App 右下「Legal」小字 | Titlebars and Toolbars › Medium › Buttons 24 | — | Mac ✅（本批：24 胶囊 Kit 玻璃、展开文字 Footnote 10）；手机 ◇（地图 App 右下 Legal 小字，MapLibre ⓘ 折叠） |
| A26 | 玻璃材质 `.glass`（所有浮层） | Materials（Kit 折射不可复现 → 白 55% + 模糊 22 + 内描边） | Materials › Regular：#ececec 63% 模糊 60 饱和 1.45；侧栏材质已用 Kit | NUMBERS | 手机 ◇（记录近似）；Mac ✅（本批：`.glass` = Kit Regular #ececec 63% 模糊 60 饱和 1.45；工具条按 A1；侧栏/面板按 Kit 侧栏材质；菜单/弹出窗按 Popover 材质） |
| A27 | 文本样式 `.t-*` / 根字号 | Text styles `5418:17464`（17 Body） | document layerTextStyles（13 Body） | NUMBERS | ✅ 两端 |
| A28 | 颜色 token | Colors `5707:28659` | Kit Colors 页为空 → 沿用 iOS 色板 + Kit 各控件里读到的填充（黑 8/11/13%、#0088ff、#ff5c60） | NUMBERS | ✅ |

## B. cost/index.html 独有

| # | 控件 | 手机 | Mac | 出处 | 状态 / 计划 |
|---|---|---|---|---|---|
| B1 | 城市行右侧「N 小时/月 + n 条」`.val` | 行同 A9 | 行同 A9：Detail Medium 13 + Subheadline 11 | NUMBERS | 随 A9 |
| B2 | 来源行 `srcRow`（篮子/水电/统计/四档明细） | 同 A14 | 同 A14 | — | Mac 行 ✅（05a19ca）；展开指示随 A14 |
| B3 | 「各档数字怎么来的」折叠 `details.tiers-how` | 同 A15 | 同 A15 | — | 随 A15 |
| B4 | 地图城市点 / 标签 `city-dot/city-lab` | 地图 App 地铁站点实测（5pt 点 + 1pt 白环） | 同 | NUMBERS | ◇；标签在底图 place 层 minzoom 以上不画 ✅（05a19ca） |
| B5 | 页脚「更新 9 月 15 日」`.src` | Footnote 13 | Footnote 10 | — | ✅ |

## C. osaka/index.html 独有（页内改动归 maa；hig.css 部分归本会话）

| # | 控件 | 手机 | Mac | 出处 | 状态 / 计划 |
|---|---|---|---|---|---|
| C1 | 图层选项 Sheet `.sheet.opt`（第二张 Sheet） | Sheet（同 A4） | Kit 无第二侧栏 → **Popovers**：r20、白 70% + 模糊 30、阴影 0 18 46 25%，从工具条按钮弹出 | NUMBERS | 手机 ✅；Mac ✅（本批：`.sheet.opt` = Kit Popover r20 白 70% 模糊 30 阴影 0 18 46 25%、箭头 46×10，距右 8 距顶 52 贴工具条钮；头同面板头 24 + 红灯） |
| C2 | 车站 popup `.hpop`（MapLibre popup r16） | iOS 27 Kit 无 iPhone Popover（只有 iPad）→ HIG：手机用 Sheet 或 r34 卡 | Popovers r20 | NUMBERS | ✅ 两端（maa 分支）：手机 = Sheet 材质（.glass 令牌）+ Inspector r34、关闭钮 28 圆 + SF xmark；Mac = Kit Popovers r20 白 70% 模糊 30 阴影 0 18 46 25% 箭头 46×10、关闭 24；focusAfterOpen:false |
| C3 | 枢纽标记 `.hubmk` / 标签 `.hublbl` | 地图 App 车站图标实测 | 同 | NUMBERS | ◇ |
| C4 | 图例行 `#lg .mrow` | 同 A9（页内 52） | Sidebars › Large 40（页内已加） | — | Mac ✅（3820172）；手机随 A9 |
| C5 | 注释 `.mnote` / `.txt` | Footnote 13 | Subheadline 11 | — | ✅ |

## D. japan/index.html 独有（页内归 maa）

| # | 控件 | 手机 | Mac | 出处 | 状态 / 计划 |
|---|---|---|---|---|---|
| D1 | 图层开关行 `.r + .sw` | 同 A18 | 同 A18 | — | ✅ |
| D2 | 图例色块行 `.sub` | Kit 无 → 地图 App 图例 | Kit 无 | — | ◇ |
| D3 | 详情内联卡（点地图后的「这是哪」） | 同 A13 | 同 A13 | — | 随 A13 |

## E. quiz/index.html 独有（页内归 maa）

| # | 控件 | 手机 | Mac | 出处 | 状态 / 计划 |
|---|---|---|---|---|---|
| E1 | 题目条 `#promptBar`（玻璃卡 + 反馈 + 两颗按钮） | Kit 无 → HIG（顶部浮层） | Kit 无 → Popovers r20 材质 | — | ✅ Mac（maa 分支）：r20 + Popover 材质（白 70% + #bfbfbf 10% + 模糊 30、阴影 0 18 46 25%）；按钮已是 A23 |
| E2 | 图例浮层 `#legend`（lg-head / lg-body / lg-jmp 小按钮） | Kit 无图例；lg-jmp = Button S 28 | Kit 无；lg-jmp = Buttons › Regular 24 r6 | — | ✅ 两端（maa 分支）：lg-jmp/lg-toggle = .btn.s 加 Bordered 底（手机 #767680 12% + tint 字；Mac 黑 8% + Medium 13 黑字）；浮层 Mac 移到侧栏右（left 304）不再压侧栏 |
| E3 | 完成卡 `#doneCard .box`（模态） | iOS 27 Kit › Alerts › Default：300 宽 r34 玻璃、内边 14、按钮 48 胶囊 | macOS Kit › Alerts：260 宽 r26、按钮 Large 28 | NUMBERS（两节都记了） | ✅ 两端（maa 分支）：手机 = Kit Alert 300 宽 r34 玻璃 内边 14 标题 17 说明 13 按钮 48 胶囊；Mac = Kit Alert Stacked 260 宽 r26 图标 72 @(22,20) 标题 Bold 13 说明 13 内边 16 按钮 Large 28 距文字 14 |
| E4 | 信息浮层 `#info` | Kit 无 → Popover | Popovers r20 | — | ✅ Mac（maa 分支）：r20 + Popover 材质，距右/底 16 |
| E5 | 地方跳转胶囊 `#jumps.chips` | 同 A20 | 同 A20 | — | 随 A20 |
| E6 | 東亜图例的国家勾选 `#cbGrid input[type=checkbox]`（清单原先漏掉：原生 checkbox） | iOS 无 checkbox → Lists › Rows › Editing 多选圆：22 圆、未选 1.5 描边 #bfbfbf、选中 tint 底 + 白 􀆅 | Toggles - Checkboxes › Regular：16×16 r5.5、未选黑 10%（按下 19%）、选中 #0088ff + 白勾 9×9（按下 +黑 7%）、标签 Medium 13 间 5、行 24 | NUMBERS（两节新增 2026-09-15） | ✅ 两端（maa 分支） |

## F. index.html（首页）

| # | 控件 | 手机 | Mac | 出处 | 状态 / 计划 |
|---|---|---|---|---|---|
| F1 | 大标题 `.t-large` | Large Title 34/41 | Large Title 26/32 | NUMBERS | ✅ |
| F2 | 图标行 `.row.icon`（设置 App 顶层行） | Row Regular 52 + 分隔（设置 App 同） | Sidebars › Items › Large 40、图标 24 —— **现无 Mac 规则**，1440 仍是手机列表居中 | NUMBERS | 手机 ✅；Mac ✅（本批 11c：行 Large 40、图标 24、标题 13 + 副题 11、无分隔线无箭头、悬停黑 5%；分组 Group Box r12 黑 3%） |
| F3 | 段头 `.sect h2` / 段尾 `.foot` | 设置 App 实测（Kit List Header 未核，同 A8） | Sidebars › Header 18 / Bold 11 | NUMBERS | 手机 ✅（同 A8：Kit Nested header；段尾 = Kit Footer Regular 13 @y8）；Mac ✅（1277f1e） |
| F4 | 分组卡 `.group` | 设置 App 卡 r26 内缩 20 | Group Boxes r12 黑 3% | NUMBERS | 手机 ✅；Mac ✅（本批） |
| F5 | Claw'd 插图 | 非 HIG 组件（用户保留素材） | 同 | DESIGN-HIG | ◇ |

## Kit 页解析状态（macOS 27，全部走 Sketch）
Disclosure Controls / Sliders / Alerts 已解（hig-kit 58365ea，NUMBERS KIT_VERSION 5）· Popovers / Menus / Materials 已解。
iOS 27 Kit（Sketch 版 2026-09-09，hig-kit 748a7c6）：Sheets / Toolbars / Lists / Segmented / Buttons / Alerts 已解，写在 NUMBERS「iOS 27 UI Kit（Sketch 版）」；Figma 不再需要。

## 施工顺序（本会话，cost/hig.css/shell.js）
1. 解 Kit：Disclosure Controls、Sliders、Alerts → NUMBERS.md。2. hig.css 11b：A1 工具条玻璃、A2 分隔线、A3 菜单、A10 建议卡、A14/15 展开指示、A19 滑块、A24 ±、A25 ⓘ、A26 材质、C1 opt→Popover、F2–F4 首页。3. 每步 1440 + 375 全部标签/展开项截图自查。4. 手机侧 A2/A4/A5/A7/A8/A9 已按 Sketch 版 iOS 27 Kit 改（本批）。C2、E1–E4（+ 补的 E6 勾选框）maa 分支已改完（2026-09-15 晚）；◇ 行（Kit 无组件）保持并注明规则。
