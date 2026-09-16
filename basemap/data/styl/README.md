# globe-key-numbers.tsv 怎么用（给界面会话，2026-09-16 数据会话）

来源：本机地图 App 的球样式表 `globe-default-20207.styl`（编译版 GeoCSS），用 `pipeline/basemap/styl/styl_decode.py` 解出（格式见根目录 `STYL-FORMAT.md`）。表里每行 = 一个样式在某个缩放段/条件下的一个属性值。列：`style, source(base|zoom|cond|cond+zoom), zoom(zmin-zmax), condition, prop_id, meaning, type, value`。

先记三条口径，否则数会对不上：
1. **颜色是样式表里的输入色（sRGB 8 位）**，渲染时还会过 `labelColorLumAdjustment` / `strokeColorLumAdjustment`（同一行组里的 463/464/470/471，单位是亮度百分点，正数提亮）和色彩空间转换；量具测的像素是输出色。暗色海洋标注 rgb(62,116,182) 与量具 #3d73b6 差 1，说明标注色基本不动；线条色叠了半透明描边再合成，会差一些。
2. **缩放段 zmin–zmax 是 MapLibre 的 zoom 同一口径**（Web Mercator z，苹果存 z×8）。首屏 `#ll=30,125&spn=50,60` 是 z3.1，落在 3–4 段。
3. 同一样式的缩放段可以重叠（几组各管不同属性），取值时按属性分别看；条件行（`client:37(~IncreaseContrast)`、`client:1(~TimePeriod)=[1]` 即夜间）只在该条件成立时覆盖基础值。**没有条件的 zoom 行就是默认（白天）值。**

## 各层对应的行

| 页面层（map/README.md） | 表里的样式 | 用哪几行 |
|---|---|---|
| 国界线 | `Border-Country-NonDisputed-Base`（线宽）+ `Border-Country-NonDisputed-Colors-Globe`（颜色） | 线宽 `3:width`：z0–2 0.9 → z4–5 1.1 → z5–6 1.45 → z6–8 1.55 → z8–10 1.75 → z10–12 1.95 → z12–14 2.1 px；套边 `6:strokeWidth` 从 z4 起 0.1 → 2.75。颜色：`1:fillColor` 灰组 z0–2 (188,188,188) → z2–4 (196,196,196) → z4–6 (200,200,200) → z6+ 白，`2:strokeColor` 同色 α 0.4→0.8；另一组紫 (56,19,51)→(77,26,70) 是 `Colors-Globe` 的夜间/混合球组（同表无条件，按 `-Globe` 样式的继承者分辨）。`0:visible=False` 于 z0–2：**球最远两级不画国界** |
| 争议国界 | `Border-Country-Disputed-*` | 同上加 `60:patternBits`/`279:dashPattern`（虚线，位型未拆） |
| 一级行政区界 | `Border-State-Globe-Colors-Base`、`Border-State.Globe` | 同结构 |
| 洲名 | `Continent-PointLabel-Base` + `Continent-PointLabel-Globe` | 字号 = `172:labelInfo.height`：z0–2 9 pt（曲线到 14）、z2–3 14 pt（到 20）、**z3 起隐藏**（`0:visible=False`）；球版本再乘 `18:textSizeScale` 1.2（z8+ 1.83、z11+ 2.2）；字体 `%$default,semibold,width=80`；色 (237,232,235) α0.98，光晕 (22,0,8) α0.85 |
| 国名 | `Country-Label-Base` 及 `Country-Label-{Small,Medium,Large,Extra-Large}-Base` | 基础 `172:labelInfo.height` 9 pt；Extra-Large 按缩放 z0–3 13 → z3–4 13→16 曲线 → z4–5 16→20 → z5+ 20 pt；字体 `%$default,bold-G3,width=80`；光晕 (248,248,246) α0.8；**z0–3 隐藏**（`0:visible=False` + `33:labelTextVisibility=0`） |
| 首都/城市名 | `CapitalCity-*`、`City-Style-0N` | 字号在 `172:labelInfo.height` 与 `21:fontSize`（12/13/18/20 pt）；用 `map/data/cities.geojson` 的 `globe_rank` 选点 |
| 海洋/海名 | `Ocean-Label-Base`（字体 `%$default,bold,italic`、`21:fontSize` 12、色 (231,252,255)）+ `Ocean-Label-Color-Globe-Base`（球上文字色 (170,224,235)）+ `Ocean-Label-Color-{Light,Dark}-Base` | 暗色：z0–2 (62,112,172)、z2–4 (62,116,182)、z4–6 (70,124,190)、z6–12 (68,126,197)；光晕 (19,31,73)。亮色基础 (35,35,35) α0.45–0.6 + LumAdjustment −20，量具 #206aa1 是叠加后的输出 |
| 湖/河名 | `Lake-Label-Globe-Base`、`Rivers-Globe-Base` | 文字色 (170,224,235)；河线 `Rivers-Line-Base` 宽 1.5 → z12+ 2.1 → 2.5 → 2.75 → z17+ 4.0 |
| 海岸线光晕 | `Coastline-Glow-Base`（宽）+ `Coastline-Glow-{Light,Dark}-Base`（色） | `55:coastlineGlowWidth`：z0–8 0（球上不画）、z8–10 5、z10–12 7、z12–14 8、z14+ 9 px（Muted/DarkMuted 变体 2.5–3.25）；亮色 `57:coastlineGlowColor` z0–8 (135,221,251)、z8–10 (130,218,247)、z10+ (138,218,244)；暗色 (34,59,135) 等 |
| 海底地名 | `PhysicalFeature-Undersea-*`、`PhysicalFeature-Rank-*-UnderWater*` | 点名 `24:textColor`/`25:labelHaloColor`；配 `map/data/undersea.geojson`（`cls` 1 = 海沟/深渊/海隆/海山链） |
| 交通色（以后路线页用） | `Traffic-on-route-{Light,Dark}-Base` | `90–93 trafficStopped/Slow/Medium/Fast.fillColor`：暗红 (104,23,37)、红 (239,56,57)、黄 (255,201,23)、蓝 (17,151,255)（亮色，on-route） |
| 路线线 | `Route-Line-Base-{Light,Dark}` | 亮 `1:fillColor` (0,162,255) / `2:strokeColor` (0,77,233)；暗 (25,128,255) / (54,158,255) |
| 混合球经纬网 | `Grid-GlobeHybrid` | `203:gridColor` (56,64,68) α0.4 |

球的**海面/陆地底色不在这张表里**（样式表没有面填充；见 STYL-FORMAT 第六节），继续用 `palette-ocean.json`/`palette-land.json` 的采样值。

## 重新生成

```bash
python3 pipeline/basemap/styl/styl_decode.py ~/Money/styl-work/globe-default-20207.styl --tsv basemap/data/styl/globe-default-20207.tsv
python3 pipeline/basemap/styl/globe_numbers.py basemap/data/styl/globe-default-20207.tsv basemap/data/styl/globe-key-numbers.tsv
python3 pipeline/basemap/styl/styl_decode.py ~/Money/styl-work/globe-default-20207.styl --show Country-Label-Extra-Large-Base   # 看全属性
```
全量表（每个样式全部属性）在本地 `basemap/data/styl/globe-default-20207.tsv`，不进仓库；@2x 版 `globe-default-21097@2x.styl` 的线宽/字号系数另有一套（STYL-FORMAT 第四节），Retina 屏对照时用它。
