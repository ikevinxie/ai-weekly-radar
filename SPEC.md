# SPEC — 每周 AI 项目自动收集器

> 本文件是项目的唯一权威 Spec。任何功能变更**先改这里、再改代码**。

## 目标

每周五 20:00 自动收集全球「天马行空 / 有趣 / 有钱途」的 AI 项目，经规则粗筛和 LLM 三维评分 + 中英双语解读后，发布到公开 GitHub Pages 周报站点，推送 Top 10 到飞书群，并累积历史数据用于跨周去重与「起飞追踪」。

## 核心决策

| 决策点 | 结论 |
|---|---|
| 调度方式 | Claude Code 定时任务：每周五 20:00 周报；每月 1 日 20:30 起飞追踪 |
| 数据源 | 全部免费、无需付费 API |
| 筛选评分 | 规则粗筛 + Claude 三维评分与双语解读（定时任务中的 Claude 完成，零额外 API 成本） |
| 解读深度 | **全部项目**：中英双语简读（analysis）+ 结构化深度解读（deep_dive）+ 主题标签（tags）；Top 10 徽章按当周总分排名标记 |
| 产出形式 | GitHub Pages 公开站点（`docs/`，仓库 ikevinxie/ai-weekly-radar）+ RSS + 飞书推送 + 累积库（`data/projects.json`） |
| 秘密管理 | 飞书 webhook 等秘密只放环境变量或 `~/.config/ai-weekly-radar/`，**绝不进入仓库** |
| 技术栈 | Python 3（纯标准库，无第三方运行时依赖）+ pytest |

## 数据源

| 来源 | 接口 | 说明 |
|---|---|---|
| GitHub | Search API（未认证 10 req/min；可选免费 `GITHUB_TOKEN` 环境变量提额） | 近 7 天创建、AI 相关、按 star 排序 |
| Hacker News | Algolia API（免费无 key） | Show HN + 高分 AI 相关帖，近 7 天 |
| Product Hunt | 官方 RSS feed（免费无 key） | 商业化产品，「有钱途」维度来源 |
| arXiv | 官方 API（免费） | cs.AI / cs.LG 近一周论文 |
| Hugging Face | Hub API trending models / spaces + daily papers（免费无 key） | 替代已关停的 Papers with Code |
| Reddit | 逐版块 RSS（Atom）——公开 JSON 接口对本环境 403 | r/MachineLearning、r/LocalLLaMA、r/artificial 周榜；RSS 无票数，靠榜单排序作热度信号 |

**容错**：单个数据源失败不中断流程，打印警告并继续其余来源。

## 数据模型（Project）

```json
{
  "id": "github:owner/repo",
  "name": "...", "url": "https://...", "source": "github",
  "description": "...",
  "collected_at": "2026-07-17", "week": "2026-W29",
  "metrics": {"stars": 1234},
  "scores": {"whimsy": 8, "fun": 7, "money": 5, "total": 20},
  "reason": "一句话推荐理由（中文）",
  "analysis": {"zh": "2-3 句中文简读", "en": "2-3 sentence English brief"},
  "deep_dive": {
    "zh": {"what": "是什么", "why": "为什么值得看", "biz": "商业潜力与风险"},
    "en": {"what": "...", "why": "...", "biz": "..."}
  }
}
```

- `id`：`source:唯一标识`，全局去重主键
- `metrics`：各源原始热度指标（stars / points / upvotes / likes 等），键名不强制
- `scores`：三维各 0–10 整数，`total` = 三者之和；候选阶段无此字段
- `reason` / `analysis`：评分时由 Claude 撰写，analysis 双语各 2-3 句；候选阶段无
- `deep_dive`：**全部项目必须有**，六个子字段均非空
- `tags`：1–3 个主题标签，取值限定于下方词表

## 标签词表（tags）

`agent` `视频` `语音` `图像` `文本` `编码` `安全` `基建` `硬件` `机器人` `论文` `数据` `效率` `创意` `社区` `商业` `教育` `金融` `游戏` `医疗`

中文为规范值（`agent` 除外）；EN 显示映射放前端。新增词表条目先改 SPEC。

## 评分文件格式（data/scored/\<week\>.json）

```json
{
  "week": "2026-W29",
  "trend": {"zh": "本周风向 3-5 句", "en": "...",
            "deep": {"zh": "风向深度解读 5-8 句", "en": "..."}},
  "entries": [{"id": "...", "scores": {...}, "reason": "...", "analysis": {...},
               "deep_dive": {...}, "tags": ["agent", "安全"]}]
}
```

`trend`（本周风向）：Claude 评分时对当周项目做主题归纳，双语；`trend.deep` 是点击展开的深度版（主题展开、代表项目串讲、下周值得盯什么）。用于站点横幅、RSS、飞书推送开头。
（v1/v2 旧格式仅在合并历史数据时兼容读取。）

