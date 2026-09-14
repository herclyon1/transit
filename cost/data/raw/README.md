# 原始取数记录

生活类数据的原始来源。城市 JSON 里每个 `listing` 数字的 note 都能对回这里的某一行。

```
cost/data/raw/<city>/<yyyymmdd>/<platform>.jsonl      # 手机 App 无障碍树一键取数（pipeline/cost/phone_grab.py）
cost/data/raw/<city>/<yyyymmdd>/anjuke_web_<站>.json  # 网页版列表（浏览器里 JS 抽取）
```

## 怎么取（乌鲁木齐 2026-09-14/15 实测定型）

手机 USB 连 Mac，App 自己登录好。用户在手机上搜好词、停在列表页第一屏，Mac 上跑一条：

```
python3 pipeline/cost/phone_grab.py               # 自动认前台 App，取前 10，追加到当天的 <app>.jsonl
python3 pipeline/cost/phone_grab.py --n 30 --scroll 5   # 原生列表（贝壳）屏幕外条目不在树里，自动下滑 5 屏合并
```

| 项目 | App / 页面 | 操作 | 备注 |
|---|---|---|---|
| 鸡蛋、牛奶、大米、面包、可乐、啤酒 | 多多买菜（拼多多 App 内） | 搜词，综合排序，第一屏 | 结果页是自研内核，**必须开读屏（TalkBack）**才读得到 |
| 本地一顿饭（拌面） | 美团 → 特价团（到店团购） | 定位 南门(地铁站)，搜"拌面"，默认排序 | 原生页面，不用读屏；用户说本地吃饭用特价团比外卖便宜 |
| 巨无霸套餐 | 麦当劳 App → 到店取餐 → 选城市/门店 | 菜单 → 巨无霸/牛鱼肉堡 → 套餐 | 我用 adb 自己点的 |
| 拿铁 | 瑞幸 App → 自提 → 选城市/门店 → 菜单 → 大师咖啡 | 取菜单标价，券后价写 note | 打烊的店选不进菜单 |
| 四档房租 | 贝壳 App → 租房 → 整租 → 一居 → 地铁站 | 每站 `--scroll 5`；郊区站三站合选 | 地铁站是多选；安居客网页 wlmq.zu.anjuke.com/ditie/fx1-dt211-s<站id>-x1/ 做对照 |

个人信息（姓名、电话、地址）不会进树，jsonl 里只有商品/房源字段。
