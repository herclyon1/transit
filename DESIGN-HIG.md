# transit 的界面照 Apple Human Interface Guidelines 做

2026-09-15 起，全站五页（首页、薪资·购买力、大阪·居住、地図·学習、都道府県クイズ）的界面层统一由
`ui/hig.css` + `ui/hig.js` 提供；页面自己不写颜色、字号、圆角。方法沿用 `~/Claude/maa-automation/docs/HIG-CHECKLIST.md`
（另一会话 2026-09-14 做手机页时定型）：**规则来自 HIG，数字来自 Apple 官方 UI Kit，与真机不一致时以模拟器实测为准。**

## 三个来源

1. **HIG 正文**（Liquid Glass 版，iOS 26/27）—— https://developer.apple.com/design/human-interface-guidelines ，通过它的
   JSON 接口读：maps、sheets、searching、toolbars、sidebars、layout、materials、typography、color、motion、buttons、
   segmented-controls、tab-bars、lists-and-tables、designing-for-ios、designing-for-macos。给规则，基本不给数字。
2. **Apple 官方 iOS and iPadOS 27 UI Kit**（Figma，用户自己的副本，key 在 `~/.config/ark/push.env` 的 `FIGMA_IOS_KIT`）——
   通过 Figma REST API `/v1/files/<key>/nodes?ids=…` 读几何。下表的节点号就是数字的出处：
   Sheet - iPhone `10525:1632`、Grabber `5827:57566`、Toolbar - Top - iPhone `1:54472`、_Search - Top `5720:33677`、
   _Title - Large Title `5827:57551`、Button - Liquid Glass - Text `5473:21667`、Segmented Control `10460:145`、_Option `10456:16913`、
   _Search Field `5840:30471`、Row `550:50430`、Section Title `50:56535`、Grouped Table Footer `35:55757`、Toggles `5433:19059`、
   Text styles `5418:17464`、Colors `5707:28659`。
3. **iOS 27 模拟器**（iPhone 18 Pro Max，440×956pt，简体中文；Xcode 26.6 的 iOS 27.0 运行时）——**地图 App 首页**于
   2026-09-15 08:26 逐像素测量（`xcrun simctl io screenshot`，3× 截图除以 3）：Sheet 左右各内缩 8、顶边在 533.7pt
   即高 44% 屏、圆角拟合 36–37（取 Kit 的 38）、抓手 57×4 距顶 5、搜索胶囊高 44 距 Sheet 内边 16 距顶 15、右侧浮动控件组 49 宽
   两个 44 按钮、底边在 Sheet 上沿之上 35。**地图 App 地点卡片**（搜 Tokyo Station，08:57）：两枚 44 圆钮距 Sheet 顶 15、距 Sheet 边 15，
   标题 22 粗体居中、副标题 15，主按钮 50 高距 Sheet 边 20，段头 17 半粗 label 色距 Sheet 边 20（与卡片对齐），白卡片距 Sheet 边 20，
   筛选胶囊 32 高。**设置 App 顶层**（08:59）：卡片距屏边 20（不是 16——UIKit 布局边距在 ≥414pt 宽的机型是 20）、行 52.33
   （Kit Row Regular 52 + 1/3 分隔线）、图标 28 距卡片边 18、文字与分隔线内缩 60、分隔线 0.67 粗、卡片相隔 35、大标题距屏边 20、
   标题到首张卡片 13。段头 28/6、段尾 6/24、开关 63×28 沿用另一会话 iOS 26.5 的测量。Kit Row：Regular 52 / Tall 68。

## 每一页照哪个原生 App

