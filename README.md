# AI Weekly Radar · AI 周报

**每周五自动收集全球「天马行空 / 有趣 / 有钱途」的 AI 项目，AI 评分 + 中英双语解读。**
Every Friday, this repo automatically collects the world's most whimsical, fun, and money-smelling AI projects — scored and analyzed bilingually by Claude.

**📊 在线周报 / Live site:** https://ikevinxie.github.io/ai-weekly-radar/
**📡 RSS:** https://ikevinxie.github.io/ai-weekly-radar/feed.xml

## 它是怎么工作的 / How it works

```
6 个免费数据源 → 规则粗筛 → Claude 三维评分 + 双语解读 → 静态周报站点 + RSS + 飞书推送
GitHub · Hacker News · Product Hunt · arXiv · Hugging Face · Reddit
```

- **三个维度 / Three dimensions**：天马行空 whimsy · 有趣 fun · 有钱途 money（各 0–10）
- **每周产出 / Weekly output**：最值得看的 **Top 30 AI 项目**（只收实际做出来/在做的，模型发布与行业新闻不算项目）双语简读 + 深度解读；📰 **本周 10 条最有价值的 AI 新闻**；本周风向；彩蛋奖 🏆🤪💰
- **每月产出 / Monthly**：🚀 起飞榜——回访历史高分项目的 star 增长，验证评分眼光
- 纯 Python 标准库实现，无运行时第三方依赖；评分由 [Claude Code](https://claude.com/claude-code) 定时任务完成，零额外 API 成本

## 自己跑一份 / Run your own

```bash
python3 -m collector collect          # 抓取 + 粗筛
python3 -m collector prompt <week>    # 输出评分 prompt（丢给你的 LLM）
python3 -m collector validate <week>  # 校验评分文件
python3 -m collector report           # 生成 docs/ 站点
python3 -m pytest                     # 130+ 离线测试
```

细节见 [SPEC.md](SPEC.md)（唯一权威规格）与 [CLAUDE.md](CLAUDE.md)（行为规范）。

## 飞书推送配置 / Feishu push (optional)

1. 建一个飞书群 → 群设置 → 群机器人 → 添加「自定义机器人」，复制 webhook 地址
2. `mkdir -p ~/.config/ai-weekly-radar && echo '<webhook地址>' > ~/.config/ai-weekly-radar/feishu_webhook`
3. 之后每周 `python3 -m collector feishu <week>` 自动推送 Top 10 卡片（webhook 不会进入仓库）

## License

MIT
