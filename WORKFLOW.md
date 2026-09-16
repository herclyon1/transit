# 办公环境与协作流程（2026-09-16 验收会话定，用户授权）

三个会话、三棵工作树、一条主干。谁在哪、用什么、怎么交付，全在这一页；改规矩改这里。

## 一、目录（都在 ~/Money 下，只有一个 Git 仓库 = herclyon1/transit）

| 目录 | 分支 | 谁用 | 干什么 |
|---|---|---|---|
| `~/Money/transit` | `main` | **验收**（Fable） | 只验不改功能：合并、写 ACCEPT-LOG、维护本页。不在这里开发。 |
| `~/Money/transit-ui` | `ui` | **界面**（Opus） | 唯一地图的界面：`ui/`、`index.html`、各页 HTML/CSS/JS、KIT-MAP、探针规则。 |
| `~/Money/transit-data` | `data` | **数据与底图**（Opus） | `pipeline/`、`*/data/`、`tiles/`、底图样式、汇率脚本。 |
| `~/Money/transit-wt` | `interaction` | 旧界面会话 | 已全部合进 main，那个会话关掉后 `git worktree remove ../transit-wt` 删掉。 |

- 干活会话数 = 2（界面 / 数据）。理由：文件归属正好切成两半，几乎不会改同一个文件；再多一个就要开始抢模拟器和抢文件。
- `~/Claude` 不并进来。transit 只依赖其中两样，按绝对路径引用即可：`~/Claude/hig-kit`（Kit 数字表 NUMBERS.md 与 Sketch 解包，不进仓库）、`~/Claude/maa-automation`（企业微信推图）。其余（hp-reinstall 15G、usb-tools 等）与本项目无关。
- `~/Money/inbox` 是用户丢原始材料的地方，不进仓库。

## 二、端口（每棵树固定，不许改、不许杀别人的）

| 会话 | rangeserver | kit-audit CDP_PORT 起 |
|---|---|---|
| 界面 `transit-ui` | 8792 | 9400 |
| 数据 `transit-data` | 8793 | 9500 |
| 验收 `transit` | 8791 | 9600 |

起法：在自己的树里 `python3 pipeline/rangeserver.py <端口> &`。8790 是旧界面树的，8788 是更早的，都别动。

## 三、共享资源：模拟器与 Maps 窗口，用锁

一台 Mac 只有一个 iPhone 18 Pro Max 模拟器、一个地图 App 窗口。用前占锁，用完释放：

```
pipeline/lock.sh take simulator ui      # 或 data / accept；资源名 simulator / maps
pipeline/lock.sh free simulator ui
pipeline/lock.sh show
```

被占用就等，不许杀进程、不许关别人的设备、不许在别人的页面上点。验收要用时，干活会话释放。

## 四、交付与验收

1. 干活会话在自己的树、自己的分支上提交；提交信息里的数字必须是 computed style 实测值。推自己的分支：`git push -u origin ui`（或 data）。
2. 做完一个可验收的单元，告诉用户一句：「ui 分支 <提交号> 待验收：<改了什么>」。用户转给验收会话（或用桌面端直接发给验收会话）。
3. 验收会话：`git fetch && git log main..origin/ui`，在 `transit` 树里 `git merge --no-commit origin/ui` 看，起 8791 预览，按 PLAN-MAC-LOOK 第 0 节一致清单自己开 Maps 同状态截图、跑 kit-audit 两端 + `?accept=1`。
4. 结论写 ACCEPT-LOG.md，**并排图存进 `accept/<日期>-<提交号>.png`**，企业微信推给用户。放行才 `git merge` 进 main 并推；打回就 `git merge --abort`，写明哪几项。
5. 干活会话每天开工先 `git merge main`（把别人已放行的拿过来），不要反过来把 main 合进自己没验收的东西再推 main。
6. **main 不接受直接开发提交**。只有验收会话的合并、ACCEPT-LOG、本页。方案文档（PLAN-*、IDEAS）谁写谁提交到自己分支，随下次验收一起进 main。

## 五、备份

- 仓库：origin = GitHub，分支推上去即备份。
- `~/Claude/hig-kit` 有本地 Git 但无远端，是唯一没备份的依赖。建议用户自己开一个私有仓库（Apple 套件不能公开）作为它的 origin。
