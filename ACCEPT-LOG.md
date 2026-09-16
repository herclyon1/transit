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

## 2026-09-16 13:4x　验收 ui 98c0d1a（第 0 步：只有球的页面 map/）　验收人：transit 验收（Fable）

**看了什么**：`git merge --no-commit ui` 进 main 树，起 8791，内置浏览器 1280×744 开 `map/index.html#3.12/33.48/125`（东亚，等价 ll=30,125 spn=50,60）和 `#2.3/20/140`（全球），亮/暗各一张，共 4 张。对照：地图 App 原生球截图 `~/Money/styl-work/native.png`（同东亚视野，11:0x 我自己截的）。

**像不像（陌生人三秒）**：亮色东亚视野一眼是苹果的球——黑太空 + 星点 + 球边光晕、海深分层、陆地气候色、国名紫色大写、海名蓝斜体、SF 系字体。**方向对，放行。**

| 项 | 页面 | App 原生 | 结论 |
|---|---|---|---|
| 太空/星/光晕 | 纯黑，星点，球边灰蓝雾→黑 | 同 | 一致 |
| 海深分层 | 12 档，平面调色板（#6cc9fa→#0d8de6） | 球用另一张样式表，海更浅更灰（菲律宾海 (121,189,233) vs 页面 (10,149,233)） | **不一致，已知**（界面会话自己报的）：球的海色要单独采 |
| 陆地色 | Köppen 分区 → humid/semi/dry/very_dry/high_grey | 同类色，App 纹理更细 | 近似，可接受 |
| 山影 | terrarium，方位 260°，幅度校准过（14.2 vs 14.3） | 同 | 一致 |
| 标注 | 洲/国/海名，字号字距颜色照 labels-globe.json | App 还有城市名（Tokyo/Beijing…）和深渊名 | 缺城市名（不在本单范围）、缺深渊名（NE 无点数据，已注明） |
| 球半径/相机 | 536 px（按快照器整区规则 fit） | App 球更大（右缘到窗口边） | 不一致：App 的球相机不是快照器规则，下一单按 native.png 城市点位拟合 |

**缺陷（下一单先修，再做别的）**：
1. 暗色全球视野：VIETNAM / INDONESIA 两个标注画在球外的太空里（背面点没剔除或投影出圈）。
2. 暗色东亚视野：「Arctic Ocean」标注落在黄海位置（跨极海域多边形取质心错）。
3. 同一 hash 亮/暗两次加载标注集合不一样（暗色东亚只有 ASIA/RUSSIA/INDIA/CHINA），疑似标注在数据加载完成前就做了避让；东亚视野首次 8 秒内海深也没画出（12 MB GeoJSON），要有加载完成再布标的顺序。

**没做到的验收步骤**：内置浏览器截图不落盘；无头 Chrome 落盘渲染还在跑，出来后补一张并排图到 accept/。暗色没有 App 原生球截图可对（App 暗色球要另截）。

**结论**：放行合并（map/ 独立目录，不影响任何旧页）；上面 3 条缺陷记为下一单第一项。

## 2026-09-16 14:0x　验收 data bcea8d0 + c832a8f + da130f7（.styl 格式与球数值表）　验收人：transit 验收（Fable）

**看了什么**：`git diff --stat main...data`：12 文件 +7506，无删除（两点 diff 里的 ui/basemap 删除是分支落后 main 的假象）。STYL-FORMAT.md 八节；解码器 pipeline/basemap/styl/；数值表 basemap/data/styl/globe-key-numbers.tsv 5246 行；20 MB 全量导出已 gitignore。