| 页 | 样板 | 结构 |
|---|---|---|
| 首页 `index.html` | 设置 App 顶层 | 大标题 34/41 → 分组列表：每张图一行（30pt 圆角图标 + 名称 + 副标题 + 箭头），说明放段尾 13pt |
| 薪资·购买力 `cost/` | 地图 App（HIG Maps › Place cards：iOS 用 sheet，iPadOS/macOS 用侧栏） | 地图全屏；顶部左 44 玻璃圆钮（返回）、右 UIMenu 下拉（货币）；底部非模态 Sheet：列表态 = 搜索胶囊 + 建议卡 + 「城市」+ 国旗圆图标行，卡片态 = 地点卡片头 + 动作行（换算成工时 / 来源 / 可达性图）+ 2×2 统计卡（时薪/房租/通勤/食费）+ 分节卡片 + 「来源与相关图」链接行；iPad 侧栏 440，Mac 侧栏 200 + 卡片面板 282 |
| 大阪·居住 `osaka/` | 地图 App（地点卡片 + 地图模式 Sheet + 公共交通模式标注） | 地图全屏；返回钮 + 右上「图层」钮；主抽屉只放结果：阈值值卡（健身统计卡的形 + Kit 滑块）、可达枢纽数筛选胶囊、可达枢纽图例、居住等级色点；五个开关在「图层」小 Sheet；车站 = 线路色实心点 + 白圈，枢纽带名字图标；主题跟随系统 |
| 地図·学習 `japan/` | 地图 App | 顶部玻璃分段控件切「現代日本／東亜」；Sheet 小档只露标题和提示，点了地图升到中档显示详情；图层（交通开关、底图分段控件）和凡例在 Sheet 里 |
| クイズ `quiz/` | 地图 App + HIG Buttons / Alerts | 玻璃分段控件切模式；题目是顶部玻璃卡；地方跳转是一排 28 高胶囊；设置在 Sheet（范围/题型 pop-up、两个开关）；结算是居中的 26 圆角卡 |

## 数字表（改任何一个先改这里）

