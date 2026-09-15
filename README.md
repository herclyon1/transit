# 地図ツール

https://herclyon1.github.io/transit/

给自己用的一组地图：学日本和东亚的行政区划、在大阪选房、比较各城市外国人的真实收入与开销。

**先读 [IDEAS.md](IDEAS.md)**：每个功能为什么存在、用户定下的规则、已证伪的路。代码可以推倒重来，那份不能。
待办在 [TODO.md](TODO.md)。

## 目录

```
index.html        首页，卡片式入口（按"打开它是为了做什么"分，不按地图种类分）
japan/            地図·学習：現代日本四级下钻 + 東亜 27 国，MapLibre + pmtiles
quiz/             都道府県クイズ：47 県背诵工具（旧版 D3 页面，将来重做进 japan/）
osaka/            大阪·居住：找住处——目的地→通勤时间档→房租档（MapLibre GL）+ 作者标注的居住等级面层（data/tiers.geojson）
cost/             薪資·購買力：世界地图打点，每城一张卡（MapLibre + 本地 Natural Earth）
tiles/            全部 pmtiles 瓦片 + NotoSansJP 字形（0–65535 全 256 段）
vendor/           本地化的库：maplibre-gl、pmtiles、d3 7.8.5、topojson 3
ui/               全站共用的界面层（DESIGN-HIG.md）：hig.css 数字、hig.js 符号/开关/菜单、sheet.js Sheet 物理、press.js 按下态、shell.js 地图壳骨架（地图 + Sheet + 地点卡片，页面只给 layers()/card()）、accept.js 验收探针
pipeline/japan/   東亜 / 現代日本 数据管线（OSM → 裁剪 → 切瓦片），README 记录每一步为什么必须这么做
pipeline/osaka/   大阪可达性管线（OSM route relation → 拓扑 → 时间层 → Dijkstra → reach.json）
pipeline/test/    真人手势验收脚本（Playwright，手机视口 + 4x 降速）
clawd/            首页螃蟹，Anthropic 官方素材原样引用
```

每张卡自带自己的运行时数据（`*/data/`）；管线的输入和中间产物只在 `pipeline/` 里。
外部依赖只剩国土地理院瓦片（底图，官方免费无 key）。

## 各页面

### japan/ 地図·学習
- 現代日本：都道府県 → 市町村 → 政令市の区 → 町丁・字等（令和2年国勢調査小地域，带人口世帯）。
- 東亜：27 国 621 个一级行政区，越南、缅甸再下钻一级；铁路・空港・港湾・口岸・定期航路；高速公路。
- 底图：地理院 淡色／写真／標高 三选一。
- 数据：OpenStreetMap、国土数値情報 N02/C28/N09/S12、e-Stat、OSM 陸地ポリゴン、Geofabrik 提取包。
- 归属规则：填色按实际管理，官方划法虚线叠加。国家色取各国自己声明的代表色。

### quiz/ 都道府県クイズ
- 浏览／闯关／混考／大日本／東亜 五个模式。県界用 smartnews japan-topography s0010 的本地副本。
- 東亜和大日本两个浏览模式已被 japan/ 覆盖，留着只为闯关和混考；重做后整页删除。