## 彩蛋奖（awards，实时计算不入库）

| 奖项 | 规则 |
|---|---|
| 🏆 本周最佳 | total 最高 |
| 🤪 最离谱奖 | whimsy − money 最大 |
| 💰 闷声发财奖 | money − whimsy 最大 |
| 🐴 黑马奖 | 有数值热度（stars/points/upvotes/likes）且 total 进入当周前 1/3 的项目中，热度最低者 |
| 🔬 硬核奖 | 论文类（arxiv 或 huggingface kind=paper）中 total 最高 |
| 🎪 最好玩奖 | fun 最高 |
| ⚖️ 两极分化奖 | 三维分数极差（max−min）最大 |

并列时依次按（奖项指标降序 → total 降序 → id 字典序升序）断绝；同一项目可兼得多个奖；无符合条件项目时该奖空缺（如当周无论文则硬核奖不发）。奖项徽章展示在项目卡片上并进飞书卡片。

## 每周流水线

1. `python3 -m collector collect` — 抓取全部源 → 归一化 → 规则粗筛 → 与 `data/projects.json` 历史去重 → 写 `data/candidates/<week>.json`
2. **Claude 评分与解读** — 按 `python3 -m collector prompt <week>` 输出的模板，产出 trend + 每项 scores/reason/analysis + Top 10 deep_dive，写 `data/scored/<week>.json`
3. `python3 -m collector validate <week>` — 校验 v2 结构（分数、双语字段、deep_dive 恰好覆盖 Top 10），失败则退出码非 0
4. `python3 -m collector report` — 合并入累积库，生成 `docs/` 全套站点文件
5. `python3 -m collector feishu <week>` — 推送 Top 10 卡片到飞书群（webhook 未配置时跳过并提示）
6. `git add -A && git commit && git push` — 发布到 GitHub Pages

## 站点结构（docs/，GitHub Pages 从此目录服务）

| 文件 | 内容 |
|---|---|
| `docs/index.html` | Dashboard，全部资源内嵌无外链；界面文案随中/EN 切换完整双语，`<html lang>` 同步 |
| `docs/data/<week>.json` | 每周全量已合并项目（含解读、tags），按 total 降序并带 `rank` 字段 |
| `docs/data/weeks.json` | 周索引：各周 trend（含 deep）、awards、top3、count、该周 URL 二维码矩阵 `qr`；顶层 `qr_site`、`liftoff` |
| `docs/feed.xml` | RSS 2.0，每周一条 item：标题含风向首句，描述含 Top 10 |

### Dashboard 功能

信息架构遵循**渐进披露**：默认界面只给「入口级」信息，细节都在一次点击之后；避免信息大爆炸。

- **周报视图**（`#<week>`），自上而下：
  1. 风向横幅：概览常显 +「展开深度分析」显示 trend.deep（**按空行分段渲染**）
  2. 奖项徽章条：紧凑单行（溢出横向滚动），点击平滑滚动并**闪烁定位**到项目卡片（keyframes 脉冲光环 ≈2.4s，读者能明确看到是哪块）
  3. 🎙️ 大佬之声：overview 常显，主题折叠条展开见归纳与原文引用
  4. 🎯 本周象限图：**默认收起**，手动展开（whimsy×money SVG 散点、hover tooltip、点击滚动定位、四象限角标）
  5. 🚀 起飞榜：默认收起，行内含项目介绍（随语言切）
  6. 筛选行（周选择 + ◀▶ 上一周/下一周、来源/标签/排序/中英/搜索）与项目卡片流
- **归档视图**（`#archive`）：竖向时间线，每周一卡（周编号、周五日期、项目数、风向首句、奖项得主、Top 3 链接），点击进入该周
- **项目卡片（降密度）**：默认只显示 名称+徽章+来源、reason 钩子、标签 chips、三维分数条与总分；**双语 analysis 收进「深度解读」折叠区作为导语**，其后接 what/why/biz。排名 1-3 显示 🥇🥈🥉，4-10 显示 🔥 Top 10。hover 上浮+边框高亮+阴影（prefers-reduced-motion 降级）
- **分享**：右下角悬浮按钮（随滚动固定），面板含当前周二维码（canvas 渲染 weeks.json 内嵌矩阵）、复制链接、微博/X/Telegram/LinkedIn 分享链接

本地预览：`.claude/launch.json` 的 dashboard 服务（fetch 需要 http，file:// 打不开）。

## 二维码（collector/qr.py）

纯标准库实现：byte 模式、EC=M、版本 1–6 自适应、Reed-Solomon（GF 256）、8 掩码评估。build 时为站点根与每周 URL 生成矩阵嵌入 weeks.json；正确性以 python-qrcode 交叉比对录制的 fixture 快照锁定。

