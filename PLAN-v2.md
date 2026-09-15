# transit 第二阶段：表和里一起改（2026-09-15，两个会话合写）

用户的要求（原话要点）：不只苹果的原生外观，原生交互也要复制过来；实现方式可以换；薪资图的岗位数据必须是「普通人现在就能去应聘」的真帖——工资是确数、有工时、有联系方式，BOSS 那种区间薪资出局；别再出现「跑一晚上只有 4 条」。

分工：**transit 会话（本文作者）** 管数据、架构、页面迁移、hig.css；**maa 会话** 管交互物理、手势验收、截图 OCR 入库。共用文件的规矩在第五节。用户点头前不开工。

---

## 一、岗位数据：先定判据，再定来源

### 判据（一条记录 = 微信群里那种帖子）
| 项 | 要求 | 不满足 |
|---|---|---|
| 发帖方 | 用人单位自己（门店/公司/单位）；中介、派遣、劳务帖只在帖子里写明**具体用人单位**时入库并标 `via_agent: true` | 拒 |
| 工资 | 一个确数（4000/月、21 元/时）；区间、面议、「+提成」无底数 | 拒 |
| 工时 | 帖子写明班次或工时（白班 9–20 / 两班倒 / 月休 2 天 / 8 小时），能算出月工时 | 拒 |
| 日期 | 发帖 ≤90 天优先，最长 180 天（用户 9-15 定的上限） | 拒 |
| 联系 | 电话 / 微信 / 帖子 URL / 招聘会编号，任一 | 拒 |
| 岗位 | 落在城市「普通人岗位篮子」里（下表） | 记但不入篮子 |

时薪 = 月薪 ÷ 帖子写明的月工时；法定 174 小时只能出现在对照注里（`wage-must-carry-hours` 规矩不变）。
**24 小时岗口径**（保安「上一休一」「上一休二」）：月工时 = 24 × 班数（上一休一 = 15 班 = 360 h），记 `hours_flag: 24h岗`，卡片里注明「含夜间值守」；对照注另给「按 12 小时在岗」的时薪。帖子写了具体班次（白班 9–20 / 夜班 20–9 两班倒）就按班次算，不用这条。

### 普通人岗位篮子（每城相同，每岗 3–5 条即够）
保安 · 餐饮服务员/后厨 · 便利店/超市理货收银 · 外卖/快递 · 工厂普工 · 保洁 · **连锁锚点**（麦当劳/肯德基/Circle K/7-Eleven 官网小时工资，跨国可比）

### 来源顺序（每城都按这个走，先做 ①③）
| 序 | 类型 | 为什么 | 乌鲁木齐 | 邦美蜀 | 大阪 / 其他 |
|---|---|---|---|---|---|
| ① | 官方公共就业服务 | 用人单位提交、法律要求写工资工时、免费、普通人直接投 | 新疆公共就业服务网 / 中国新疆人才网（境外连不上，走用户手机或境内路由）；区级人社公众号的招聘会岗位表（「南部就业」水磨沟区网络招聘会 1169 岗，搜狗微信可搜到，文章公开可读） | Trung tâm Dịch vụ việc làm Đắk Lắk（省就业服务中心）岗位公告 | 大阪：ハローワーク求人検索（每条有時給/月給、就業時間、休日）；韩国 워크넷；德国 Jobbörse；美国各州 job bank；澳洲 Workforce Australia；台湾 台灣就業通（区间多，要筛） |
| ② | 不登录可见确数工资的本地蓝领站 | 已实测无验证码、纯 HTML | 快聘网 wlmqkp.com、石榴快聘 0991zp.com（PLATFORMS.md 已核） | Việc Làm Tốt（vieclamtot.com，Chợ Tốt 蓝领板，可按 Buôn Ma Thuột 筛） | 各城在 PLATFORMS.md 里挑 1–2 个 |
| ③ | 微信群的网页可抓版 | 本地中介/公众号把和群里一样的帖子发成文章，一篇十几条带工资工时 | 搜狗微信搜索 weixin.sogou.com：「乌鲁木齐 招聘 保安/服务员 工资」，公众号「乌鲁木齐优汇」每日汇总（实测「管吃，月休两天」格式） | Facebook 群 Việc làm Buôn Ma Thuột（只能本人加群看；不自动抓） | 日本：LINE オープンチャット、Indeed 直接雇用帖（時給确数）作补充 |
| ④ | 连锁锚点官网 | 跨国可比 | 麦当劳/肯德基中国官网招聘 | Circle K / Highlands / Lotte 官网（已有 20 000–25 000 đ/時） | 各国官网 |
| ⑤ | 用户自己给的群帖 | 用户手上就有（机场保安招聘群 402 人） | 「转发即入库」：用户合并转发到文件传输助手或截图 → 文本解析（transit）/ 截图 OCR（maa）→ 同一记录格式 → 人工确认发帖方 | 同 | 同 |

**BOSS 直聘整体出局，不再爬。**

### 记录格式（每城 `cost/data/raw/<city>/jobs_raw.jsonl`，一行一条）
```
{"city":"urumqi","source":"weixin_sogou","source_url":"https://mp.weixin.qq.com/s/...","fetched_at":"2026-09-15",
 "posted_at":"2026-09-14","employer":"××保安服务公司","via_agent":false,"title":"保安员","basket":"security",
 "wage_value":4000,"wage_unit":"CNY/月","hours_text":"白班9:00-20:00 夜班20:00-次日9:00 两班倒 月休2天",
 "hours_per_day":11.5,"days_per_month":28,"hours_month":322,"hourly":12.4,
 "contact":"192****4918","location":"天山区东泉路","confidence":"listing","raw":"原文全文"}
```
拒绝日志 `rejected.jsonl`：同字段 + `reason`（`range_wage` / `no_hours` / `agent_unnamed` / `stale` / `no_contact` / `off_basket`）。
每晚报告 `cost/data/raw/<city>/<date>/report.md`：看了 N 条、收 M 条、拒绝原因分布、每个来源的命中率、下一步。**没有报告的抓取等于没跑。**

