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
| 解读分层 | 全部项目：中英双语简读（analysis）；总分 Top 10：结构化深度解读（deep_dive） |
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
- `deep_dive`：**仅总分 Top 10**（并列时按 id 字典序断绝）必须有、其余不允许有；六个子字段均非空

## 评分文件格式（data/scored/\<week\>.json）

```json
{
  "week": "2026-W29",
  "trend": {"zh": "本周风向 3-5 句", "en": "This week's trend, 3-5 sentences"},
  "entries": [{"id": "...", "scores": {...}, "reason": "...", "analysis": {...}, "deep_dive": {...}}]
}
```

`trend`（本周风向）：Claude 评分时对当周项目做主题归纳，双语；用于站点横幅、RSS、飞书推送开头。
（v1 的纯数组格式仅在合并历史数据时兼容读取。）

## 彩蛋奖（awards，实时计算不入库）

| 奖项 | 规则 |
|---|---|
| 🏆 本周最佳 | total 最高 |
| 🤪 最离谱奖 | whimsy − money 最大 |
| 💰 闷声发财奖 | money − whimsy 最大 |

并列时依次按 total、id 字典序断绝；同一项目可兼得多个奖。

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
| `docs/index.html` | Dashboard：fetch 加载周数据；风向横幅、奖项徽章、Top 10 🔥 卡片可展开深度解读、解读中/EN 切换、🚀 起飞榜；保留周选择/排序/来源筛选/搜索/明暗主题 |
| `docs/data/<week>.json` | 每周全量已合并项目（含解读） |
| `docs/data/weeks.json` | 周索引 + 各周 trend + 起飞榜数据 |
| `docs/feed.xml` | RSS 2.0，每周一条 item：标题含风向首句，描述含 Top 10 |

本地预览：`.claude/launch.json` 的 dashboard 服务（fetch 需要 http，file:// 打不开）。

## 飞书推送（collector/feishu.py）

- 群自定义机器人 webhook；URL 读取顺序：环境变量 `FEISHU_WEBHOOK_URL` → `~/.config/ai-weekly-radar/feishu_webhook` 文件；都缺失时报配置指引并跳过（不算失败）
- 交互式卡片：标题（周编号）+ 风向（中文）+ Top 10（名称链接、三维分、reason + analysis.zh）+ 彩蛋奖 + 站点深度解读链接；卡片 JSON < 30KB

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