| 项 | 值 | 出处 |
|---|---|---|
| 根字号 | `font:-apple-system-body`（17pt，跟随「文字大小」），其余全用 em | HIG Typography / Dynamic Type |
| 字体 | `-apple-system, "SF Pro Text", "PingFang SC", "Hiragino Sans", "Noto Sans CJK SC"…`——中文日文一律苹方（用户 2026-09-15 定） | Kit Text styles |
| 文字样式 | Large Title 34/41 700 · Title 2 22/28 700 · Headline 17/22 600 · Body 17/22 · Subheadline 15/20 · Footnote 13/18 · Caption 11/13 | Kit `5418:17464` |
| 颜色 | tint #0088ff（深 #0a84ff）· 绿 #34c759 · 红 #ff383c · secondaryLabel rgba(60,60,67,.6) · separator rgba(60,60,67,.29) · systemFill rgba(120,120,128,.2) · 分组底 #f2f2f7 / 黑 · 卡 #fff / #1c1c1e · disabled #aeaeb2 | Kit `5707:28659` |
| 玻璃 | 底色 55% 白（深 55% #1e1e20）+ blur 22 saturate 180% + 内描边 .5px + 阴影 0 8 28 16% | Kit Materials（GLASS 效果网页做不了折射，只能近似） |
| 顶部工具条 | 内容区 54 = 44 按钮 + 10 下边距；左右 16；按钮组 44 圆形，组内文字钮 36 高 8 内边 | Kit `1:54472` |
| 搜索胶囊 | 44 高，圆角 1000，左 11 右 10，图标 17 中体，文字 17/20 中体 | Kit `5720:33677`；地图 App 实测 44 |
| 胶囊按钮 | 小 28（5/10）· 中 34（8/12）· 大 50（16/20），文字 15/17 中体 | Kit `5473:21667` |
| 分段控件 | 小 32 / 大 50，外内边 2，段间 4，段圆角 1000，选中白底 + 20 模糊阴影，文字 13.33/18，选中 590 | Kit `10460:145` |
| Sheet | 左右内缩 8；圆角 38；抓手 58×4 圆角 100 距顶 5；内容顶部内边距 16；中档 = 44% 屏高；大档 = 屏高 − 62；小档 = 96 + 安全区 | Kit `10525:1632`；地图 App 实测（内缩、44%） |
| 布局边距 `--inset` | 16；视口 ≥414pt 时 20（Plus/Max 机型） | 设置/地图 App 在 iPhone 18 Pro Max 上实测 20 |
| 分组列表 | 卡片圆角 26，左右 = 布局边距；单行 52.33（15 上下内边 + 17/22）、双行 68.33（13 + 17/22 + 15/20）；文字内缩 20 右 20；带图标的行：图标 28 距边 18，文字与分隔线内缩 60；分隔线 0.67；段头 17 半粗 上 28 下 6（设置 App：secondaryLabel、比卡片再内缩 20；Sheet 里：label 色、与卡片对齐）；段尾 13/18 上 6 下 24；卡片间 35；副标题单行截断 | 设置 App iOS 27 实测 + Kit Row 550:50430 |
| Sheet 标题区 | 第一行距 Sheet 顶 15（抓手区 15 = 5 + 4 + 6）；圆钮 44 距边 15；搜索胶囊距边 16；标题 22/28 粗居中、副标题 15/20 单行、两侧各 44 槽位；正文距标题块 16 | 地图 App 地点卡片实测 |
| 开关 | 63×28，圆钮 38×24 白药丸，开绿关灰，0.2s | Kit `5433:19059` + 设置 App 实测 |
| 滑块 | 轨道 4 圆角 2，填充 tint，圆钮 28 白带阴影 | Kit Sliders `7:53847` |
| 浮动地图控件 | 右 = 布局边距，44 圆钮竖排 | 地图 App 实测 |
| 工具条里的分段控件 | 44 高（与圆钮同高） | **待核**：Kit Toolbar-Top 是否有 Segmented 变体（Figma API 限流，2026-09-15 09:20 三次 429），模拟器里没有带顶部分段控件的系统 App 可量 |
| 宽屏·触屏（iPad） | ≥900px 且 pointer: coarse：侧栏面板 440 宽、左 24、顶 = 安全区 + 8、底 20、圆角 38；搜索 44 距边 16 距顶 16；控件簇右上距右 24 | iPadOS 27 地图 App 实测（iPad Pro 13″ 竖屏，09:56） |
| 宽屏·鼠标（Mac） | ≥900px 且 pointer: fine：系统字号 13；侧栏面板 200 宽、左 8、顶 8、底 8、圆角 14；搜索框 36 距边 15 距顶 12；侧栏行 32（13pt + 11pt 副标题、图标 22）、段头 11 灰；地点卡片 = 第二块面板 282（薪资：列表 200 + 卡片并排；其余页整个面板 282）：圆钮 28 距边 12 距顶 12，标题 17 粗居中、副标题 11，主按钮 45 距边 16，段头 15 半粗距边 20，筛选胶囊 25 间 9，卡片圆角 12 距边 16、行 44（13/16）、头行 24 图标；控件簇 36 圆钮距右 8 距顶 8 间 10；开关 38×22（NSSwitch） | macOS 27 地图 App 实测（窗口 1280×744，AX 坐标，2026-09-15 10:55） |
| 动效 | Sheet 档位 0.32s cubic-bezier(.2,.8,.2,1)；开关 0.2s；`prefers-reduced-motion` 全关 | HIG Motion |

## HIG 逐条对照

