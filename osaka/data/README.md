# osaka/data — 大阪·居住 的数据文件

| 文件 | 内容 | 怎么生成 |
|---|---|---|
| `reach.json` | 835 站到四枢纽（梅田/難波/天王寺/京橋）的分钟数（默认视图 `t_default` / 含低频优等 `t_low`）、出处等级、经由 | `pipeline/osaka/fetch_routes.py`（OSM 重抓，raw/ 不进仓库）→ `build_graph.py` → `build_reach.py`。实测时分锚点在 `pipeline/osaka/anchors_metro.json`（每条带来源 URL） |
| `tiers.geojson` | 104 块「作者标注」等级面层（印象分，见 README-tiers-audit.md） | 手绘像素坐标反算 |
| `tiers_scored.json` | 同 104 块的三维度数据分（治安/便利/环境）+ 两种拟合级，未写回 geojson | `pipeline/osaka/tiers_score.py`；`--write` 把三项分写进 geojson 的 `properties.score`，`--set-tier A|B` 换 tier——等用户拍板 |
| `crime_rate_r07.json` | 府内 72 市区町村 令和 7 年刑法犯認知件数 ÷ 国調人口 | 大阪府警 表 9 xlsx + japan/data/muni_stats.json |
| `suumo_ek.json` | 835 站 ↔ SUUMO 関西版站代码（ek = rn 4 位 + 站 5 位，同站每线一个）+ 每站 1R/1K 检索 URL；unmatched 里写了对不上的原因 | `pipeline/osaka/suumo_stations.py`（六府县沿線页，HTML 缓存在 raw/suumo/html/ 不进仓库） |
| `station_rent.json` | 按站房租：SUUMO 在挂 ワンルーム/1K（専有 ≥20 ㎡、駅徒歩 ≤10 分）賃料的中位/下四分位/最低/n，按主 ek 键，增量写 | `pipeline/osaka/suumo_station_rent.py 站名…`；`--all` 跑全部 825 站（约 1–2 小时、几千次请求，先问用户）；`--all --only-osaka` 只跑府内 486 站 |
| `pass_student.json` | 通学定期 1 か月价目表底稿：Osaka Metro 区数表、JR 西日本 幹線 営業キロ表（1–100 km）+ 大阪附近特定額 168 区間、阪急 営業キロ表（1–76 km，含普通/通勤对照）、阪堺 均一；各社官方 URL/版本在 meta；南海・近鉄・阪神・京阪・北大阪急行・モノレール・能勢・水間 还没落表（meta.todo 写了官方页） | 手工从官方页/旅客営業規則 別表 PDF 抽（pymupdf），不动页面 |
| `walk_polys.json` | 每站步行 5/10/15/20 分等时圈（Valhalla） | `pipeline/osaka/fetch_walk_polys.py` |
| `raw/` | 国土数値情報 洪水浸水想定（zip 不进仓库，脚本缺了自动下载）、OSM 超市、SUUMO 路線表 | 见 raw/README.md |

## 按站房租的口径

检索参数就是 `cost/data/cities/osaka.json` tiers 里那 4 条 URL 的：`md=01,02`（ワンルーム/1K）`mb=20`（専有 20 ㎡以上）`et=10`（駅徒歩 10 分以内）`cn=9999999`（築年不限）`po1=12`（賃料+管理費が安い順）`pc=50`。多线站把所有 ek 一起带上（`ek=` 可重复），SUUMO 按建物去重后给一份列表。翻完全部页，賃料（不含管理費）取：

- `median` 中位数——页面上要显示的「这一站的房租」
- `q1` 下四分位——和 tiers 现值同口径（刚来的人真会租到的那档），tiers 的档值 = 该档几个代表站 q1 的中位
- `min`、`n`（去重后行数）、`total_listed`（SUUMO 标的含重复挂牌总数）、`pages`、`fetched_at`、`url`

2026-09-16 在 4 个既有站上核对：天神橋筋六丁目 q1 59,000 / 中位 70,200（n 710）、千林大宮 55,000 / 62,000（635）、大日 42,000 / 66,000（99）、なかもず 50,000 / 58,000（185）——q1 和 osaka.json 各站 items 完全一致；大日 中位 66,000 vs 09-15 的 65,000 是多带了モノレール的 ek（n 89→99）。tiers 档值 59,000/60,000/46,000/50,000 是各档几个站 q1 的中位（如 15 分档 = median(55,000, 68,000, 50,000, 66,000) = 60,000），不是单站数。

礼貌：UA、每次请求间隔 ≥2 s、失败重试 2 次（退避 5/10 s）、每站落盘一次。
