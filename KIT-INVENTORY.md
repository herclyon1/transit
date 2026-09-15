# 控件清单 · 五页 × (iOS 27 Kit / macOS 27 Kit)

2026-09-15 用户令（经 maa 会话）：「按 Kit 重做」= 页面上每一个可见控件都对上 Kit 组件，不是挑几个数字换。先出清单再动手；
改完的行标「已按 Kit + commit」；全部改完才许说「按 Kit 重做完成」。推送前 Mac 1440 / 手机 375 每个标签、每个可展开项点开截图自己看，探针只是底线。

状态：**✅ 已按 Kit（commit）** · **⛔ 未按 Kit → 计划** · **◇ Kit 没有此组件 → 按 HIG/系统 App 实测，写明规则**。
数字出处：iOS = Figma 「Apple iOS and iPadOS 27 UI Kit」节点 id（NUMBERS.md 上半），macOS = Sketch 「Apple macOS 27 UI Kit」页›artboard（NUMBERS.md「macOS 27 UI Kit」）。
分工：cost/index.html、ui/hig.css、ui/shell.js、本清单 = 本会话；osaka/japan/quiz 三个文件 = maa 会话（interaction 分支），它们页内的项本会话只在 hig.css 里改，页内改动等分支合并。

## A. 共用（cost / osaka / japan / quiz）

