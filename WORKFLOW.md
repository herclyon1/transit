# 办公环境与协作流程（2026-09-16 验收会话定，用户授权）

三个会话、三棵工作树、一条主干。谁在哪、用什么、怎么交付，全在这一页；改规矩改这里。

## 一、目录与会话根（都在 ~/Money 下，只有一个 Git 仓库 = herclyon1/transit）

**三个会话的根目录一律选 `~/Money/transit`**（记忆按根目录分，根相同才共用 `~/.claude/projects/-Users-herclyon-Money-transit/memory/` 那 24 条记忆）。干活会话开起来第一件事：用 EnterWorktree 切进自己的树（`path` 给下表路径），之后所有改动都落在自己的树、自己的分支。

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

起法：在自己的树里 `python3 pipeline/rangeserver.py <端口> &`。

## 三、共享资源：模拟器与 Maps 窗口

一台 Mac 只有一个 iPhone 18 Pro Max 模拟器、一个地图 App 窗口，三个会话共用。不加锁，靠三条规矩：
- 用之前先看模拟器前台是不是自己的页面（`xcrun simctl io <udid> screenshot`），不是就等，不在别人的页面上点。
- 不杀不是自己起的进程，不关不是自己启动的设备（先 `ps -o lstart,ppid` 看是谁的）。
- 要用之前先发会话间消息问对方释放，用完说一声。同时驱动会互相把状态改掉（09-16 上午发生过）。

## 四、交付与验收（会话间消息，用户不传话）

三个会话互相用桌面端的会话间消息联系（send_message / SendMessage）。验收会话：标题「工作流最优方案验收」，id `local_ffb898d8-d748-430a-81a4-6a04c98d4d32`。

1. 干活会话在自己的树、自己的分支上提交；提交信息里的数字必须是 computed style 实测值。推自己的分支：`git push origin ui`（或 data）。
2. 做完一个可验收的单元，**直接发消息给验收会话**：「ui 分支 <提交号> 待验收：改了什么、要看哪个状态（哪页、Mac 还是手机、什么缩放）、对照 Maps 的哪个状态」。不经用户。
3. 验收会话：`git fetch && git log main..origin/ui`。**参照图必须自己开 Maps 同状态截，不认干活方发的图**（HANDOFF-UI 第四节，用户定）。，在 `transit` 树里 `git merge --no-commit origin/ui` 看，起 8791 预览，按 PLAN-MAC-LOOK 第 0 节一致清单自己开 Maps 同状态截图、跑 kit-audit 两端 + `?accept=1`。
4. 结论写 ACCEPT-LOG.md，**并排图存进 `accept/<日期>-<提交号>.png`**，企业微信推给用户。放行才 `git merge` 进 main 并推；打回就 `git merge --abort`，**发消息告诉干活会话**哪几项不过、依据是什么。
5. 干活会话每天开工先 `git merge main`（把别人已放行的拿过来），不要把 main 合进自己没验收的东西再推 main。
6. **main 不接受直接开发提交**。只有验收会话的合并、ACCEPT-LOG、本页。方案文档（PLAN-*、IDEAS）谁写谁提交到自己分支，随下次验收一起进 main。
7. 用户是最终验收人：只看 ACCEPT-LOG 和并排图，抽查；效果差追责验收会话。

## 五、备份

- 仓库：origin = GitHub，分支推上去即备份。
- `~/Claude/hig-kit` 有本地 Git 但无远端，是唯一没备份的依赖。建议用户自己开一个私有仓库（Apple 套件不能公开）作为它的 origin。
