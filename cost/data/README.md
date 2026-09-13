# 薪资购买力图 · 数据规范

想法见仓库根 IDEAS.md 第 6 节。这里只定"数据长什么样、什么算合格"。

## 文件

- `cities.json`：城市清单。地图只读这个文件画点；每个城市一条：id、三语名、国家、货币、经纬度、`status`（`draft` 未填 / `ready` 可看）、`links`（比如大阪指向可达图）。
- `cities/<id>.json`：一个城市一份，点开点才加载。
- `rates.json`：汇率与购买力平价（PPP）换算因子，带来源和日期。为空时页面只显示当地货币。
- `countries_110m.geojson` / `countries_50m.geojson`：Natural Earth 国界（公有领域），低缩放用 110m，放大用 50m。属性只留 iso / en / zh / ja。

## 每一个数字的格式

```json
{
  "value": 1177,
  "unit": "JPY/h",
  "source_url": "https://...",
  "source_name": "厚生労働省 地域別最低賃金",
  "fetched_at": "2026-09-14",
  "confidence": "official",
  "n": null,
  "note": "2025-10 起适用"
}
```

- `value` 为 `null` 表示还没查，页面显示"暂无"。**不许填估计值冒充实测。**
- `confidence` 只能是：
  - `official` 官方统计或法定数字（最低工资、家计调查）
  - `listing` 招聘／租房平台上的真实挂牌（写明样本数 `n`）
  - `measured` 自己的实际账目（家計汇总）
  - `crowd` 众包（Numbeo 之类），只做对照，页面用虚线框
  - `estimated` 推算，必须在 `note` 写推算方法
- `fetched_at` 必填。超过一年的数字页面会标"旧"。

## 城市文件的段落

| 段 | 回答的问题 |
|---|---|
| `work` | 按签证类型，外国人真实能干什么活、每周上限、去哪个平台找（平台按"最靠谱"排序并说明理由） |
| `wage` | 官方最低时薪 + 平台挂牌时薪（按工种：饮食、便利店、物流、语言教学…） |
| `transport` | 通勤月票、单程票价、常见通勤距离下的月开销 |
| `rent` | 按户型（单间/1K/合租）和区位（市中心/通勤 25 分钟圈）的月租，含礼金押金等一次性费用 |
| `living` | 食、水电网、通信、保险税费；官方家计调查一份，自己账目一份 |
| `derived` | 页面现算，不存：房租要打多少小时工、月结余、以工时计的生活成本 |

## 合格线

一个城市从 `draft` 变 `ready` 的条件：`wage.min_official`、至少一个 `wage.listing`、`rent` 至少一档、`transport.monthly_pass`、`living` 至少官方一份，全部有 `source_url` 和 `fetched_at`。
