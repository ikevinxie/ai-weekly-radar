# HANDOFF — 跨对话项目记忆

> **给未来的 Claude**：处理本项目前先读完本文件，即可无损接续，无需回溯历史对话。
> **铁律**（CLAUDE.md）：① Spec 先行——先改 SPEC.md 再写代码；② 测试积累——每个功能/修复配测试，收尾 `python3 -m pytest` 全绿；③ **每次迭代收尾必须更新本文件**。

## 一句话说清这个项目

每周五 20:00 定时任务自动收集全球「天马行空/有趣/有钱途」的 AI 项目，Claude 评分+中英双语解读，发布到公开站点 https://ikevinxie.github.io/ai-weekly-radar/ 并推送飞书群；配套每日大佬发言采集、每月起飞追踪。

## 用户（kevin）的工作偏好

- 先探讨 Spec、确认后再动手；重要决策用选择题问他，他通常全选推荐项
- 喜欢天马行空的新点子——每轮主动提几个想法供他挑选（历史上全被采纳）
- 产出要"渐进式披露"：全局→局部，反感信息大爆炸式罗列
- 界面双语（中文为主，EN 可切换）；解读内容必须双语且地道
- 仓库公开：秘密（飞书 webhook）只放 `~/.config/ai-weekly-radar/feishu_webhook`，绝不入库

## 架构速览（细节见 SPEC.md，这里只给地图）

```
collector/
  sources/      6 个免费数据源：github hackernews producthunt(RSS) arxiv huggingface reddit(RSS)
  filter.py     规则粗筛（关键词/阈值/去重/每源Top10）   store.py   data/projects.json 累积库
  scoring.py    评分prompt+校验（v3格式）               awards.py  7个彩蛋奖(纯规则)
  report.py     生成 docs/ 全套站点(fetch式dashboard+RSS) qr.py     纯标准库二维码(已交叉验证)
  feishu.py     Top10卡片(标题必含关键词「AI项目」)      tracking.py 月度star增长快照
  voices.py     大佬之声：follow-builders feed 日采+周汇总
数据流: collect → (voices-prompt→voices/<week>.json) → prompt→scored/<week>.json → validate → report → feishu → git push
```

- 纯 Python 标准库运行时，pytest 仅开发用；**测试全离线**（fixtures 录制真实响应）
- 评分/解读由定时任务里的 Claude 完成，零 API 成本；量大时拆组并行 subagent 再合并
- `docs/` 全部是生成产物，改样式去 `collector/report.py` 的 `_TEMPLATE`
- 评分文件 v3 结构、标签词表、奖项规则、粗筛阈值 → 一切以 SPEC.md 为准

## 定时任务（Claude Code scheduled tasks）

| taskId | 时间 | 干什么 |
|---|---|---|
| weekly-ai-project-digest | 周五 20:00 | 完整周报流水线（scripts/run_weekly.md） |
| daily-voices-collect | 每天 21:30 | `python3 -m collector voices`（仅本地，不发布） |
| monthly-liftoff-tracking | 每月 1 日 20:30 | star 增长快照 + 更新起飞榜 |

## 迭代史与关键决策（为什么是现在这样）

- **v1**：6 源收集+三维评分（whimsy/fun/money）+本地 dashboard。Reddit JSON 403→改走逐版块 RSS（无票数，靠周榜排序）；Papers with Code 已关停→用 HF 替代；macOS python 证书问题→net.py 里 certifi/系统证书回退链
- **v2**：双语解读分层、GitHub Pages 公开(ikevinxie/ai-weekly-radar, Pages 从 /docs)、飞书 webhook 推送、彩蛋奖、RSS、月度起飞追踪。dashboard 由内嵌数据改为 fetch 式（数据会逐周增长）
- **v3**：用户要求全员深度解读（60 个/周都要 what/why/biz 双语）+tags(1-3, 限词表)+trend.deep；7 个奖项；归档时间线 #archive；象限图；分享按钮+纯标准库 QR（与 python-qrcode 逐位交叉验证，快照 fixture 锁定）；界面完整英化。飞书机器人设了关键词「AI项目」→卡片标题必须含该字面量（有回归测试）
- **v4.1**：修奖项徽章条排版——单枚徽章限 max-width 260px，奖项名全显、项目名过长时省略号截断（完整文案进 title 悬浮提示），修复长论文标题（如硬核奖 VEXAIoT…）撑爆整行的问题。奖项条由「单行横向滚动」改为「flex-wrap 自动换行多行铺满」（桌面 2 行、移动端每枚一行），所有奖项一屏看全无需滚动
- **v4**：大佬之声（follow-builders 公开 feed，日采不发布、周汇总渐进式呈现+融入风向）；象限图改默认收起；奖项点击定位加脉冲动画(card-locate)；卡片降密度（analysis 收进深度解读折叠区）；🥇🥈🥉 Top3 徽章；周导航 ◀▶；trend.deep 加深(8-12句可分段)；本 HANDOFF 机制确立

## 当前状态（每次迭代更新此节）

- 最新周报：**2026-W29**（60 项目全解读；大佬之声 5 主题——基于 7/15 首采的部分周真实数据）
- 测试：**171 个全绿**
- 起飞追踪：data/tracking.json 有首批快照；起飞榜已渲染（榜首 gpt-5.6-instruct）
- 飞书：webhook 已配置并实推验证过（W29 卡片已送达）
- 大佬之声：daily 采集已跑通（2026-07-15，38 条/16 人，来源 feed 24h 滚动窗口）；W30 起为完整周数据

## Backlog（提过但未做，可作为新点子候选）

- 邮件订阅 / 播客语音版（TTS）/ 年度盘点自动生成
- 大佬发言与项目卡片联动（发言里提到的项目高亮互链）
- 「可复刻」标记（solo 开发者能否复刻，做成 idea 库）
- 评分一致性回归：把 tests/scoring_cases 样例混进每周评分抽查

## 收尾检查清单（每次迭代）

1. SPEC.md 与实现一致；CLAUDE.md 运行方式最新
2. `python3 -m pytest` 全绿；浏览器实测本地+线上
3. 提交前确认无秘密入库（grep webhook 值）；commit 尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`
4. **更新本文件**「当前状态」「迭代史」，有新约定补进「用户偏好」
5. 涉及定时任务行为变化时同步更新任务 prompt 与 scripts/run_weekly.md