| HIG 页 | 规则（浓缩） | 页面怎么做的 |
|---|---|---|
| Maps | 别用不可交互的东西盖住地图；自定义控件要靠描边/阴影和地图区分；搜索配筛选；选中要有明显样式；place card 在 iOS 是 sheet、iPadOS/macOS 是 popover/侧栏 | 地图全屏，所有控件是玻璃（有阴影和内描边）；城市卡片是非模态 Sheet，iPad 侧栏 440，Mac 侧栏 200 + 卡片面板 282；Sheet 里只用地图 App 自己的组件（段头/半透明卡片/搜索结果行/筛选胶囊/地图模式磁贴/建议卡/主按钮），不用设置 App 的分组表 |
| Sheets | 非模态 sheet 有抓手，拖或点抓手在档位间切换；中档约半屏，大档全高；内容滚到顶再下拉可缩 | `HIG.sheet()`：三档，抓手点击循环、拖拽按位置落档、滚到顶再下拉退回中档 |
| Searching | 一个清楚的搜索入口，占位文字说明搜什么 | 薪资图 Sheet 顶部搜索胶囊「搜索城市」，边打边筛 |
| Toolbars | 标题非必需；返回用标准符号；只放最重要的动作；iOS 大标题随滚动变小 | 顶部只有返回钮（chevron.left）和一个主动作（货币 / 区域分段）；首页大标题 |
| Segmented controls | iPhone 上不超过五段，单词标签 | 地図·学習两段；クイズ五段（用户要求保留五个模式） |
| Lists and tables | 分组样式：段头、段尾、留白分组；行内文字简洁 | 所有设置和数据都是 `.sect > h2 + .group > .row + .foot` |
| Materials | Liquid Glass 只给悬浮的控件层，内容层用标准材质，少用 | 玻璃只在工具条、Sheet/侧栏、浮动按钮、题目卡；分组卡片是实色 |
| Typography | 系统字体、Dynamic Type、文字样式 | 根字号 `-apple-system-body`，全站 em；文字样式类 `.t-*` |
| Color | 系统色，支持深色模式 | token 两套值；`prefers-color-scheme` + `data-theme` 都认 |
| Motion | 短、准、可关 | 见数字表 |
| Settings | 尊重系统设置，不做冗余版本 | 大阪页删掉了手动明暗按钮，主题跟随系统 |
| Designing for iOS | 控件放中下部，限制屏幕上的控件数 | 控件集中在底部 Sheet；顶部只两枚 |
| Buttons | 胶囊、大小三档、销毁用红 | `.btn.s/.m/.l`，`.btn.red` |

## 验收程序

一次改动要过三关，都在仓库里，跑一条命令：

```bash
xcrun simctl boot "iPhone 18 Pro Max"; python3 pipeline/rangeserver.py 8788 &
python3 pipeline/ui/accept.py
```

1. **数据/结构自检**（原有）：`python3 pipeline/cost/validate.py`。
2. **真机 DOM 数值验收**（确定性，`ui/accept.js`）：任何页面地址加 `?accept` 就会加载它，在**该浏览器里**量 DOM 并逐项与数字表比
   （根字号、字体栈含 PingFang SC、tint、工具条圆钮 44 与边距、Sheet 内缩 8 / 圆角 38 / 44% / 抓手 58×4@5、搜索胶囊 44@16@15、
   卡片头圆钮与标题位置、卡片圆角与边距、单行 52.33 / 双行 68.33、图标 28@18、文字 60、分隔线 0.67、段头段尾字号与间距、
   分段控件 32/2/4、按钮 28/34/50、开关 63×28 与 38×24 圆钮、滑块 28、大标题 34/41、SF 蒙版、系统配色），左上角盖结果；
   加 `&quiet` 不画覆盖层。结果同时 POST 到 rangeserver 的 `/accept`，写 `.accept/<页>.json`；`accept.py` 用模拟器 Safari
   逐页打开 `?accept=1&quiet=1`，汇总打印，任一超差退出码 1。
   只认 Safari/iOS 的数字：桌面预览面板是 Chromium，`-apple-system-body` 落到 16，并且没有安全区。
   2026-09-15 09:12 结果：五页 21/32/44/38/42 项全部通过，浅色与深色（`simctl ui … appearance dark`）都过。
   已知口径差：Safari 有自己的地址栏，视口是 440×796 而不是 956，Sheet 的 44% 按视口算（加到主屏幕后就是整屏）。
3. **模拟器目测**：`accept.py` 还会截地图 App 首页做基准、逐页截图，拼成 `.accept/compare.png`（左起地图 App、首页、薪资、大阪、学習、クイズ），
   人眼核对：玻璃、字体（PingFang）、标题居中、间距。
