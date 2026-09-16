# globe-key-numbers.tsv 怎么用（给界面会话，2026-09-16 数据会话）

来源：本机地图 App 的球样式表 `globe-default-20207.styl`（编译版 GeoCSS），用 `pipeline/basemap/styl/styl_decode.py` 解出（格式见根目录 `STYL-FORMAT.md`）。表里每行 = 一个样式在某个缩放段/条件下的一个属性值。列：`style, source(base|zoom|cond|cond+zoom), zoom(zmin-zmax), condition, prop_id, meaning, type, value`。

先记三条口径，否则数会对不上：
1. **颜色是样式表里的输入色（sRGB 8 位）**，渲染时还会过 `labelColorLumAdjustment` / `strokeColorLumAdjustment`（同一行组里的 463/464/470/471，单位是亮度百分点，正数提亮）和色彩空间转换；量具测的像素是输出色。暗色海洋标注 rgb(62,116,182) 与量具 #3d73b6 差 1，说明标注色基本不动；线条色叠了半透明描边再合成，会差一些。
2. **缩放段口径：苹果 z = MapLibre z + 1**（苹果按 256 px 瓦片算 zoom，MapLibre 按 512 px；苹果存 z×8）。验收视野 `#ll=34.69,135.50&spn=0.12,0.2` @1280×744 是苹果 z12.8 = MapLibre z11.8；首屏球 `#ll=30,125&spn=50,60` 是苹果 z4.1 = MapLibre z3.1。查表时把 MapLibre 的 z 加 1 再找段（`to_maplibre.py` 已按 −1 位移生成）。
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

## 平面样式生成器（2026-09-16 下午，`pipeline/basemap/styl/to_maplibre.py`）

v6（2026-09-16 晚，按 RENDER-PIPELINE §7.12）：虚线按缩放段（279/280 各行）出 `step` 表达式，单位 = 0.2 pt（§7.16 三次实测，不是 ¼ pt），除以该段线宽；海岸光晕层 `coast-glow`（Coastline-Glow-Base 宽 55 / 颜色 57，画在 OpenMapTiles ocean 多边形轮廓上、`line-offset` 向水侧，苹果 z8 起）；字体按缩放段（fontSpec 23 各行 → `text-font` step）；resolve.py v6：菱形继承取最后一次出现（LowZoom 基类压过 JPN 宽度表）、条件行按 CONTEXT（client:69=2、TimePeriod 亮 0/暗 1、Country=10）求值，未知特征属性的条件行跳过；高速 z6–7 0.5 px 由解析器自己给出，z6 以下不画、z7–8 1 px 灰是 feature:85 行（OpenMapTiles 没有苹果的低缩放连接类，§7.15）；经纬网 `geoline-tropics/-equator` 读 `map/data/graticule.geojson`，样式 Geolines-Tropics/Equator（§7.13）。v6.1（验收记下两项后查表回填）：① 县界属性 12=0.25 仍作 line-opacity（v6 一度去掉；z6 局部对照 App 是淡紫灰 = (179,0,158) α0.8×0.25，表里的 fillColorLumAdjustment −10 只会更深，不是它）；② 279 整线虚线也套到套边上（280 只虚描边=铁路刻度）——新幹線 z6–8 白芯 + 0.5 px 蓝边一起断成 [28,28]×0.2 pt 的淡蓝虚线，之前套边整条实蓝、白芯断开看起来是亮蓝粗虚线。指标（v6.1）：大阪 z12 亮 7.31% / 暗 8.12%（v5 当日重测 7.08%）；日本视野亮 68.34% / 暗 32.83%（绿色植被归界面叠层，线与字见 `~/Money/styl-work/cmp-v6-japan-light-side.png`）。

