# osaka/data/raw — 居住等级三维度的原始数据

| 目录 | 内容 | 来源 · 版本 · 许可 | 进不进仓库 |
|---|---|---|---|
| `a31b/A31a-25_86_10_GEOJSON.zip` | 国土数値情報 A31a 洪水浸水想定区域（河川単位）2025 年度版，近畿地方整備局（国管理河川：大和川・淀川・猪名川・桂川・木津川・紀の川…），GeoJSON | https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A31a-2025.html → `/ksj/gml/data/A31a/A31a-25/A31a-25_86_10_GEOJSON.zip`（66 MB，CC BY 4.0，2026-09-16 取） | 不进（.gitignore），`tiers_score.py` 缺了会自动下载 |
| `a31b/A31a-25_27_10_GEOJSON.zip` | 同上，大阪府管理河川（神崎川・安威川・寝屋川・大津川・石川…） | 同页 → `A31a-25_27_10_GEOJSON.zip`（17 MB） | 不进 |
| `a31b/A31a-25_27_20_GEOJSON.zip` | 同上，大阪府 中小河川 | 同页 → `A31a-25_27_20_GEOJSON.zip`（2.3 MB） | 不进 |
| `a31b/A31b-25_20_5135/5235_GEOJSON.zip` | A31b 一次メッシュ版（2025 年度）。**5235 里没有淀川本川**（十三/京橋/御幣島三点查无多边形），所以不用，只留作证据 | https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-A31b-2025.html | 不进 |
| `osm/supermarkets_overpass.json` | OpenStreetMap `shop=supermarket` 节点/面（面取 center），bbox 34.27–35.06N / 135.09–135.75E，2,332 家 | Overpass API https://overpass-api.de/api/interpreter ，查询 `nwr["shop"="supermarket"](34.27,135.09,35.06,135.75); out center tags;`，osm base 2026-09-15T19:44:21Z，ODbL | 进（740 KB） |

只用 想定最大規模（A31a-20-*）和浸水深ランク `A31a_205`（1: <0.5 m，2: 0.5–3 m，3: 3–5 m，4: 5–10 m，5: 10–20 m）。码表 https://nlftp.mlit.go.jp/ksj/gml/codelist/water_depth_code.html 。
