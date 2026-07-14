"""LLM 评分环节：prompt 模板、评分文件校验、评分合并。

v2 评分文件 data/scored/<week>.json 是对象（见 SPEC.md「评分文件格式」）：
    {"week": "...", "trend": {"zh": "...", "en": "..."},
     "entries": [{"id", "scores", "reason", "analysis", "deep_dive"?}, ...]}
deep_dive 仅出现在总分 Top 10（并列按 id 字典序）。
v1 纯数组格式仅在合并历史数据时兼容读取。
"""
from __future__ import annotations

import json

from .schema import validate_scores

DEEP_DIVE_COUNT = 10
DEEP_DIVE_KEYS = ("what", "why", "biz")
LANGS = ("zh", "en")

PROMPT_TEMPLATE = """\
你是「每周 AI 项目收集器」的评审。请对下面 {count} 个候选项目逐一评分并撰写双语解读。

## 评分：三个维度，各 0-10 整数

- whimsy（天马行空）：想法的新奇、大胆、跳出常规程度。抄袭常见套路 0-3，有新意 4-6，让人眼前一亮 7-8，疯狂而迷人 9-10
- fun（有趣）：普通人看到会觉得好玩、想立刻试试的程度
- money（有钱途）：商业化潜力、市场空间、变现路径清晰度。论文类通常 money 偏低，除非应用前景明确
- total = whimsy + fun + money

## 每个项目必写

1. reason：一句中文推荐钩子（20-60 字，说人话，突出它为什么值得看）
2. analysis：双语简读，zh 和 en 各 2-3 句——比 reason 更具体：它做了什么、亮点/局限是什么

## Top 10 深度解读（deep_dive）

全部打分后，按 total 降序（并列按 id 字典序升序）取前 {deep_dive_count} 个项目，
**恰好这 {deep_dive_count} 个**要多写 deep_dive（其余项目不允许有此字段），中英各三段：
- what：它是什么、怎么运作（3-5 句）
- why：为什么值得关注、放在本周/行业背景里看意味着什么（3-5 句）
- biz：商业潜力与风险——市场、变现路径、竞争与隐忧（3-5 句）

## 本周风向（trend）

纵览全部候选，写一段本周趋势归纳（zh 和 en 各 3-5 句）：哪些主题扎堆出现、
风往哪吹、有什么值得玩味的信号。

## 输出

严格按以下 JSON 结构写入 {output_path}，entries 的 id 与候选一一对应、不增不减：

{{
  "week": "{week}",
  "trend": {{"zh": "...", "en": "..."}},
  "entries": [{{
    "id": "<候选id>",
    "scores": {{"whimsy": 0, "fun": 0, "money": 0, "total": 0}},
    "reason": "...",
    "analysis": {{"zh": "...", "en": "..."}},
    "deep_dive": {{"zh": {{"what": "...", "why": "...", "biz": "..."}},
                  "en": {{"what": "...", "why": "...", "biz": "..."}}}}
  }}]
}}

写完后运行 `python3 -m collector validate {week}` 校验，若报错请修正后重跑。

## 候选项目

{candidates}
"""


def build_prompt(candidates: list[dict], week: str, output_path: str) -> str:
    lines = []
    for p in candidates:
        metrics = ", ".join(f"{k}={v}" for k, v in (p.get("metrics") or {}).items()
                            if k not in ("hn_link", "reddit_link"))
        lines.append(f"- id: {p['id']}\n  名称: {p['name']}\n  来源: {p['source']} ({metrics})\n"
                     f"  链接: {p['url']}\n  描述: {p.get('description') or '(无)'}")
    return PROMPT_TEMPLATE.format(count=len(candidates), week=week,
                                  deep_dive_count=DEEP_DIVE_COUNT,
                                  output_path=output_path, candidates="\n".join(lines))


def top_ids(entries: list[dict], count: int = DEEP_DIVE_COUNT) -> set[str]:
    """总分降序、并列按 id 字典序升序，取前 count 个 id。"""
    def key(e):
        scores = e.get("scores") or {}
        total = scores.get("total") if isinstance(scores.get("total"), int) else -1
        return (-total, e.get("id") or "")
    ranked = sorted((e for e in entries if isinstance(e, dict)), key=key)
    return {e["id"] for e in ranked[:count] if e.get("id")}