| 条 | 怎么验 | 结果 |
|---|---|---|
| ① 来源与口径 | 文档写明样本路径、解法依据（本机 VectorKit 反汇编 + 26.1 反编译）、颜色是 sRGB 8 位输入色、流序 A,B,G,R、1x/2x 差异 | 齐 |
| ② 抽值回源 | 我把 `git archive data pipeline/basemap/styl` 抽到 /tmp 独立跑 styl_decode.py：球文件 5 章、属性 210、属性集 3200、样式 2421，20 章剩 6 位 / 21 章剩 2 位，与报告一致。字节序 A,B,G,R 与我 13:2x 用渲染像素互证的结论独立一致（它走反汇编）。字号：Continent-PointLabel z2–3 由 14 曲线到 20，界面会话在东亚视野实测洲名 17.4 pt，落在曲线段内（MapKit 缩放约 2.7），两把尺子对上。Coastline-Glow-Light 57 = rgb(135,221,251) 对我渲染近岸 #88d4f5 | 对上 |
| ③ validate.py | 不覆盖 | — |
| ④ 计数 | 425 属性有映射、球文件定名 100/210（定死 64 + 推断 36，high 19）、tsv 5246 行 | 与消息一致 |

**两项裁定**：① 球的海/陆底色不在样式表（球文件无面填充样式，match_palette 全部落空）→ 继续走渲染器/App 截图采样，这条转界面会话（已在它下一单里）。② 20 MB 全量导出不进公开仓库（苹果样式逐值），维持 gitignore，本地重生成。
**记下**：30 章匹配树、dashPattern/iconGradient 内部布局、约 110 个低频属性未定名——同意到此为止，不再投格式。

**结论**：放行，合并 main。

## 2026-09-16 14:2x　验收 ui ab63014（球页面缺陷 1–3 修复）　验收人：transit 验收（Fable）

**看了什么**：`merge --no-commit ui`，8791，1280×744，暗色 #2.3/20/140、暗色 #3.12/33.48/125、亮色 #3.12/33.48/125，各等 16 秒。
- 缺陷 1 标注出圈：**修好**，VIETNAM/INDONESIA 在球内。
- 缺陷 2 Arctic Ocean：**没好**，亮暗两张东亚视野里仍落在黄海位置。
- 缺陷 3 标注集合：**更差**，东亚视野亮暗都只剩 ASIA/RUSSIA/INDIA/Arctic Ocean 四条（上版二十多条）；它报「暗色 37 条」与截图不符，以截图为准。
**结论**：打回（2、3）。`git merge --abort`，main 不动。App「球边压陆地」参照图已截：`~/Money/styl-work/native-limb-land-light.png`（1280×744 pt @2x，`maps://?ll=30,60&spn=50,60`）。

## 2026-09-16 14:4x　验收 data f36afaa（球页面数据：海深三级 / 海底地名 / 城市点 / 数值表说明）　验收人：transit 验收（Fable）

| 条 | 怎么验 | 结果 |
|---|---|---|
| ① 来源与口径 | map/data/meta.json sources 九项齐（bathymetry_levels/undersea/cities 新增），三个脚本头部有 URL；NE 10m Bathymetry v4.1.0、GEBCO Gazetteer（NOAA NCEI ArcGIS 服务）、NE 10m populated places v5.1.2 | 齐 |
| ② 抽值回源 | Challenger Deep rep (142.5917, 11.3733) 对 GEBCO 辞典 11°22.4′N 142°35.5′E = (142.592, 11.373)；Emperor Seamount Chain / Shatsky Rise / Mariana / Japan Trench 为线要素，代表点在合理位置；Tokyo (139.7495, 35.687)、Ōsaka (135.5038, 34.6911) 与 NE 一致，name_ja 有 | 对上 |
| ③ validate.py | 不覆盖 | — |
| ④ 计数 | bathy-z0 12 要素 40 265 外环顶点、bathy-z4 12 要素、深度档 0–10000 共 12；undersea 1479 = cls1 468 + cls2 1011；cities 1148 = 68/174/331/575 | 与消息一致 |

**记下**：Ramapo Deep 在 GEBCO 辞典里没有（只有 Ramapo Bank），App 那条标签无公开来源，页面上不做；pmtiles 没做（本机无 tippecanoe），三级 GeoJSON 先用。
**结论**：放行，合并 main。

## 2026-09-16 14:5x　验收 ui 70f9ef0（球调色板 + 含 ab63014 缺陷修复）　验收人：transit 验收（Fable）

