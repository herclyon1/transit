# 办公环境与协作流程（2026-09-16 验收会话定，用户授权）

三个会话、三棵工作树、一条主干。谁在哪、用什么、怎么交付，全在这一页；改规矩改这里。

## 一、目录与会话根（都在 ~/Money 下，只有一个 Git 仓库 = herclyon1/transit）

**三个会话的根目录一律选 `~/Money/transit`**（记忆按根目录分，根相同才共用 `~/.claude/projects/-Users-herclyon-Money-transit/memory/` 那 25 条记忆）。干活会话开起来第一件事：用 EnterWorktree 切进自己的树（`path` 给下表路径），之后所有改动都落在自己的树、自己的分支。

兜底（换机器要重做）：万一会话直接以 transit-ui / transit-data 为根开了，记忆目录已做成软链指向同一份：
```
mkdir -p ~/.claude/projects/-Users-herclyon-Money-transit-{ui,data}
ln -s ../-Users-herclyon-Money-transit/memory ~/.claude/projects/-Users-herclyon-Money-transit-ui/memory
ln -s ../-Users-herclyon-Money-transit/memory ~/.claude/projects/-Users-herclyon-Money-transit-data/memory
```

| 目录 | 分支 | 谁用 | 干什么 |
|---|---|---|---|
| `~/Money/transit` | `main` | **验收**（Fable，本会话，不切树） | 只验不改功能：合并、写 ACCEPT-LOG、维护本页。不在这里开发。 |
| `~/Money/transit-ui` | `ui` | **界面**（Opus，EnterWorktree 切进来） | 唯一地图的界面：`ui/`、`index.html`、各页 HTML/CSS/JS、KIT-MAP、探针规则。 |
| `~/Money/transit-data` | `data` | **数据与底图**（Opus，EnterWorktree 切进来） | `pipeline/`、`*/data/`、`tiles/`、底图样式、汇率脚本。 |

- 干活会话数 = 2（界面 / 数据）。理由：文件归属正好切成两半，几乎不会改同一个文件；再多一个就要开始抢模拟器和抢文件。
- 老界面会话的 `transit-wt`（interaction）已全部合进 main、已停手，删掉。
- `~/Claude` 不并进来。transit 只依赖其中两样，按绝对路径引用即可：`~/Claude/hig-kit`（Kit 数字表 NUMBERS.md 与 Sketch 解包，不进仓库）、`~/Claude/maa-automation`（企业微信推图）。其余（hp-reinstall 15G、usb-tools 等）与本项目无关。
- `~/Money/inbox` 是用户丢原始材料的地方，不进仓库。

## 二、端口（每棵树固定，不许改、不许杀别人的）

| 会话 | rangeserver | kit-audit CDP_PORT 起 |
|---|---|---|
| 界面 `transit-ui` | 8792 | 9400 |
| 数据 `transit-data` | 8793 | 9500 |
| 验收 `transit` | 8791 | 9600 |

起法：在自己的树里 `python3 pipeline/rangeserver.py <端口> &`。`/accept` 的结果落在起服务那棵树的 `.accept/`。
kit-audit.py / accept.py / webclips.py 的 `ACCEPT_BASE` 默认还是 8788，三棵树各自跑时**必须显式给** `ACCEPT_BASE=http://127.0.0.1:<自己的端口>`。
pipeline 里 29 个脚本假定「从仓库根运行」，指的是所在那棵树的根，在自己的树里 `python3 pipeline/…` 照常。

## 三、共享资源：模拟器与 Maps 窗口

一台 Mac 只有一个 iPhone 18 Pro Max 模拟器、一个地图 App 窗口，三个会话共用。不加锁，靠三条规矩：
- 用之前先看模拟器前台是不是自己的页面（`xcrun simctl io <udid> screenshot`），不是就等，不在别人的页面上点。
- 不杀不是自己起的进程，不关不是自己启动的设备（先 `ps -o lstart,ppid` 看是谁的）。
- 要用之前先发会话间消息问对方释放，用完说一声。同时驱动会互相把状态改掉（09-16 上午发生过）。
- **「屏幕锁定」的真相（2026-09-16 13:5x 查清，用户从不锁屏）**：这台 Mac 息屏后不要密码（`sysadminctl -screenLock status` = off），用户也从不手动锁；但显示器一熄（几分钟一次，`pmset -g log` 可查），macOS 仍把会话标成 `CGSSessionScreenIsLocked = true`，于是 computer-use 的菜单/点击被系统挡、screencapture 出不了图、浏览器面板不合成。**这不是用户锁的，别再说「用户锁屏了」，也别叫用户解锁。** 处理：验收会话在干活期间常驻一个 `caffeinate -d -i -u -t 28800`（显示器不睡就不会进这个状态）；各会话自己的截图管线仍套 `caffeinate -d -u -i`；碰到 locked=true 就等显示器亮或发消息给验收会话，报告里写「显示器熄屏导致系统标记锁定」。

