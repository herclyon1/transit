# KIT-MAP · 页面上的每个东西 → 哪个 Kit 组件

用户 2026-09-15 晚拍板：「Kit 没有这种组件」不成立——两套 Kit（iOS 27 Sketch 版 31 页、macOS 27 Sketch 版 35 页）的组件够把页面上
**所有控件**拼出来；对账工具（`pipeline/ui/kit-audit.py`）里不再有 ◇ 这一档，只有 ✅ / ⚠ / ✗，另加「内容」（地图标记、图例色块、吉祥物：
不是控件，不计入）。数字出处一律 `hig-kit/NUMBERS.md`（Kit 路径写在每行）。这份表是重构的施工图：每页一个代理，只改自己那页，
控件一律用 `ui/hig.css` 的类，**页内不许再写控件样式**（位置/布局可以）。

## 允许的词汇（只能用这些）

| 用途 | iPhone（iOS 27 Kit） | Mac（macOS 27 Kit，`(min-width:900px) and (pointer:fine)`） | hig.css 类 |
|---|---|---|---|
| 底部面板 / 侧栏 | Sheets › iPhone（中档四角 34 内缩 8；大档满宽上角 38） | Windows › Left Pane 256 / Utility Panel 280，r16，内缩 8 | `.sheet` |
| 面板头 | Toolbars › Top - Sheet（抓手 60×4 @5；44 圆钮 @16,16；Semibold 15/20 + Medium 12/16） | Utility Panel titlebar 24 + Stoplights 3×10 @0/17/34；Window Title Bold 15 | `.sheet .head` |
| 顶部工具条钮 | Toolbars › Buttons 44（条里有 Large 分段时 48） | Titlebars and Toolbars › XL 36 胶囊 | `.bar .btn-glass` |
| 分段控件 | Segmented Controls › Small 32（段 28）/ Large 48（段 44） | Segmented › Regular 24 r6（工具条里 XL 36） | `.seg` |
| 分组列表容器 | Lists › Grouped Table View：白底 **r26**，内缩 16，行 52 | Group Boxes r12 黑 3% | `.mcard` / `.mlist` |
| 段头 | Lists › Header › Nested 42（Semibold 17 secondaryLabel @16,10）；Prominent 45（Semibold 20 + trailing Action Regular 15 tint） | Sidebars › Headers Bold 11 | `.mh` / `.mh.prominent` |
| 段脚（说明文字） | Lists › Footer 30：Regular 13 @(16,8) secondaryLabel | Subheadline 11 secondary | `.mfoot` |
| 单行 | Lists › Rows › Default 52：Title Regular 17 @15；trailing Detail Regular 17 secondaryLabel | Forms › Row 40（文字）/ 48（带 24 控件）；分隔 1px 黑 5% | `.r` |
| 双行 | Lists › Rows › Large 68：Title 17 @14 + Subtitle Regular 15 @36 | Forms › Row 56（两行 32） / Sidebars › Rows Large 40 | `.mrow` / `.r.large` |
| 可展开行 | Rows › Accessories - Trailing › Disclosure Collapsed 􀆊 / Expanded 􀆈（Semibold 17） | Disclosure Controls › Regular 24 r6 | `.r.disc` / `.job .jr` |
| 行里的开关 | Accessories - Trailing › Toggle（63×28） | Toggles - Switches › Regular 54×24 | `.sw` |
| 行里的选择 | Accessories - Trailing › Pop-up Button（label 17 + 􀆏） | Pop-up Buttons › Regular 24 r6 | `.r .pop` |
| 行里的滑块 | Sliders（轨 4 r2、钮 28） | Sliders › Regular（控件 24、轨 6、钮 20×16） | `.r.slider` |
| 勾选 | Rows › Editing 多选圆 22 | Toggles - Checkboxes › Regular 16 r5.5 | `#cbGrid input` |
| 文字按钮 | Buttons › Small 28 / Medium 34 / Large 50；Bordered = #767680 12% + tint 字，Prominent = tint 底白字 | Push buttons › Regular 24 r6 / Large 28 / XL 36；Bordered 黑 8%，Default 蓝 | `.btn.s/.m/.l`（+`.tint`） |
| 动作行（卡片顶部几个动作） | 一排 Buttons › Medium 34（第一个 Prominent） | Segmented › Regular 24 r6 | `.actions .btn` |
| 筛选胶囊 | Buttons › Small 28 Bordered（选中 Prominent） | Push buttons › Regular 24 r6 | `.chips button` |
| 菜单（货币） | Menus › iPhone：250 宽、项 42、勾 Semibold 15 @10、字 Regular 17 @68、分隔 21 含 1px #e6e6e6 | Menus › Regular：r12、项 24、Medium 13 | `.menu` |
| 弹出信息 | Kit 无 iPhone Popover → Sheet 材质 r34 | Popovers r20 | `.hpop`, `#promptBar`, `#info` |
| 提示框 | Alerts › Default 300 r34、按钮 48 | Alerts 260 r26、按钮 Large 28 | `#doneCard .box` |
| 搜索 | Search 44 胶囊 | Search Fields 24 / Toolbar 36 | `.search` |
| 链接文字 | tint（Kit Colors #0088ff） | 同 | `a` |

## 现有的每一类「◇」→ 怎么改（代理照此施工）