**看了什么**：`merge --no-commit ui`，8791；浏览器面板未显示（桌面 app 窗口不在前台时页面不合成），改无头 Chrome 1280×744 落盘：`#ll=30,125&spn=50,60` 亮、`#2.3/20/140` 亮（scratchpad g70-*.png）。对照 native.png（App 球，同东亚视野）。

| 项 | 怎么验 | 结果 |
|---|---|---|
| 球轮廓拟合 | 我在 native.png y=743 行从右扫第一个非黑像素 x=2435 → 半径 1170 px；它拟合 1156.3 + 14 px 光晕 = 1170.3 | 一致 |
| 球海色 | 我在 native.png 菲律宾海 (1716,1010) 取中值 #74b8e6，它 5000–6000 m 档 centre #77bce9 / #75b9e9；孟加拉湾 #a2d7f7 对 1000–2000 m 档 #a9d6f1 | 对上（Δ≤4） |
| 缺陷 2 Arctic Ocean | 东亚视野渲染图上黄海处已无该标注 | 修好 |
| 缺陷 3 标注集合 | 东亚视野 15 条（KAZAKHSTAN/ASIA/CHINA/JAPAN/SOUTH KOREA/INDIA/VIETNAM/THAILAND/PHILIPPINES + Sea of Okhotsk/Sea of Japan/Bay of Bengal/South China Sea/Philippine Sea） | 修好 |
| 整体 | 东亚视野与 native.png 并看：球大小、浅蓝海、淡绿陆、紫色国名、蓝斜体海名，三秒像 | 放行 |

**未验/记下**：全球视野 `#2.3/20/140` 无头渲染里一条标注都没有（可能是无头虚拟时间下 idle 未触发），要在面板可见时用真浏览器再看一次；暗色只有平面暗色（缺 App 暗色球截图，我这边不能切系统外观）。

**结论**：放行，合并 main。

## 2026-09-16 15:0x　验收 ui ffee181（缺陷 2、3 复验）+ 更正上一条 ab63014 的打回　验收人：transit 验收（Fable）

**更正**：ab63014 那次打回（14:2x）是我验错了。当时用桌面浏览器面板截图，globe.js 走了 HTTP 缓存（旧 JS + 新 labels.geojson），正好复现出 98c0d1a 的症状（4 条标注、Arctic 在黄海）。界面会话用同一工具在 ab63014 上得 24/24，我这次也复现不出。**以后验收一律全新浏览器配置 + `?v=<提交号>` 防缓存。**

**ffee181 复验**（`merge --no-commit ui`，8791，用它的 pipeline/basemap/count-labels.sh = 无头 Chrome DPR2、新开页、等 16 s、数 DOM 可见标注）：
| 视野 | 可见/总 | Arctic Ocean | 说明 |
|---|---|---|---|
| 亮 #3.12/33.48/125 | 24/141 | hidden，投影 (666,−166) 屏外 | 与它报的 24 条集合一致 |
| 暗 #3.12/33.48/125 | 24/141 | hidden | 集合与亮色完全相同 |
| 亮 #3.285/30.18/116.15（东亚对位视野） | 28/141 | hidden | 多出 Uzbekistan/Pakistan/Afghanistan/Sri Lanka |
缺陷 2、3 修好。**放行，合并 main。**

**干净比对（用户要求：App 关侧栏、同缩放同位置）**：App 侧栏用工具栏钮关掉后截 `native-nosidebar.png`（`maps://?ll=30,125&spn=50,60`，1280×744 @2x）；我们用 `#3.285/30.18/116.15`。球：App 圆心 x 639.5 半径 577.5，我们 639.5 / 571.5。全图色差>40 像素 13.3%（海面 19.1%、陆地 11.9%）。差异图（styl-work/cmp2-diff.png）里白块集中在：① 0–200 m 陆架海（黄海、东海、巽他陆架、孟加拉湾近岸）App 明显更白更亮；② 深海沟脊的地形纹理（App 更细）；③ 球缘雾化带（App 更宽更亮）；④ 标注（App 有城市名/深渊名/山脉名/回归线，我们只有洲国海名）。几何对位本身没有问题。