入库：`pipeline/cost/ingest.py` 把 `jobs_raw.jsonl` 里通过的条目按篮子取最低 3–5 条写进 `cities/<city>.json` 的 `jobs[]`（沿用现有 `wage.hours{basis:'posted'}` 结构），`validate.py` 继续拦没工时的。

### 谁做
- transit：适配器 `pipeline/cost/sources/{weixin_sogou,wlmqkp,shiliu,hellowork,vieclamtot,dvvl_daklak}.py`、`ingest.py`、`rejected.jsonl`、每晚报告、`PLATFORMS.md` 每城来源表更新。
- maa：`pipeline/cost/wechat_ingest.py`（用户给的群截图/转发文本 → 同一记录格式，OCR 只处理用户主动给的内容）。
- 用户：把保安群的帖子合并转发或截图给我们；境内才能访问的官方站用手机开一次看格式。

### 第一步（用户点头后）
乌鲁木齐：跑 ①（搜狗微信搜「南部就业」「乌鲁木齐人社」招聘会岗位表）+ ③（「乌鲁木齐优汇」等每日汇总）+ ②（快聘网/石榴快聘按类别页），当晚出第一份报告。通了再铺邦美蜀（DVVL Đắk Lắk + Việc Làm Tốt）和大阪（ハローワーク）。

---

## 二、交互：把地图 App 的手感量出来再做（maa 主导）

现状差在哪：Sheet 只能拖抓手、松手按高度落档、0.32s 贝塞尔；没有速度判断、橡皮筋、弹簧；行没有按下高亮、按钮没有按压缩放；地图与 Sheet 不联动；没有左缘滑动返回；安卓字号 16、字体 Noto、玻璃模糊掉帧。

要量的（地图 App，模拟器 120fps 录像逐帧）：
1. 拖动跟手系数（档位内应为 1）；2. 超出顶/底档的橡皮筋系数；3. 松手落档的速度阈值与中点规则；4. 落档弹簧的时长与过冲；5. 抽屉内滚动 ↔ 拖 Sheet 的交接条件；6. 行按下高亮的出现/消失时序、拖动时取消；7. 按钮按压缩放与时长；8. 点地图上一个点时卡片推入的过渡与地图平移。

交付（maa）：`hig-kit/ui/sheet.js`——pointer events + 速度采样 + spring 积分，不用 CSS transition；接口 `HIG.sheet(el,{detents,onDetent})` 不变，内部换实现；行高亮、按压、胶囊选中、左缘返回（页面栈只有首页→图一层，做成 history.back 手势）；每个手势一段与地图 App 并排的逐帧对照图 + 探针进 accept。减弱动态时全关。

transit 这边：四张图接新控制器、跑 accept、hig.css 里的样式配合。

---

## 三、实现方式（改其内）

| 项 | 现在 | 改成 |
|---|---|---|
| 地图引擎 | 薪资/学習 MapLibre GL；大阪 Leaflet + 几百个 DOM 圆点（缩放不跟手） | **统一 MapLibre GL**，大阪的车站/面层/等时圈改成 GL 图层 |
| 页面结构 | 四张图各 900–1500 行内联 JS，只共用 hig.css/hig.js | 抽 **「地图壳 + Sheet + 工具条 + 地点卡片」骨架**（hig-kit `ui/shell.js`）；每张图只提供 `layers()`（数据 → 图层）和 `card(feature)`（要素 → 卡片内容）两个接口，交互代码不碰数据代码 |
| 部署 | GitHub Pages 静态 | 不变：不做 SPA、不上框架、不要构建 |
| 非 Apple 平台 | 字号 16、Noto、模糊掉帧 | 字号写死 17、Noto Sans CJK 退路、`prefers-reduced-transparency` 或按性能关 backdrop-filter |
| 数据 | 城市 JSON 手写 | 每条带 `source_url/posted_at/confidence`，由 `ingest.py` 从 raw 生成 |

顺序：骨架先在薪资图上落地（数据最复杂），再迁大阪（顺便换引擎），最后学習/クイズ。

---

## 四、验收（在 DESIGN-HIG.md 五关之上加两关）

6. **交互逐帧对照**：每个手势一段模拟器录像，和地图 App 并排，maa 出图、写探针。
7. **数据报告**：每次抓取必有 `report.md`；`validate.py` 通过；城市卡片里每个数字点得开来源。

---

## 五、共用文件规矩
- maa 在 `~/Money/transit-wt`（分支 `interaction`）工作，只碰 `ui/hig.js` 的 sheet 段或新文件 `ui/sheet.js`、`pipeline/cost/wechat_ingest.py`；transit 不改 sheet 引擎那段；合并由 transit 做。`hig.css` 只 transit 改。
- 数字只进 `hig-kit/NUMBERS.md`，谁量谁写，两边 accept 期望值跟着改。
- 模拟器：用前截图看前台，不是自己的页面不发触控；用完关机。
- 不是自己起的进程、不是自己建的设备不碰。

---

## 六、今天不做的
用户额度 19:00 重置，今天不大规模跑抓取、不动引擎；只等点头。
