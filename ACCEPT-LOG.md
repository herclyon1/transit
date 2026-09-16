# 验收记录

> 规矩（2026-09-16 用户定）：任何一方做完 → 发另一方验收 → 通过才合 main；用户抽查，效果差追责验收人。每条必须写：日期、分支/提交、看了哪个状态、对的是 Maps 哪张图（自己截的）、不一致项、放行/打回理由。
> 环境与流程见 WORKFLOW.md（目录、分支、端口、锁、交付步骤）。

## 2026-09-16 09:3x　验收 interaction 44e5348（含 d4125bd）　验收人：money 会话

**看了什么**：本地起 transit-wt（interaction）rangeserver 8791，浏览器视口 1280×744。
- cost 页：侧栏 + 大阪城市卡（z4 国家尺度）。对照：Maps.app 窗口 4961 我自己截的 Osaka Station 地点卡 + 国家尺度（scratchpad 08:3x 首张 app_screenshot；Map Modes 弹窗 `maps_map_modes_transit.png` / `maps_map_modes_satellite.png`）。
- osaka 页：右上「地图模式」弹窗（Mac）。对照：同上 Map Modes 两张。

**量到的（computed style / getBoundingClientRect）**：
| 项 | 分支现值 | Maps 实测 / 提交声称 | 结论 |
|---|---|---|---|
| 地点卡材质 | 白 86% + blur 40 + sat 1.8，320×728 @(208,8) | 声称一致；位置尺寸同 Maps 地点卡 | 一致 |
| 卡底工具条 | 36 高，3 颗 28×28 | Maps 288×36 @底 3 颗 28 | 一致 |
| 侧栏行 | 32 高两行 + 选中 aria-current + 右侧灰数字 | Maps Recents 行 32 两行 | 一致 |
| 底部链接 | 「目录」灰 (60,60,67,.3) 11px @(16,717) | Maps「Terms & Conditions ›」灰 11 @(16,底 13) | 一致 |
| **侧栏材质** | **#ececec 63% + blur 60 + sat 1.45**（`html .glass` 规则压过了 `.sheet` 的 78%/40/1.8，元素是 `.sheet.glass.split`） | 提交声称 白 78% + blur 40 + sat 1.8 | **不一致 → 打回**（选择器优先级，声称的值没生效） |
| osaka 地图模式弹窗（Mac） | 标题居中 + × ；3 个 tile 单选；白盒 3 行左侧勾选框 16；说明段 + 出处 | Maps：tile 单选；白盒左侧勾选框（我截图量约 23–24 pt）；2 行；出处 | 形一致；**勾选框 16 vs 实机 ≈23**，要么按实机改要么写明取 Kit 16 的理由 |
| 开关行标签 | 低频线 / 枢纽标记 / 居住等级标注，无 ⚡ 无括号 | 44e5348 声称 | 一致 |

**结论**：打回。两处：① 侧栏材质选择器；② 勾选框尺寸对不上实机（定一个）。其余放行。
**没做到的验收步骤**（如实写）：浏览器视口截图没落盘（浏览器面板不支持区域缩放），以上用的是元素实测值；Maps 参照图是我 08:3x 自己截的，状态 = Osaka Station 卡 + 国家尺度。

## 2026-09-16 09:5x　复验 interaction 5a15ae7　验收人：money 会话

- 侧栏材质：`html .sheet.glass` 生效，computed = rgba(255,255,255,.78) / blur(40px) saturate(1.8) → **一致**。
- 勾选框：我按自己截的 `maps_popover2_crop.png`（@2x）逐像素量，Traffic 框 32×30 px ≈ 16 pt——**上一条我写的「≈23–24」是错的，撤回**；分支 16×16 @ 行内 x16 → 一致。
- 弹窗材质 白 70% + blur 40 + sat 1.8，320 宽 @ x696 → 一致清单 #26。
- 行高：分支 48；Maps 弹窗白盒两行按发丝线量约 45–46 pt（crop y 300→388→480 @2x）。差 2–3 pt，**放行但记下**：下次提交按实机再量一次定 45/46/48。
- 结论：**放行，合并 main**。

## 2026-09-16 12:3x　验收 ui e27b07b（苹果渲染器当量具：海色/陆色/标注三表）　验收人：transit 验收（Fable）

**看了什么**：ui 分支 e27b07b，9 个文件 +33 886 行；ui/basemap/{palette-ocean,palette-land,labels-globe}.json + README，pipeline/basemap/ 5 个脚本。不含页面。按 WORKFLOW 第四节第 7 条「数据验收四条」验。

| 条 | 怎么验 | 结果 |
|---|---|---|
| ① 来源与口径 | 三个 json 的 `sources` 都写了渲染器参数（视野 ll=30,125 spn=50,60 @1280×744、macOS 27.0 26A428、渲染时刻、sha256）、Natural Earth 10m bathymetry v4.1.0 URL、AWS terrarium URL、groundSettings.json 路径、native.png | 齐 |
| ② 抽值回源 | 我用自己的 snap.swift 同参数重渲亮/暗各一张，随机抽 5 个海样本 + 3 个陆样本，在同像素取中值对它记的 RGB：亮 Δ≤2、暗 Δ≤2（3×3 中值）。再抽 2 个海样本自己拉 terrarium 5 级瓦片算深度：−77 m / −49 m 与它一致到米，瓦片号和像素位一致 | 对上 |
| ③ validate.py | 不覆盖这类文件，跳过 | — |
| ④ 计数 | 海样本 200、陆样本 705、标注 22 条、海深档 11，与消息一致 | 对上 |

**另核**：native.png 右侧 gutter 最常见色 (0,0,0) 116/156 → 「太空纯黑」成立；我渲染图上 MONGOLIA 字的最深像素 (148,93,141)=#945d8d，它拟合的国名色 #8c608a，Δ≤8，属抗锯齿字芯的正常差；蒙古一带地表色 #e1eda7 在我图上是该区最常见色，与「半湿 #e1eda7」一致。

**不一致 / 记下**：陆样本没有 `tint_class` 字段（分类只在 `tints` 汇总里，样本级看不出归哪类，下次补）；宽视野标注是 1x 量的（±0.35 pt），json 已注明。

**结论**：放行，合并 main。渲染图不进仓库（苹果图），json 里参数与 sha256 可复现。
