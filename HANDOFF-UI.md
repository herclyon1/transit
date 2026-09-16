# 界面端交接（2026-09-16，给换根后的干活会话和验收会话）

只写「怎么跑、在哪、为什么」；数字本身在 NUMBERS.md / PLAN-MAC-LOOK 第 0 节，不重复。

## 一、事实文件（新地图照用）

| 文件 | 是什么 | 谁维护 |
|---|---|---|
| `~/Claude/hig-kit/NUMBERS.md` | Apple iOS 27 / macOS 27 UI Kit 的组件数字（从官方 Sketch 套件读的）+ 「macOS 27 地图 App 的组合尺寸」（辅助功能树实测） | 界面会话；.sketch 不进仓库，解包在 `~/Claude/hig-kit/kits/sketch/{ios27,macos27}/`，读法 `tools/sketch-dump.py <页名> <artboard 正则> [深度] [行数]` |
| `PLAN-MAC-LOOK-2026-09-16.md` 第 0 节 | 一致清单：26 项，Maps 实测 / 我们现值 / 改不改 | 验收会话按它验 |
| `KIT-MAP.md` | 页面上每类控件对应哪个 Kit 组件、CSS 类名 | 界面会话 |
| `ui/sf/*.png` | SF Symbols 蒙版（`pipeline/ui/sf-symbols-export.swift` 导出） | 缺符号时加 |
| `cost/data/style_apple_{light,dark}.json` | 底图样式（dddevid 的 Apple 配色整份照搬 + 中文/Noto 改动） | 数据会话 |

## 二、工具怎么跑

- 本地服务：每棵工作树自己起 `python3 pipeline/rangeserver.py <端口> &`（界面树 8790，其它别撞）。探针 POST 到同端口 `/accept`，结果落 `.accept/`。
- Kit 对账：`ACCEPT_BASE=http://127.0.0.1:8790 CDP_PORT=9400 python3 pipeline/ui/kit-audit.py --mac cost osaka japan quiz index`（无头 Chrome，每页一个端口从 CDP_PORT 起）；`--phone` 走已启动的模拟器（`xcrun simctl openurl`）。规则表在 `ui/kitaudit.js`：每条 `rule({name, ref, plat, sel, check})`，改样式先改规则再改 CSS。
- 验收探针：页面 URL 加 `?accept=1&quiet=1`，`ui/accept.js` 量 DOM，`document.title` 变 `ACCEPT-OK` / `ACCEPT-FAIL-n`；模拟器上打开后 `.accept/<页>.json` 出现即完成。Mac 上用 scratchpad 的 `shotm.py <url> 1280 744 '<await 的 js>' out.png`（无头 Chrome，DARK=1 环境变量切暗色）。
- 唯一模拟器：iPhone 18 Pro Max（udid 8E793B8A-…），三个会话共用，谁用谁锁、用完释放；`xcrun simctl io <udid> screenshot x.png` 截图。
- 地图 App 同状态截图（验收必做）：
  1. `open 'maps://?ll=<lat>,<lng>&spn=<dlat>,<dlng>'` 定视野；`open 'maps://?q=<地点>'` 出地点卡；点地图上的图钉用 `osascript … click at {x,y}`（坐标从辅助功能树取）；缩放 `osascript` 发 `keystroke "-" using command down`（Maps 必须 frontmost）。
  2. 截图：`(caffeinate -u -t 10 &); screencapture -x -o -l <窗口id> out.png`（显示器息屏时 app_screenshot 会报「capture failure」，这样能出图；窗口 id 用 app_list_windows 或 `osascript` 取，这几天一直是 4961）。
  3. 数字：`swiftc -O ~/Claude/hig-kit/tools/axdump.swift -o /tmp/axdump && /tmp/axdump com.apple.Maps 14 > x.jsonl`，每行一个元素的 frame；比例尺别读右上那条（读数和实际对不上，09-16 实测），用两个已知经纬度的 AXMapItem 的像素距离算 m/px，再把我们的地图 `jumpTo` 到同一 m/px、同一屏幕位置。
  4. 两张图并排、标状态和比例尺，不用别人发的图。
- 图片给用户：一律企业微信（`~/Claude/maa-automation/scripts/mac/push.py` 的通道，`Notifier(Config()).wecom.send_image(path)`），SendUserFile 他手机看不到。

## 三、这轮做到哪

- Mac 布局按 Maps 组合重排、材质/分组框/侧栏行/卡底工具条/地图模式弹窗按实机一致清单改完，两端 KIT-OK / ACCEPT-OK，验收记录 ACCEPT-LOG.md（f60fd7a 放行）。
- 验收留下没打回的一条：弹窗白盒行高我们 48，Maps 量约 45–46，下次按实机定。
- 老 bug 修掉一个：手机端第二张 Sheet 只露头（hig.css `.sheet.opt{height:auto!important}` 顶掉 sheet.js 的元素高）。
- 没做（等新地图）：山影/海深/交通模式配色/比例尺（数据会话在做，落在底图样式里，新地图照用）。

## 四、新地图起头时别再犯的

1. 参照必须自己开 Maps 同状态截，标缩放和比例尺；拿别人的图当依据、Maps 不缩放就截——09-16 两次被打回。
2. 写进提交信息的值必须是 computed style 的实际值（`.sheet` 被 `html .glass` 压掉那次）。
3. 给用户看的每个字中文，过程句也是。
4. 交付先发验收会话，通过才合 main；验收人自己截图、自己量，记录写 ACCEPT-LOG.md。
5. 「像 Apple」的每条尺寸要么 Kit 画板、要么实机量到，说不出来源就别写。