### osaka/ 大阪·居住
- **用法（找住处）**：先选目的地（梅田／難波／天王寺／京橋，或四枢纽都看），再拖能接受的通勤时间（15–40 分），地图只画满足条件的车站；点车站看它到各枢纽的分钟数和落在哪一档（步行圈／15／25／40 分）、那一档的单间月租（SUUMO 在挂 1R/1K 的下四分位，来自 `cost/data/cities/osaka.json`）。长按地图任意处可算「步行到最近几个站 + 轨道」。
- 点层数据：`data/reach.json`，纯轨道站到站时间 + 换乘罚时，A/B 双频度层（⚡ 低频线、💴 需特急券），面覆盖用实路网步行等时圈。初始视图点画 8 px、缩到 12.5 级才满尺寸，12 级以下同一格只画枢纽最多/最快的一站，放大再出现（2026-09-16 用户：「点全挤在一起」）。
- **居住等级面层 = 作者标注**（印象分）：104 块的 S–D 没有一块有出处（`data/README-tiers-audit.md`）。三维度数据分（治安 = 府警刑法犯／千人、便利 = 门到枢纽分钟 + OSM 超市、环境 = 国交省洪水浸水想定占比）已在 `data/tiers_scored.json` 算好，与现等级的相关只有便利那项（ρ +0.35），治安、浸水基本无关；用哪种合法、治安分母用常住还是昼间人口，待用户拍板后一条命令写回。
- 按站房租：`pipeline/osaka/suumo_station_rent.py` 已能按站取 SUUMO 賃料中位/下四分位（`data/station_rent.json`），全站抓取等用户点头；数据文件一览见 `data/README.md`。
- Mac 布局按 macOS 27 地图 App 的组合：左侧栏通高、地点卡片浮在地图上、右侧竖排控件，尺寸取自 UI Kit 和辅助功能树实测（`ui/DESIGN-HIG.md`、`KIT-MAP.md`）。
- 底图：地理院淡色地図；暗色主题用 CSS 反色滤镜。

### cost/ 薪資·購買力
- 世界底图：Natural Earth 110m（低缩放）/ 50m（放大）国界，本地文件，不依赖任何外部瓦片；字形复用 tiles/glyphs。
- `data/cities.json` 决定画哪些点；`data/cities/<id>.json` 一城一份，点开才加载；数字格式与置信度规则见 `data/README.md`。
- 页面不写死任何数值；`value` 为 null 显示「暂无」。汇率表 `data/rates.json` 为空时只显示当地货币。
- 饮食费分两态：**在岗**（进公式）= 一周五天有班、全外食，工作日一顿最便宜定食 + 员工餐，周末两顿外食，加可乐；**过渡期**（只展示）= 国民健康・栄養調査 20–29 岁男性每日克数 × 当地买菜平台现价 + 调料 + 瓶装茶（太贵退自泡）+ 可乐。个人参数在 `data/personal.json`，推导在 `data/FOOD-MODEL-DRAFT.md`。

## 怎么验证（改完必跑）

1. 本地起一个**支持 HTTP Range** 的静态服务器（pmtiles 按字节范围取，`python3 -m http.server` 不支持 Range 会报 content-length 错），逐页打开 `/`、`/japan/`、`/quiz/`、`/osaka/`、`/cost/`。
2. 控制台零错误、零 404。MapLibre 页面改完样式必须查 `map.getStyle().layers.length`（一个非法表达式会让整份样式不加载，页面全白）。
3. 明暗主题各测一遍；手机视口（390×844）面板不遮滑块。
4. 手势类改动跑 `pipeline/test/usersession.js` 和 `pinch.js`，逐张看联系表，红线清单在 `pipeline/test/README.md`。
5. 重切瓦片必须改 `japan/index.html` 里的 `?v=` 版本串，否则浏览器按 Range 缓存旧文件的片段，表现为"标注在、边界整片消失"且不报错。
6. 字形必须 0–65535 全 256 段都有。缺一段，整张矢量瓦片解析失败，那一片什么都不显示。

## 已知偏差（不打算改，理由见提交记录）

- 北方領土的 6 个村不在市町村层，按"填色按实际管理"画在 disp 层。
- 米原市由町丁合并而来（OSM 关系建不出多边形），与邻市 0.1% 量级重叠。
- 11 个市区町村面积仍超官方 ±5%（高石市填海地、根室市北方領土、田尻町関空、小笠原村离岛等），再压会误删有人口的町丁。
- 可达图 82% 的站到枢纽时间是 borrowed 级速度（実測 15%、锚定 3%），精度升级方案见 TODO。

## 数据来源

OpenStreetMap（ODbL）· 国土数値情報 · 令和2年国勢調査（e-Stat）· 国土地理院（地理院タイル、面積調）· OSM 陸地ポリゴン（osmdata.openstreetmap.de）· geoBoundaries · FOSSGIS Valhalla（步行等时圈）· smartnews-smri/japan-topography · Wikipedia（優等停站型、National colours）
