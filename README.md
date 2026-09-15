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
osaka/            大阪·居住：车站可达性图（MapLibre GL，2026-09-15 从 Leaflet 换过来）+ 居住等级面层（data/tiers.geojson）
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
- 点层：每站到梅田／難波／天王寺／京橋的分钟数，阈值滑块，A/B 双频度层，⚡💴 标注，面覆盖用实路网步行等时圈，长按任意地点查询。
- 面层：居住等级 S–D（治安×便利×环境），面板勾选「居住等级（面层）」叠加，点区块看说明。
  `data/tiers.geojson` 由旧等级图的像素坐标 SVG 反算而来：用 517 个车站点对 stations_final.json 做 Mercator 三参数拟合，
  513 站全部落在 2px 内，中位误差 0.4px ≈ 31m（参数记在文件的 meta 里）。评级本身仍是 2026 粗略版。
- 底图：地理院淡色地図；暗色主题用 CSS 反色滤镜。

### cost/ 薪資·購買力
- 世界底图：Natural Earth 110m（低缩放）/ 50m（放大）国界，本地文件，不依赖任何外部瓦片；字形复用 tiles/glyphs。
- `data/cities.json` 决定画哪些点；`data/cities/<id>.json` 一城一份，点开才加载；数字格式与置信度规则见 `data/README.md`。
- 页面不写死任何数值；`value` 为 null 显示「暂无」。汇率表 `data/rates.json` 为空时只显示当地货币。

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
- 可达图 86% 的站是 borrowed 级速度，精度升级方案见 TODO。

## 数据来源

OpenStreetMap（ODbL）· 国土数値情報 · 令和2年国勢調査（e-Stat）· 国土地理院（地理院タイル、面積調）· OSM 陸地ポリゴン（osmdata.openstreetmap.de）· geoBoundaries · FOSSGIS Valhalla（步行等时圈）· smartnews-smri/japan-topography · Wikipedia（優等停站型、National colours）
