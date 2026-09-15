# ports.geojson / airports.geojson（学習页 港湾・空港 图层的数据）

| 文件 | 来源 | 版本 / 基准日 | 要素 | 属性 |
|---|---|---|---|---|
| `ports.geojson` | 国土数値情報 港湾データ（C02） | C02-14（2014 年版，最新版）；`https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-C02-v3_2.html` → `data/C02/C02-14/C02-14_GML.zip` 里的 `C02-14-g_PortAndHarbor.shp`（点 = 港湾标点） | 994 点 | `name`（港湾名 + 港）、`kind`、`kind_code`（港湾種別コード ClassHarbor2Cd）、`pref`（行政区域コード前两位 → 都道府県名） |
| `airports.geojson` | 国土数値情報 空港データ（C28） | C28-21（2021 年版，基准日 2021-12-31，最新版）；`https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-C28-v4_0.html` → `data/C28/C28-21/C28-21_GML.zip` 里的 `C28-21_AirportReferencePoint.geojson`（標点）+ `C28-21_Airport.geojson`（属性，经 C28_101 关联） | 97 点 | `name`（C28_005）、`kind`、`kind_code`（空港種別コード InstallAirPortCd-v2_3）、`status`（供用中/建設中/休止中）、`pref` |

`kind` 分色字段（Kit 无此组件，颜色由页面定）：

- 港湾（ClassHarbor2Cd）：11 国際戦略港湾（5）· 12 国際拠点港湾（18）· 13 重要港湾（102）· 14 地方港湾（808）· 15 56条港湾（61）→ 合并为「その他」· 99 その他
- 空港（InstallAirPortCd-v2_3）：1 拠点空港（会社管理）（4）· 2 拠点空港（国管理）（20）· 3 拠点空港（特定地方管理）（5）· 4 地方管理空港（54）· 5 その他（7）· 6 共用空港（7）

坐标 WGS84 / JGD2011 经纬度，5 位小数；ports.geojson 174 KB、airports.geojson 20 KB。解析用 python 标准库直接读 .dbf/.shp（pipeline 无第三方依赖）。

**许可**：国土数値情報 利用約款（https://nlftp.mlit.go.jp/ksj/other/agreement.html）——可自由利用（含商用），须注明出典：「国土数値情報（港湾データ・空港データ）（国土交通省）」；加工后须写明「…を加工して作成」。页面署名里加这一句。

生成日期 2026-09-15。