## 飞书推送（collector/feishu.py）

- 群自定义机器人 webhook；URL 读取顺序：环境变量 `FEISHU_WEBHOOK_URL` → `~/.config/ai-weekly-radar/feishu_webhook` 文件；都缺失时报配置指引并跳过（不算失败）
- 交互式卡片：标题「AI项目周报 {week} · 最值得看的 10 个项目」+ 风向（中文）+ Top 10（名称链接、三维分、reason + analysis.zh）+ 彩蛋奖 + 站点深度解读链接；卡片 JSON < 30KB
- **卡片标题必须含字面量「AI项目」**：机器人配置了关键词安全校验，缺关键词消息会被拒收（有回归测试锁死）

## 大佬之声（collector/voices.py）

追踪 AI 建设者在社交媒体的发言，数据源为 [follow-builders](https://github.com/zarazhangrui/follow-builders) 的公开聚合 feed（`feed-x.json`，免 key，24 小时滚动窗口，约 16 位 builder）。

- **每日采集**（定时任务 `daily-voices-collect`，每天 21:30）：`python3 -m collector voices` 拉取 feed 归一化后写 `data/voices/daily/YYYY-MM-DD.json`（同日重跑覆盖）。**每日原始数据不发布**——`data/voices/daily/` 在 .gitignore 中，只留本地。
- **每周汇总**（并入周五周报任务）：`python3 -m collector voices-prompt <week>` 输出该周去重后的全部发言 + 汇总指令；Claude 写 `data/voices/<week>.json`：

```json
{
  "week": "2026-W30",
  "overview": {"zh": "本周大佬叙事总览 2-4 句", "en": "..."},
  "themes": [{
    "title": {"zh": "主题名", "en": "Theme"},
    "summary": {"zh": "该主题 2-4 句归纳", "en": "..."},
    "quotes": [{"author": "Swyx", "handle": "swyx", "text": "原文摘录",
                "url": "https://x.com/...", "date": "2026-07-14"}]
  }]
}
```

- 站点呈现为**渐进式**（全局→局部）：overview 常显 → 每个主题一个折叠条（标题+一句话）→ 展开见主题归纳与原文引用（保留原链接）；绝不平铺罗列。
- 本周风向（trend / trend.deep）撰写时**必须融入当周大佬发言的信号**；trend.deep 加深加长（8-12 句，可用空行分段，站点按段渲染）。
- 该周无 voices 文件时站点自动隐藏该区块（如历史周）。report 合并时校验结构，不合格则警告跳过。

## 起飞追踪（collector/tracking.py，每月 1 日）

- 取累积库中 GitHub 项目按 total 前 50，GitHub API 查当前 star（可选 `GITHUB_TOKEN` 提额；未配 token 时限速并截断）
- 快照追加进 `data/tracking.json`：`{"github:a/b": [{"date": "2026-08-01", "stars": 2100}]}`，只追加不覆盖
- 增幅榜 = 当前 star 对比入库时 `metrics.stars`，倍数降序；渲染进站点「🚀 起飞榜」

## 粗筛规则（filter.py）

- 时间窗口：仅保留近 7 天内创建/发布的条目（源接口已按时间过滤的除外）
- AI 相关性：名称/描述命中 AI 关键词表（对 GitHub/HN/PH/Reddit 生效；arXiv/HF 天然 AI 相关，跳过）
- 热度阈值（每源不同）：GitHub ≥ 50 stars；HN ≥ 50 points；HF space ≥ 20 likes / paper ≥ 10 upvotes；PH/arXiv/Reddit（RSS 无票数）不设阈值
- 跨周去重：`id` 已存在于累积库则丢弃
- 每源截断 Top N（默认 10），6 源共计上限 60，总候选控制在约 20–60 个/周

## 评分维度

| 维度 | 键 | 含义 |
|---|---|---|
| 天马行空 | `whimsy` | 想法的新奇、大胆、跳出常规程度 |
| 有趣 | `fun` | 普通人看到会觉得好玩/想试试的程度 |
| 有钱途 | `money` | 商业化潜力、市场空间、变现路径清晰度 |

## Dashboard

- 自包含单文件 HTML，数据构建时内嵌，`file://` 双击可开
- 功能：周选择器、按三维度/总分排序、按来源筛选、关键词搜索、明暗主题
- 项目卡片：名称（外链）、来源标签、三维分数条、推荐理由、热度指标

## 测试约定

见 [CLAUDE.md](CLAUDE.md)。核心：所有测试离线（fixture 录制真实响应）、每次功能变更同步积累测试用例、收尾前 `python3 -m pytest` 全绿。
