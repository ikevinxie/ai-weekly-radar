# 每周收集任务执行说明（定时任务中的 Claude 按此执行）

工作目录：`/Users/kevin/Downloads/Claude/自动收集天马行空且有趣或有钱途的AI项目`

## 步骤

1. **收集**：运行 `python3 -m collector collect`。个别数据源失败（警告）可接受；若全部失败则停止并报告。
2. **评分**：运行 `python3 -m collector prompt <本周>`（collect 的输出里有周编号），按输出的 prompt 要求给每个候选打三维分（whimsy / fun / money，各 0–10 整数）并写中文一句话理由，结果写入 `data/scored/<本周>.json`。
   - 评分口径参考 `tests/scoring_cases/cases.json` 里的样例区间，保持跨周一致。
3. **校验**：运行 `python3 -m collector validate <本周>`。若报错，修正评分文件后重跑，直到通过。
4. **出报告**：运行 `python3 -m collector report`，确认输出「已合并周」并生成 `dashboard/index.html`。
5. **收尾汇报**：向用户简要汇报——本周候选数量、总分前 5 的项目（名称 + 一句话理由）、失败的数据源（如有），并附 Dashboard 路径。

## 注意

- 遵守项目 [CLAUDE.md](../CLAUDE.md)：不要改动 `data/` 下历史数据；如需改代码，先改 SPEC 再改代码并补测试。
- 若本周候选为 0（比如全被去重），直接汇报即可，不要伪造数据。
- 不需要联网评分：评分由你（Claude）直接完成，不调用外部 API。
