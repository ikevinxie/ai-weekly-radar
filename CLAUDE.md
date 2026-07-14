# 项目行为规范

## 两条铁律

1. **Spec 先行**：任何功能探讨、变更，先更新并确认 [SPEC.md](SPEC.md)，再动手写代码。SPEC.md 是唯一权威规格。
2. **测试用例积累**：每次新增功能或修 bug，必须同步新增/更新测试用例；收尾前全量 `python3 -m pytest` 必须通过。测试是持续积累的回归资产，只增不删（除非对应功能删除）。

## 测试规则

- 框架 pytest，测试放 `tests/`，**一律离线**——不打真实网络
- 真实 API 响应样本录制在 `tests/fixtures/`（新增数据源时先真实请求一次录制，再基于 fixture 写解析测试）
- 每个数据源模块至少覆盖：正常响应、空响应、字段缺失的畸形响应
- `tests/scoring_cases/` 积累 LLM 评分用例（样例项目 + 期望分数区间），用于人工回归检查评分质量

## 运行方式

```bash
python3 -m collector collect          # 抓取 + 粗筛 → data/candidates/<week>.json
python3 -m collector prompt <week>    # 输出评分 prompt（Claude 按此评分+双语解读）
python3 -m collector validate <week>  # 校验 data/scored/<week>.json（v2 结构）
python3 -m collector report           # 合并入库 + 生成 docs/ 全套站点
python3 -m collector feishu <week> [--dry-run]  # 推送 Top 10 卡片到飞书
python3 -m collector track [--limit N]          # 月度起飞追踪快照
python3 -m pytest                     # 全量测试
```

每周五 20:00 的定时任务执行说明见 [scripts/run_weekly.md](scripts/run_weekly.md)。

## 技术约束

- 纯 Python 标准库，无第三方运行时依赖（pytest 仅用于开发）
- `docs/` 整个目录是生成产物，不要手改；改样式/交互去 `collector/report.py`
- `data/` 下的 JSON 是数据资产，谨慎删改
- 项目标签只能取 SPEC.md「标签词表」里的值；要加新标签先改 SPEC
- **本仓库是公开的**：飞书 webhook 等秘密只放环境变量或 `~/.config/ai-weekly-radar/`，绝不写进仓库内任何文件