def _validate_bilingual(obj, ident: str, field: str) -> list[str]:
    if not isinstance(obj, dict):
        return [f"{ident}: {field} 必须是 {{zh, en}} 对象"]
    errors = []
    for lang in LANGS:
        text = obj.get(lang)
        if not isinstance(text, str) or not text.strip():
            errors.append(f"{ident}: {field}.{lang} 缺失或为空")
    return errors


def _validate_deep_dive(dd, ident: str) -> list[str]:
    if not isinstance(dd, dict):
        return [f"{ident}: deep_dive 必须是 {{zh, en}} 对象"]
    errors = []
    for lang in LANGS:
        section = dd.get(lang)
        if not isinstance(section, dict):
            errors.append(f"{ident}: deep_dive.{lang} 缺失")
            continue
        for key in DEEP_DIVE_KEYS:
            text = section.get(key)
            if not isinstance(text, str) or not text.strip():
                errors.append(f"{ident}: deep_dive.{lang}.{key} 缺失或为空")
    return errors


def _entries_of(scored) -> list[dict]:
    """兼容 v1 数组 / v2 对象两种格式取出条目列表。"""
    if isinstance(scored, list):
        return scored
    if isinstance(scored, dict):
        return scored.get("entries") or []
    return []


def validate_scored(candidates: list[dict], scored) -> list[str]:
    """校验 v2 评分文件。返回错误列表，空为通过。"""
    if not isinstance(scored, dict):
        return ["评分文件必须是对象 {week, trend, entries}（v2 格式，见 SPEC.md）"]
    errors = []
    if not isinstance(scored.get("week"), str) or not scored["week"].strip():
        errors.append("缺少 week 字段")
    errors.extend(_validate_bilingual(scored.get("trend"), "trend", "trend"))
    entries = scored.get("entries")
    if not isinstance(entries, list):
        errors.append("entries 必须是数组")
        return errors

    candidate_ids = {p["id"] for p in candidates}
    seen = set()
    valid_entries = []
    for entry in entries:
        if not isinstance(entry, dict):
            errors.append(f"条目必须是对象: {json.dumps(entry, ensure_ascii=False)[:80]}")
            continue
        entry_id = entry.get("id")
        if entry_id not in candidate_ids:
            errors.append(f"{entry_id}: 不在候选列表中")
            continue
        if entry_id in seen:
            errors.append(f"{entry_id}: 重复评分")
            continue
        seen.add(entry_id)
        valid_entries.append(entry)
        errors.extend(validate_scores(entry, entry_id))
        errors.extend(_validate_bilingual(entry.get("analysis"), entry_id, "analysis"))
    for entry_id in sorted(candidate_ids - seen):
        errors.append(f"{entry_id}: 缺少评分")

    expected_deep = top_ids(valid_entries)
    for entry in valid_entries:
        entry_id = entry["id"]
        if entry_id in expected_deep:
            if "deep_dive" not in entry:
                errors.append(f"{entry_id}: 总分 Top {DEEP_DIVE_COUNT}，缺少 deep_dive")
            else:
                errors.extend(_validate_deep_dive(entry["deep_dive"], entry_id))
        elif "deep_dive" in entry:
            errors.append(f"{entry_id}: 不在总分 Top {DEEP_DIVE_COUNT}，不应有 deep_dive")
    return errors


def merge_scored(candidates: list[dict], scored) -> list[dict]:
    """把评分条目合并回候选，返回完整 project 列表（按总分降序）。兼容 v1/v2。"""
    by_id = {e["id"]: e for e in _entries_of(scored) if isinstance(e, dict) and e.get("id")}
    merged = []
    for p in candidates:
        entry = by_id.get(p["id"])
        if not entry:
            continue
        full = dict(p)
        full["scores"] = entry["scores"]
        full["reason"] = entry["reason"]
        for extra in ("analysis", "deep_dive"):
            if extra in entry:
                full[extra] = entry[extra]
        merged.append(full)
    merged.sort(key=lambda p: p["scores"]["total"], reverse=True)
    return merged