4. **宽屏**：桌面预览面板 1280×744 打开 `<页>?accept`（pointer: fine → macOS 数字：侧栏 200/面板 282、行 32/44、圆钮 36…）；iPad Pro 13 模拟器（触屏）→ 440 侧栏，`SIM_UDID=<iPad> python3 pipeline/ui/accept.py`。2026-09-15 11:05 两套各四张图全部通过。
5. **网页 App**：`python3 pipeline/ui/webclips.py` 装图标 → `python3 pipeline/ui/accept.py --webapp` → 逐个点图标；11:00 五页通过、点击位置与显示一致。

**任何一项与数字表不符 = 回归**，先改这份表再改 CSS，再改 `ui/accept.js` 的期望值。

## 地图 App 组件（iOS 27，2026-09-15 实测；CSS 在 ui/hig.css §14）

| 组件 | 数字 | 量自 |
|---|---|---|
| 段头 `.mh` | 17 半粗 label 色，上 28 下 10，距 Sheet 边 = 布局边距；首页带 › | 地点卡片「出发班次」、首页「地点 ›」 |
| 半透明卡片 `.mcard` | 填充比玻璃底暗 6%（`--fill-3`），圆角 20，距边 20，左右内边 16；头行 24 图标 + 17 半粗；行 47（17/22 + 12.5×2）值右对齐；分隔线 1 | 地点卡片「Hokuriku Shinkansen」卡 |
| 列表 `.mlist/.mrow` | 白卡圆角 26 距边 20 卡片间 13；行 69（13.5 + 17/22 + 15/20 + 13.5）；圆图标 34 距卡片边 16；文字 61；分隔线 1 内缩 61/16 | 搜索结果（大档，Sheet 满宽） |
| 筛选胶囊 `.chips` | 32 高，间 8，选中 tint 白字，未选中 fill + 1 描边，15 中体 | 地点卡片 Shinkansen / JR East / Tokyo Metro |
| 地图模式磁贴 `.tiles` | 87 图 + 2 选中描边 = 91，圆角 12，间 10，标签 13 距块 10 | 右上「地图模式」Sheet |
| 建议卡 `.sugg` | 白 55%，圆角 16，圆图标 36，标题 17 半粗，副标题 15，右上 ×，17 tint 链接 | 首页「附近的公共交通」 |
| 主按钮 `.btn.l.stack` | 50 高 tint，图标在上 13 标签在下，距 Sheet 边 20 | 地点卡片「规划」 |
| 卡片头 | 圆钮 44 距顶 15 距边 15；标题 22/28 粗居中；副标题 15/20 | 地点卡片 Tokyo Station |
| 大档 | Sheet 满宽（左右 0） | 搜索结果 |
| 动作行 `.actions` | N 枚等宽、50 高、间 8、距 Sheet 边 20；首枚 tint 白字，其余灰底 tint 字，不可用更浅；图标 17 在上（距顶 8）标签 13 半粗在下 | 地点卡片 Apple Marunouchi（规划/呼叫/网站/下单，11:50） |
| 统计卡 `.stats/.stat` | 两列各 195、距边 20、间 10、圆角 20、内边 16；标题 17 半粗 + 右上 17 圆钮；副标题 15 灰；大数 28 粗；脚注 13 | 健身 › 摘要（Step Count 卡，11:47） |
| 置信度小胶囊 `.tag` | 24 高、13 半粗、tint 12% 底 | **未量**，待有实测再改 |
| 城市列表行右侧 | 数值 17 半粗 + 胶囊，与副标题同行（股市行的形）；数值 = 到枢纽 15 分那档每月要打的工时（与卡片「换算成工时」同一公式） | 形按 maa 会话意见，未量 |
| 选项小 Sheet `.sheet.opt` | 标题 17 半粗居中 + 关闭 44 距边 15，内容按需高；打开时主抽屉收起 | 地图 App「地图模式」Sheet（09:08） |
| 车站标注 | 线路色实心点 ≈5pt + 1pt 白圈，无黑描边；枢纽 = 带名字的图标（圆角方块 + 白色符号），标签 13 半粗带白描边 | 地图 App 公共交通模式，東京駅周边（11:51） |
| 分组表行（子页） | 白行 52.33 + 分隔线 1.0 = 间距 53.33；顶层图标行是 52.33 含 0.67 分隔线 | 设置 › 无障碍（11:48）/ 设置顶层（08:59） |