| # | 控件 | 手机 = iOS 27 Kit | Mac = macOS 27 Kit | 数字出处 | 状态 / 计划 |
|---|---|---|---|---|---|
| A1 | 顶部工具条玻璃圆钮 `.bar .btn-glass`（返回 / 图层 / 货币） | Toolbar - Top - iPhone `1:54472`：44 圆、距边 16/20 | Titlebars and Toolbars › XL › Buttons：36×36 胶囊、内 28、间 8、距边 8 | NUMBERS 两节 | 尺寸 ✅（3820172）；**材质 ⛔**：Mac 仍用 iOS 玻璃近似（白 55% + 模糊 22），Kit 工具条玻璃 = 黑 25% + 白 25% + #444 60% + #f8f8f8 20% + 背景模糊 6 + 边缘高光 → 计划：hig.css 11b 加 Kit 配方 |
| A2 | 工具条分段控件 `.bar .seg`（japan 現代日本/東亜、quiz 模式） | Segmented Control `10460:145`：S 32 / L 50 —— **现用 44 与圆钮同高，Kit 未核**（NUMBERS「Open」） | Titlebars and Toolbars › XL › Segmented Control：36 高、段 32×28、分隔 3×22 | 同上 | 手机 ⛔（Kit 里工具条分段是什么高度要核：iOS 27 Kit 也有 Sketch 版，走 Sketch 取，不碰 Figma）；Mac 尺寸 ✅（3820172）、**分隔线未画 ⛔** → 11b 补 3×22 分隔 + Kit 玻璃 |
| A3 | 货币下拉菜单 `.menu`（cost） | Menu（UIMenu）：248 宽、r26、行 42、内边 5 —— Safari 长按菜单实测 | Menus › Light › Regular：容器 r12、内缩 16、行 24 Medium 13、悬停底 r8 外扩 11、分隔 11 高 | NUMBERS | 手机 ◇（Kit 无 UIMenu 组件，按系统实测）；**Mac ⛔** → 11b 加 `.menu` 规则 |
| A4 | Sheet（手机）/ 侧栏（Mac）`.sheet` | Sheet `10525:1632`：内缩 8、圆角 38、三档 | Windows › Left Pane：256 宽、内边 8、窗口圆角 16、材质 #fafafa 80% + 模糊 100 | NUMBERS | ✅（3820172） |
| A5 | 抓手 `.grab` | Sheet grabber 58×4 距顶 5 | Kit 无（桌面不拖） | NUMBERS | 手机 ✅；Mac 隐藏 ✅ |
| A6 | Sheet 头搜索胶囊 `.head .search`（cost 列表） | Search `5720:33677`：44、r1000、11/10 内边 | Titlebars and Toolbars › XL › Search：159×36；Search Fields › Regular：白底 + 1px 黑 5% 描边、图标槽 @8 | NUMBERS | ✅（3820172） |
| A7 | 地点卡片头 `#card .head`（标题 / 副标题 / 关闭） | Kit 无地点卡片头 → 地图 App 地点卡片实测：44 圆钮距顶 15 距边 15，标题 22/28 粗居中 | Windows › Utility Panel › Titlebar：24 高、红灯 10⌀ #ff5c60 @(8,8)、标题 Medium 11 居中 | NUMBERS | 手机 ◇（App 布局实测）；Mac ✅（05a19ca） |
| A8 | 列表段头 `.mh` | Kit「List › Section Header」**未核**（现按设置 App 实测 17 半粗 secondaryLabel） | Sidebars › Headers › Medium：18 高、Bold 11、距边 14 | NUMBERS | 手机 ⛔（Sketch 版 iOS 27 Kit 核 List Header）；Mac ✅（3820172） |
| A9 | 列表行 `.mlist .mrow`（cost 城市行、osaka 图例行） | Kit Row Regular 52 —— **现用地图 App 搜索结果行实测 69**（双行 + 圆图标 34） | Sidebars › Items › Large：40 高、图标 24 @14、标题 Regular 13、选中底 r8 黑 11% | NUMBERS | 手机 ◇→需裁定：Kit 有 Row 52，Maps 搜索结果行是 App 布局；按「尺寸取 Kit」应改 52 双行？请用户/maa 定；Mac ✅（3820172，双行 13+11 是推算） |
| A10 | 建议卡 `.sugg`（cost 首屏介绍卡） | Kit 无 → 地图 App「附近的公共交通」建议卡实测：白 55% r16、圆图标 36 | Kit 无建议卡 → Group Boxes：r12 黑 3%；图标 24 | NUMBERS | 手机 ◇；**Mac ⛔**（仍是手机样式 r16 / 36 图标）→ 11b 改 Group Box + 24 图标 + Kit 字号 |
| A11 | 统计卡 `.stats .stat` | Kit 无 → 健身 › 摘要 实测：两列 195、r20、内边 16 | Group Boxes：r12 黑 3%；数字 Title 1 22 | NUMBERS | 手机 ◇；Mac ✅（3820172） |
| A12 | 动作行 `.actions .btn`（换算成工时 / 来源） | Kit 无 → 地图 App 地点卡片动作行实测：等宽 50 高 | Segmented Controls › Regular：24 r6、轨道黑 8%、Medium 13 | NUMBERS | 手机 ◇；Mac ✅（05a19ca）；「可达性图」没做不显示 ✅ |
| A13 | 卡片分组 `.mcard` + 行 `.r` | Kit 无 → 地图 App 地点卡片实测：r20 半透明、行 47 | Group Boxes r12 黑 3%；行 = Sidebars › Items › Medium 32 | NUMBERS | 手机 ◇；Mac ✅（3820172） |
| A14 | 可展开行 `.job .jr` + 展开区 `.det`（岗位 / 来源行） | 行同 A9（69）；展开 = 点行 | 行 = Sidebars › Large 40；展开指示 = **Disclosure Controls**（Kit 有 120 个 artboard，未解） | NUMBERS | 手机 ◇；Mac 行 ✅（05a19ca）、**展开指示 ⛔** → 解 Disclosure Controls › chevron/triangle 尺寸写 NUMBERS，`.jr[aria-expanded]` 与 `.sublist summary` 用它 |
| A15 | 次级列表 `details.sublist`「看 8 家店」 | Kit 无 → HIG Disclosure | Disclosure Controls | — | ⛔ 同 A14 |
| A16 | 四档表 `table.tiers` | Kit 无表格控件 → HIG Tables；字号 Footnote 13 | Kit 无 Table View 页 → 字号 Body 13 / Subheadline 11，分隔 separator | — | ◇（字号已随根字号） |
| A17 | 置信度胶囊 `.tag` / 小圆点 `.chip` | Kit 无 → 24 高 tint 12%（未量，NUMBERS 记「unmeasured」） | Kit 无 | NUMBERS | ◇（保留，标未量） |
| A18 | 开关 `.sw` | Toggles `5433:19059` 63×28（设置 App 同） | Toggles - Switches › Regular 54×24、圆钮 32×20、按下 50×31 | NUMBERS | ✅ 两端（3820172） |
| A19 | 滑块 `.r.slider`（osaka 阈值 / 步行） | Sliders `7:53847`：轨道 4 r2、圆钮 28 | Sliders 页（836 artboard）**未解** | NUMBERS | 手机 ✅；**Mac ⛔** → 解 Sliders › Regular（轨道高、圆钮、刻度）写 NUMBERS + 11b |
| A20 | 筛选胶囊 `.chips button`（osaka 枢纽数、quiz 地方跳转） | Kit Button S 28 —— 现按地图 App 筛选胶囊实测 32 | Buttons › Large：28 胶囊、Medium 13、内边 16 | NUMBERS | 手机 ◇（App 实测，DESIGN-HIG 记）；Mac ✅（3820172） |
| A21 | 缩略图块 `.tiles`（japan 底图） | Kit 无 → 地图 App 地图模式块实测 91 | Kit 无 → 三块各 78 塞 280 面板（推算） | NUMBERS | ◇ 两端（Mac 推算已注明） |
| A22 | 行内分段控件 `.mcard .seg`（japan/quiz 题型等） | Segmented S 32 | Segmented Controls › Regular 24 r6 | NUMBERS | ✅ 两端 |
| A23 | 按钮 `.btn.s/.m/.l`（quiz 再来一轮 / 开始 / 不会） | Button - Liquid Glass - Text `5473:21667`：28 / 34 / 50 | Buttons › Regular 24 r6 / Large 28 胶囊 / XL 36 胶囊 | NUMBERS | ✅ 两端（3820172） |
| A24 | MapLibre 缩放 ± 控件（地图右下） | iOS 地图 App 没有 ± 按钮（捏合缩放） | Kit 无 ± → Titlebars and Toolbars › XL › Button Group（36 胶囊内两颗 28） | — | **⛔ 两端**：手机隐藏；Mac 按 Kit Button Group 重画（hig.css，MapLibre 控件类名） |
| A25 | 底图署名 ⓘ（MapLibre attribution 折叠钮） | Kit 无 → 地图 App 右下「Legal」小字 | Titlebars and Toolbars › Medium › Buttons 24 | — | **⛔** → hig.css 按 24 玻璃钮 |
| A26 | 玻璃材质 `.glass`（所有浮层） | Materials（Kit 折射不可复现 → 白 55% + 模糊 22 + 内描边） | Materials › Regular：#ececec 63% 模糊 60 饱和 1.45；侧栏材质已用 Kit | NUMBERS | 手机 ◇（记录近似）；Mac 浮层 ⛔ → 11b 统一 Kit Regular material（工具条另按 A1 配方） |
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
| C1 | 图层选项 Sheet `.sheet.opt`（第二张 Sheet） | Sheet（同 A4） | Kit 无第二侧栏 → **Popovers**：r20、白 70% + 模糊 30、阴影 0 18 46 25%，从工具条按钮弹出 | NUMBERS | 手机 ✅；**Mac ⛔** → hig.css 11b 给 `.sheet.opt` 在 Mac 改 Popover（锚定工具条钮） |
| C2 | 车站 popup `.hpop`（MapLibre popup r16） | Kit 无 → HIG Popover | Popovers r20 | NUMBERS | **⛔ 两端**（页内样式，maa 分支）→ 手机 r16 改 Kit？iOS 27 Kit 有 Popover 组件待核；Mac r20 + Kit 材质 |
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
| E1 | 题目条 `#promptBar`（玻璃卡 + 反馈 + 两颗按钮） | Kit 无 → HIG（顶部浮层） | Kit 无 → Popovers r20 材质 | — | **⛔ Mac**（页内样式）→ r20 + Kit Regular material + 按钮 A23 |
| E2 | 图例浮层 `#legend`（lg-head / lg-body / lg-jmp 小按钮） | Kit 无图例；lg-jmp = Button S 28 | Kit 无；lg-jmp = Buttons › Regular 24 r6 | — | **⛔ 两端**（lg-jmp 现为自定义样式）→ 用 `.btn.s` |
| E3 | 完成卡 `#doneCard .box`（模态） | **Alerts**（iOS Kit 有）—— 现 r26 自定义 | Alerts 页（14 artboard）**未解** | — | **⛔ 两端** → 解 Alerts 写 NUMBERS，两端按 Alert 做 |
| E4 | 信息浮层 `#info` | Kit 无 → Popover | Popovers r20 | — | ⛔ Mac |
| E5 | 地方跳转胶囊 `#jumps.chips` | 同 A20 | 同 A20 | — | 随 A20 |