```bash
python3 pipeline/basemap/styl/to_maplibre.py ~/Money/styl-work/default-56689.styl map/style-flat-light.json map/style-flat-dark.json   # 加 --lum 试亮度调整
python3 pipeline/rangeserver.py 8793 &   # 预览 http://127.0.0.1:8793/map/flat.html?dark=0#ll=34.69,135.50&spn=0.12,0.2
```
- **变体：默认取 `-Elevated` 叶样式**（Mac 地图 App 和 MKMapSnapshotter `elevationStyle: .realistic` 画的是这套：高架高速紫色 (185,174,209)/(137,123,166)、地面 Landcover-Ground (247,246,242) 而不是 LandPolygon (245,242,234)；验收并排图直方图里的紫路与地色就是这两个数）。`--flat` 换回 Explore/Light 平面变体（.flat）。
- 输入：**`default-56689.styl`（iOS 版）**。Mac 版 `default-iosmac-11358.styl` 颜色、缩放段完全一样、尺寸 ×1.2987，但 Mac 是按 77% 画的，像素输出 = iOS 表值：验收并排图实测阪神高速 ≈5 px = iOS 3.75 + 2×0.5、区名大写字高 12 px = iOS 16 pt、铁路 1–2 px = iOS 1.0（v4 之前用 iosmac 所以线粗 1.3 倍、字大 1.3 倍）。亮/暗是同一文件里的 `.Light*` / `.Dark*` 叶样式；解析用 `resolve.py`（继承链先父后子、后者覆盖，缩放段「后者优先」）。
- 数据：OpenFreeMap `planet`（OpenMapTiles 字段），字体只有 Noto Sans Regular/Bold/Italic（medium→Regular、semibold→Bold、bold,italic→Italic）。
- 映射表 `map/style-flat-mapping.tsv`（80 行）：每个 MapLibre 图层对应哪个苹果叶样式，「inferred」标出的是我推的（motorway→FreewayControlled、trunk→MajorHighway、primary→Highway、secondary→ConnectorRoad、tertiary→LocalMajorRoad、minor→LocalRoad-MinorRoad、service→ServiceRoad、path→PrivatePath、日本路网用 `.Light-JPN`；城市标注按 OpenMapTiles rank 对 City-Label-LMZ-05/07/09/12；区名 SubMuni-Ward；湖名 Lake-Label.Zoom9；海名 Ocean-Points.Large）。
- 取值：fillColor/strokeColor→颜色（按缩放段 step），width→line-width，套边 = width + 2×strokeWidth 画在下层，visible=False 段→minzoom，边界属性 12→line-opacity（推断为不透明度 0.25），labelInfo.height→text-size（段内从 height 线性到 heightCurveLimit），文字色/光晕色照搬，建筑面用 buildingFlatColor(86)，dashPattern 279/280（小端 u16 的 (dash,gap) 对，单位 pt；铁路 4,48、国界 18,4,10,4,4,4）→line-dasharray（除以苹果 z13 的线宽）。所有缩放刻度已按「苹果 z = MapLibre z + 1」位移。
- 国道紫线：苹果 `Line-*.Light-JPN-ClassOne`（填充 (185,174,209)/套边 (137,123,166)，缩放段见表）；OpenFreeMap transportation 层没有 ref/network，改在 transportation_name 层（带 name/ref 的路线几何）上按 `name` 前缀「国道」画（`road-kokudo` + 套边），叠在普通道路之上。府道苹果没有单独样式（JPN 只有 ClassOne），走普通 Highway。
- 区名 `label-ward`：SubMuni-Ward 可见段苹果 z10–14 → MapLibre 9–13（minzoom/maxzoom 都从 visible=False 段推，v2 只推了 minzoom 所以没出）。规格（Mac z13.2）：labelInfo.height 20.8（z12–13 段 18.2→20.8 曲线）、`%$default,semibold,width=60`（60% 宽的窄体，我们只有 Noto Sans Bold）、色 (90,94,94) 无光晕；验收并排图里苹果 NISHIYODOGAWA 的字色采样正是 (90,93,93)，大写字高 12 px ≈ 16–17 pt，比 20.8 小 0.8 倍——差在哪没找到（textSizeScale 18 = 0.5 会得 10.4，对不上；LumAdjustment 对字色也没生效），换用 iOS 文件后表值就是 16 pt（z13 段 16→18 曲线），与实测一致，不再需要手改；字体：semibold width=60 是窄体，映射到 Noto Sans Regular（OpenFreeMap 没有 Medium，Bold 太重）；暗色 (200,214,231)；uppercase + letter-spacing 0.1。
- 道路名密度：symbol-sort-key 按高速>主干>次干>支路，支路名 minzoom 提到 MapLibre 14（验收定的，不是苹果的数）。
- 道路名：labelTextVisibility(33) 不能当开关——高速全程 33=0 但苹果照样标名（HANSHIN EXPRESSWAY…），所以没用它收紧；密度差是苹果标注器的取舍（避让/优先级），不是样式表里的数。
- 铁路（2026-09-16 晚改）：不再用 OpenMapTiles 的 rail（OSM 每股道一条线，复线站场画成 2–3 px），改用仓库已有的 `tiles/transit.pmtiles` 的 `rail` 层（国土数値情報 N02-24 RailroadSection，一条线路一条中心线，`pipeline/japan/build_transit2.py` 切的；样式 JSON 多一个 `transit` 源 `pmtiles://../tiles/transit.pmtiles`，页面要注册 pmtiles 协议）。`cls` jr/private/sector3/public/other/tram → Railway-Japan（(113,167,255) 宽 1.0 + 4/48 刻度套边，z6 起），shinkansen → Railway-Japan.Bullet（蓝边 (0,111,255) + 白芯 48/48 虚线）；subway/mono/cable 不画（苹果标准图也不画）。同视野铁路同色横向连续像素从 2–3 px 回到 1–2 px；cmp-accept 大阪亮 7.08%、暗 7.91%。暗色铁路 (35,48,69) 在 (55,72,93) 陆地上就是苹果的数。
- z5–8 日本全国视野（`#ll=36,138&spn=12,16`，苹果 z6.1 / MapLibre 5.1）：县名用 State-Label-Small（苹果 z7–10 可见，Medium 会在这一级冒出 41 个县名而苹果一个不画）；国名/县名 Latin 大写加字距；ResidentialPolygon-TintBand 不能当面填充（在 z5 把居住区涂成紫色斑块，已去掉——苹果的 TintBand 是沿边缘的渐变带）。**对不上的**：① 高速在苹果图里 ≈1 px 淡紫，表值 z6–8 段是 2.25 + 2×0.4 套边，差在哪没查到；② 苹果的绿色地形/海底分层是渲染器贴图（Elevated 的 Landcover 与 bathymetry），不在样式表，球页面已用气候栅格与海深层；③ 城市点（圆点图标）没画；④ 苹果图是英文标注（系统语言），我们 name:ja 优先。
- 没做：隧道/桥（`brunnel`）、匝道（Ramp-*）、盾牌、POI、LumAdjustment 的精确函数（`--lum` 用 HSL 亮度 ±adj/100 近似，默认关）、z17+ 的宽度（苹果换成地面单位，数值 30/60/120 不能直接用）。
- **数据侧硬限制（并排图路网稀的主因）**：OpenFreeMap 瓦片 z11 里 transportation 只有 motorway/trunk/primary/secondary/tertiary/rail，`minor`（支路，z12 瓦片起，大阪一屏 8185 条）和 place 的 `suburb`（区名，z12 起，142 个）都没有；MapLibre 在 z11.8 取的是 z11 瓦片（矢量源只能 512 px、取整向下），所以验收视野 z11.8 画不出支路网和 YODOGAWA/ASAHI 区名，z≥12 才有。要对比全部支路请用 z12.2 的视野（spn≈0.09,0.15）。
- 自检图：`pipeline/basemap/raw/flat/osaka-{light,dark}.png`（无头 Chrome，同视野 1280×744），验收拿 MKMapSnapshotter 同视野并排。
