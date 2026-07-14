# 每周收集任务执行说明（定时任务中的 Claude 按此执行）

工作目录：`/Users/kevin/Downloads/Claude/自动收集天马行空且有趣或有钱途的AI项目`

## 步骤

1. **收集**：运行 `python3 -m collector collect`。个别数据源失败（警告）可接受；若全部失败则停止并报告。
2. **评分与解读**：运行 `python3 -m collector prompt <本周>`（collect 的输出里有周编号），按输出的 prompt 要求产出：
   - 每个候选：三维分（whimsy / fun / money，各 0–10 整数）+ 中文一句话 reason + **中英双语 analysis（各 2-3 句）** + **中英双语 deep_dive（what / why / biz 各 3-5 句）** + **1-3 个 tags**（只能取 SPEC.md「标签词表」内的值）
   - **本周风向 trend**：概览 zh/en（各 3-5 句）+ deep.zh/deep.en 深度版（各 5-8 句）
   结果写入 `data/scored/<本周>.json`（v3 对象格式）。
   - 评分口径参考 `tests/scoring_cases/cases.json` 里的样例区间，保持跨周一致。
   - 项目多、解读量大时，可拆分成几组并行撰写深度解读，再合并成一个评分文件。
3. **校验**：运行 `python3 -m collector validate <本周>`。若报错，修正评分文件后重跑，直到通过。
4. **出报告**：运行 `python3 -m collector report`，确认输出「已合并周」并生成 `docs/` 站点。
5. **飞书推送**：运行 `python3 -m collector feishu <本周>`。webhook 未配置时会打印配置指引并跳过，不算失败。
6. **发布**：`git add -A && git commit -m "weekly: <本周>" && git push`（提交信息末尾加 `Co-Authored-By: Claude <noreply@anthropic.com>`）。
7. **收尾汇报**：向用户简要汇报——本周候选数量、总分前 5 的项目（名称 + 一句话理由）、本周风向一句话、彩蛋奖得主、失败的数据源（如有），并附线上地址 https://ikevinxie.github.io/ai-weekly-radar/ 。

## 注意

- 遵守项目 [CLAUDE.md](../CLAUDE.md)：不要改动 `data/` 下历史数据；如需改代码，先改 SPEC 再改代码并补测试。
- 若本周候选为 0（比如全被去重），直接汇报即可，不要伪造数据。
- 不需要联网评分：评分与解读由你（Claude）直接完成，不调用外部 API。
- **本仓库公开**：绝不把 webhook 等秘密写进仓库内文件。

# 每月起飞追踪说明（monthly-liftoff-tracking 任务按此执行）

1. 运行 `python3 -m collector track`（GitHub 限流时会自动截断，可设 GITHUB_TOKEN 提额）
2. 运行 `python3 -m collector report` 把起飞榜渲染进站点
3. `git add -A && git commit -m "monthly: liftoff tracking" && git push`
4. 汇报增幅榜 Top 5（名称、入库时 star → 当前 star、倍数）