## F. index.html（首页）

| # | 控件 | 手机 | Mac | 出处 | 状态 / 计划 |
|---|---|---|---|---|---|
| F1 | 大标题 `.t-large` | Large Title 34/41 | Large Title 26/32 | NUMBERS | ✅ |
| F2 | 图标行 `.row.icon`（设置 App 顶层行） | Row Regular 52 + 分隔（设置 App 同） | Sidebars › Items › Large 40、图标 24 —— **现无 Mac 规则**，1440 仍是手机列表居中 | NUMBERS | 手机 ✅；**Mac ⛔** → 首页 Mac 布局：Kit 侧栏行 + Group Box，写 hig.css 11b `.sect/.group/.row` |
| F3 | 段头 `.sect h2` / 段尾 `.foot` | 设置 App 实测（Kit List Header 未核，同 A8） | Sidebars › Header 18 / Bold 11 | NUMBERS | 手机 ⛔（同 A8）；Mac ⛔（随 F2） |
| F4 | 分组卡 `.group` | 设置 App 卡 r26 内缩 20 | Group Boxes r12 黑 3% | NUMBERS | 手机 ✅；Mac ⛔（随 F2） |
| F5 | Claw'd 插图 | 非 HIG 组件（用户保留素材） | 同 | DESIGN-HIG | ◇ |

## 待解的 Kit 页（macOS 27，全部走 Sketch）
Disclosure Controls（A14/A15）· Sliders（A19）· Alerts（E3）· Popovers 已解（C1/C2/E1/E4）· Menus 已解（A3）· Materials 已解（A1/A26）。
iOS 27 Kit：List Header（A8/F3）、Toolbar Segmented（A2）、Popover（C2）、Alert（E3）—— 走 Apple Design Resources 的 Sketch 版 iOS 27 Kit，不碰 Figma（额度到 09-19 15:09Z）。

## 施工顺序（本会话，cost/hig.css/shell.js）
1. 解 Kit：Disclosure Controls、Sliders、Alerts → NUMBERS.md。2. hig.css 11b：A1 工具条玻璃、A2 分隔线、A3 菜单、A10 建议卡、A14/15 展开指示、A19 滑块、A24 ±、A25 ⓘ、A26 材质、C1 opt→Popover、F2–F4 首页。3. 每步 1440 + 375 全部标签/展开项截图自查。4. 手机侧 A2/A8/A9 待 Sketch 版 iOS 27 Kit 核完再动。