## 主屏幕网页 App（2026-09-15）

- 用 `apple-mobile-web-app-status-bar-style=default`（与 maa 手机页同一做法）：视口从状态栏之下开始，env(safe-area-inset-top)=0，fixed 元素、rect、触摸一致；地图不伸到状态栏底下。
- `black-translucent` 在 iOS 27 的网页 App 容器里：布局视口缩成 894 且 scrollY=-62，fixed 元素画在视觉视口、点击按布局视口算，差一个状态栏高；锁 html/body 都治不好。实验页 `pipeline/ui/standalone-test.html`（装成 web clip 复现）。
- `pipeline/ui/webclips.py` 直接往模拟器 `Library/WebClips/<UUID>.webclip` 写五个图标（Info.plist + icon.png），重启 SpringBoard 出现在第二页；`accept.py --webapp` 收结果（simctl 打不开网页 App，只能点图标；网页 App 里跨页跳转会让视口变 894，所以逐个点）。

## 拍板与边界（2026-09-15）

- **SF Symbols**：Apple 的许可写的是 Apple 平台；本站公开在 GitHub Pages。用户拍板照用（另一会话同样用法）。
  `pipeline/ui/sf-symbols-export.swift` 从系统字体导出为 4× PNG 蒙版到 `ui/sf/`，CSS 用 `mask-image` 上色。
- **字体**：网页不能内嵌 SF Pro / 苹方；Apple 设备上 `-apple-system` + `PingFang SC` 就是原生效果，安卓/Windows 落到 Noto。
- **Liquid Glass**：只有 backdrop-filter + 内描边 + 阴影，没有折射和高光跟随。
- **Claw'd**：不属于任何 HIG 模式，是用户保留的 Anthropic 官方素材，放在首页大标题右侧当页头插图。
- **地图底图**：GSI 淡色 / Natural Earth，HIG Maps 明说别模仿 Apple 地图的外观，底图不动。
- **小按钮**：Kit Button S = 28，地图 App 的筛选胶囊实测 32；本站 `.btn.s` 按 Kit 取 28，记一笔。
- **桌面（规则，用户 2026-09-15）**：网页按原生程序的做法——Mac 是 NavigationSplitView（左侧栏 + 右边地点面板），iPhone 是 Sheet 三档；尺寸一律从 Apple Design Resources 的 **iOS 27 / macOS 27 UI Kit** 取（macOS 套件走 Sketch 版：`~/Claude/hig-kit/kits/sketch/macos27/`，`dump.py` 读 pages/*.json），真机只量动效和 App 布局（Kit 里没有的）。除手机遥控页外全部页面都适配 Mac。
  桌面数字全在 `~/Claude/hig-kit/NUMBERS.md`「macOS 27 UI Kit」一节，`ui/hig.css` 11b 块照抄：侧栏 256 / 内边 8 / 圆角 16（Kit Windows › Left Pane）、地点面板 280（Kit Utility Panel）、根字号 13（Kit Body）、行 40（Kit Sidebar Large）、段头 18 / Bold 11、工具条 36 胶囊间 8、开关 54×24、分段 24 r6、按钮 24/28/36、卡片 r12 黑 3%（Kit Group Box）。
  作废：09-15 早上按 Maps.app 量的 200/282/13 和当天下午无出处的 360/380，两套都不再用（NUMBERS.md 里标了 history only）。
- **未做**：导航栈的滑动返回（这些页没有栈）；tab bar（每页是单一视图）；桌面动效（开关按下曲线沿用手机实测；Kit 只给了按下态的形状 50×31）。