## 四、交付与验收（会话间消息，用户不传话）

三个会话互相用桌面端的会话间消息联系（send_message / SendMessage）。验收会话：标题「工作流最优方案验收」，id `local_ffb898d8-d748-430a-81a4-6a04c98d4d32`。

1. 干活会话在自己的树、自己的分支上提交；提交信息里的数字必须是 computed style 实测值。推自己的分支：`git push origin ui`（或 data）。
2. 做完一个可验收的单元，**直接发消息给验收会话**：「ui 分支 <提交号> 待验收：改了什么、要看哪个状态（哪页、Mac 还是手机、什么缩放）、对照 Maps 的哪个状态」。不经用户。
3. 验收会话：三棵树共享同一个 .git，不用 fetch，直接 `git log main..ui`（origin 只是备份）。**参照图必须自己开 Maps 同状态截，不认干活方发的图**（HANDOFF-UI 第四节，用户定）。，在 `transit` 树里 `git merge --no-commit ui` 看，起 8791 预览，按 PLAN-MAC-LOOK 第 0 节一致清单自己开 Maps 同状态截图、跑 kit-audit 两端 + `?accept=1`。
4. 结论写 ACCEPT-LOG.md，**并排图存进 `accept/<日期>-<提交号>.png`**，企业微信推给用户。放行才 `git merge` 进 main 并推；打回就 `git merge --abort`，**发消息告诉干活会话**哪几项不过、依据是什么。
5. 干活会话每天开工先 `git merge main`（把别人已放行的拿过来），不要把 main 合进自己没验收的东西再推 main。
6. **main 不接受直接开发提交**。只有验收会话的合并、ACCEPT-LOG、本页。方案文档（PLAN-*、IDEAS）谁写谁提交到自己分支，随下次验收一起进 main。豁免两样：GitHub Action rates.yml 每天 UTC 16:20 由 rates-bot 直接推 main（只动 `cost/data/rates.json`，data 分支别自己改这个文件）；gitignore 的 `data/raw` 缓存。
7. **数据也走验收，不豁免**（reach.json、tiers、cities/*.json、pass_student.json 直接决定用户看到的分钟数和价格）。数据验收不看截图，看四条，写进 ACCEPT-LOG：① 来源 URL 和口径写在文件或 README 里；② 验收抽 3 个值回原始页面对得上；③ `pipeline/cost/validate.py` 过；④ 关键计数和上一版比得出合理解释（如站数、25 分钟可达数）。
8. 验收单位是「一个功能单元」（如「reach.json 重建」算一次），不是一个提交一次。
9. 用户是最终验收人：只看 ACCEPT-LOG 和并排图，抽查；效果差追责验收会话。

## 五、备份

- 仓库：origin = GitHub，分支推上去即备份。
- `~/Claude/hig-kit` 有本地 Git 但无远端，是唯一没备份的依赖。建议用户自己开一个私有仓库（Apple 套件不能公开）作为它的 origin。

## 六、干活会话不写中间回复（2026-09-16 用户定）

用户只和验收会话沟通，不看干活会话的对话。干活会话：
1. 不写过程叙述：工具调用之间不输出「我先看一下…」「接下来…」这类句子，直接调工具。
2. 不中途停下来汇报或提问：功能单元做完之前不结束回合，也不问用户「接下来做什么」。
3. 任务从验收会话来，结果发回验收会话；对话里最后只留一行「已发验收」。
4. 真卡住（缺数据、要用户拍板）发消息给验收会话，由验收会话去问用户。

会话名（给用户看的）：「transit 验收」「transit 界面」「transit 数据」。