| 现在 | 个数 | 改成 | 谁 |
|---|---|---|---|
| 来源列表行 `.links a` | 118 | `.mrow`（Large 68：标题 = 帖子/条目标题，副题 = 平台 · 日期）+ trailing 􀰑 符号（Accessories › Symbol） | cost |
| 分组卡片 `.mcard` | 42 | 留，但 hig.css 改成 Kit 数字（iOS r26 白底 / Mac Group Box r12） | hig.css（已） |
| 置信度胶囊 `.tag` / 小圆点 `.chip` | 40 | **删掉**。置信度写进行的副题（「平台现价 · SUUMO · 9 月 14 日」），四档表里写进 footer | cost |
| 四档表 `table.tiers` + 表里数字链接 | 36 | 每档一个 `.mcard`：段头 = 档位（Prominent，trailing 显示代表车站数），四行 = 单间月租 / 通学月票 / 通勤月票 / 单程（`.r` + trailing Detail，数字可点开来源）；分区票价表同（每区一组）；「换算成工时」表同 | cost |
| 统计卡 `.stats .stat` | 8 | 一组 `.mcard`「换算成工时」：四行 时薪 / 房租 / 通勤 / 食费（`.r.large`：标题 + 副题 = 样本 · 来源 · 日期，trailing Detail = 数字）；大数字不再单独放大 | cost |
| 设置行 `.r` | 22 | 留，hig.css 改成 Kit Rows Default 52 / Forms 40 | hig.css（已） |
| 动作行 `.actions .btn` | 9 | iOS 一排 `.btn.m`（第一个 `.tint`）；Mac 分段（已） | hig.css（已） |
| 折叠 `details.sublist` / `.tiers-how` | 6 | `.r.disc` 可展开行（trailing 􀆊/􀆈），展开内容 = 同组后续行 | cost |
| 图例浮层 `#legend`（quiz） | 4 | iOS：第二张 `.sheet.opt`（小档）；Mac：Popover（`.sheet.opt` 已是 Popover 样式） | quiz |
| 缩略图块 `.tiles` | 2 | `.seg`（Small 32 / Mac 24） | japan |
| 货币菜单 `.menu` | 1 | 留，hig.css 改成 Kit Menus › iPhone 数字 | hig.css（已） |
| 建议卡 `.sugg` | 4 | `.mh.prominent`（标题 + trailing Action「数据规范」）+ `.mfoot`（说明） | cost |
| MapLibre ± / ⓘ | 4 | Mac：Toolbar 玻璃钮（已）；iOS：± 隐藏（地图 App 没有），ⓘ = 44 玻璃圆钮 | 各页 |
| 标记 / 图例色块 / Claw'd | 12 | 内容，不计入（kit-audit「内容」） | — |
| `select`（quiz 范围/题型） | 2 | iOS：`.r .pop`（Pop-up 配件，点开 Kit Menu）；Mac：Pop-up Button 24 r6 | quiz |

## 通则（2026-09-16 定，两个会话核过 HIG 原文与原生 App）
1. **多选项过滤先用 scope 或点选，逐项开关只作二级页。** 苹果自己的 App 里没有在地图/图例上放 20+ 个逐项开关的：地图 App「地図の設定」= 3 种地图 + 2 个 overlay 开关，天气图层用分段，Health「比較」最多两条，照片/文件/邮件的筛选是菜单打勾，日历「日历」列表是订阅设置页（sheet/侧栏）不是图例。要「只看某一项」用点选（地点卡片上的主钮）；要「只看某几项」用列表多选（Kit Lists › Rows › Editing 圆勾，或每行 Toggle），放二级「编辑」页；分段控件用于范围（HIG Segmented controls：iPhone 以约五段为目标、宽界面五到七——是建议不是上限）。
2. **HIG 里没有「chips/胶囊筛选」组件**（那是 Material Design 的）。UIKit 的搜索令牌（UISearchToken）是苹果自己的形，但 iOS 27 Kit 没有 Token 画板——按「尺寸只从 Kit 取」，Kit 没画板的组件不做，先用有画板的等价物。
3. HIG 页面各自有修订日期（Toggles 2024-03-29、Lists and tables / Segmented controls 2023-06-21、Buttons/Toolbars 2025-12-16），没改的页是规则没变；引用时写页面名 + 原文句子，尺寸仍以 Kit（iOS 27 Sketch 2026-09-09 meta 196、macOS 27 2026-06-23 meta 190）为准，并用当前系统实机截图对照（macOS 27 日历侧栏复选框、Finder 設定 › サイドバー 混合态、iOS 27 日历「日历」sheet）。

## 代理规矩
1. 只改自己那页的 html（cost / osaka / japan / quiz+index）。hig.css 由本会话改好在前，缺类先问，不许页内自造控件样式。
2. 改完跑 `ACCEPT_BASE=http://127.0.0.1:8790 python3 pipeline/ui/kit-audit.py --mac <页>`，⚠/✗ 清零；再 `python3 pipeline/ui/accept.py` 那页不许退步。
3. 1440 和 375 各截一张全卡片图看一眼：没有被裁的字、没有叠在一起的行。
4. 功能一个不能少（65 条审查修复都在页里：钉住对比、换币、展开行、钉子弹出……），改样子不改行为。
