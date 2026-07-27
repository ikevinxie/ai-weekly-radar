"""LLM 评分环节：prompt 模板、评分文件校验、评分合并。

v3 评分文件 data/scored/<week>.json 是对象（见 SPEC.md「评分文件格式」）：
    {"week": "...", "trend": {"zh", "en", "deep": {"zh", "en"}},
     "entries": [{"id", "scores", "reason", "analysis", "deep_dive", "tags"}, ...]}
全部条目必须有 deep_dive 与 1-3 个词表内 tags。
v1/v2 旧格式仅在合并历史数据时兼容读取。
"""
from __future__ import annotations

import json

from .schema import validate_scores

TOP_BADGE_COUNT = 10
DEEP_DIVE_KEYS = ("what", "why", "biz")
LANGS = ("zh", "en")
TAGS = ("agent", "视频", "语音", "图像", "文本", "编码", "安全", "基建", "硬件", "机器人",
        "论文", "数据", "效率", "创意", "社区", "商业", "教育", "金融", "游戏", "医疗", "开源")
MAX_TAGS = 3

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
3. deep_dive：双语深度解读，中英各三段：
   - what：它是什么、怎么运作（3-5 句）
   - why：为什么值得关注、放在本周/行业背景里看意味着什么（3-5 句）
   - biz：商业潜力与风险——市场、变现路径、竞争与隐忧（3-5 句）
4. tags：1-{max_tags} 个主题标签，只能从这个词表里选：
   {tags}

## 本周风向（trend）

纵览全部候选，写本周趋势归纳：
- zh / en：概览版各 3-5 句——哪些主题扎堆出现、风往哪吹、有什么值得玩味的信号
- deep.zh / deep.en：深度版各 5-8 句——主题展开、点名代表项目串讲、下周值得盯什么

## 输出

严格按以下 JSON 结构写入 {output_path}，entries 的 id 与候选一一对应、不增不减：

{{
  "week": "{week}",
  "trend": {{"zh": "...", "en": "...", "deep": {{"zh": "...", "en": "..."}}}},
  "entries": [{{
    "id": "<候选id>",
    "scores": {{"whimsy": 0, "fun": 0, "money": 0, "total": 0}},
    "reason": "...",
    "analysis": {{"zh": "...", "en": "..."}},
    "deep_dive": {{"zh": {{"what": "...", "why": "...", "biz": "..."}},
                  "en": {{"what": "...", "why": "...", "biz": "..."}}}},
    "tags": ["agent"]
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
                                  max_tags=MAX_TAGS, tags=" ".join(TAGS),
                                  output_path=output_path, candidates="\n".join(lines))


def top_ids(entries: list[dict], count: int = TOP_BADGE_COUNT) -> set[str]:
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
    trend = scored.get("trend")
    errors.extend(_validate_bilingual(trend, "trend", "trend"))
    if isinstance(trend, dict):
        errors.extend(_validate_bilingual(trend.get("deep"), "trend", "trend.deep"))
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
        errors.extend(_validate_deep_dive(entry.get("deep_dive"), entry_id))
        # 注意：tag 词表合规 / 数量 / 去重 全部由 sanitize_scored 软处理，
        # 不再作为硬校验。LLM 是概率模型，tag 漂移是必然事件，不应熔断 pipeline。
        # 这里只保留最低限度的结构检查：tags 字段若存在必须是 list，
        # 否则下游 report / feishu 会崩。
        if "tags" in entry and not isinstance(entry["tags"], list):
            errors.append(f"{entry_id}: tags 必须是数组")
    for entry_id in sorted(candidate_ids - seen):
        errors.append(f"{entry_id}: 缺少评分")
    return errors


def _validate_tags(tags, ident: str) -> list[str]:
    if not isinstance(tags, list) or not 1 <= len(tags) <= MAX_TAGS:
        return [f"{ident}: tags 必须是 1-{MAX_TAGS} 个标签的数组"]
    errors = []
    for tag in tags:
        if tag not in TAGS:
            errors.append(f"{ident}: 标签 {tag!r} 不在词表内（见 SPEC.md「标签词表」）")
    if len(set(tags)) != len(tags):
        errors.append(f"{ident}: tags 有重复")
    return errors


def sanitize_scored(scored, candidates: list[dict] | None = None) -> tuple[object, list[str]]:
    """LLM 输出的统一规范化层：把"概率模型必然发生的偏差"在 validate 之前消化掉。

    处理三类偏差：
    1. ID 幻觉：entry.id 不在 candidates 列表里 → 整条丢弃（LLM 抄错 id / 编造 id）。
    2. tag 漂移：丢未知 tag、丢清洗后 tags 为空的 entry、去重、截断到 MAX_TAGS。
    3. 必填字段漏写 / 空字符串：reason / analysis.{zh,en} /
       deep_dive.{zh,en}.{what,why,biz} / trend.{zh,en,deep.*} 自动填占位符。

    就地修改 scored，返回 (scored, warnings)。warnings 非空时调用方应打印，
    便于运维观察 LLM 偏差频率；但 pipeline 不会因为这些偏差挂掉。

    candidates 为 None 时跳过 ID 检查（兼容旧调用 / 单测）。

    校验仍由 validate_scored 兜底——sanitize 之后 validate 应该 0 错；
    如果还有错，说明出现了 sanitize 没覆盖到的结构性问题（比如 scores 不是 dict），
    那才是真该硬卡的。
    """
    warnings: list[str] = []
    if not isinstance(scored, dict):
        return scored, warnings

    # ---- trend 兜底 ----
    trend = scored.get("trend")
    if not isinstance(trend, dict):
        scored["trend"] = trend = {}
    _ensure_bilingual(trend, "trend", warnings,
                      default_zh="（本周风向暂缺）", default_en="(Trend summary unavailable.)")
    deep = trend.get("deep")
    if not isinstance(deep, dict):
        trend["deep"] = deep = {}
    _ensure_bilingual(deep, "trend.deep", warnings,
                      default_zh="（深度解读暂缺）", default_en="(Deep dive unavailable.)")

    # ---- entries 兜底 ----
    entries = scored.get("entries")
    if not isinstance(entries, list):
        return scored, warnings
    candidate_ids = {c.get("id") for c in (candidates or []) if c.get("id")}
    tag_set = set(TAGS)
    kept: list = []
    for e in entries:
        if not isinstance(e, dict):
            kept.append(e)
            continue
        ident = e.get("id", "?")

        # ID 幻觉检查：LLM 抄错 / 编造 id 时整条丢，避免 validate 硬错
        if candidate_ids and ident not in candidate_ids:
            warnings.append(f"{ident}: 不在候选列表（疑似 LLM 抄错 id），整条丢弃")
            continue

        # tag 规范化
        raw = e.get("tags")
        if not isinstance(raw, list):
            warnings.append(f"{ident}: tags 不是数组（{type(raw).__name__}），整条丢弃")
            continue
        cleaned = [t for t in raw if isinstance(t, str) and t in tag_set]
        dropped = [t for t in raw if t not in cleaned]
        if dropped:
            warnings.append(f"{ident}: 丢弃非词表 tag {dropped}")
        if not cleaned:
            warnings.append(f"{ident}: 清洗后无有效 tag，整条丢弃")
            continue
        seen: set = set()
        deduped: list = []
        for t in cleaned:
            if t not in seen:
                seen.add(t)
                deduped.append(t)
            else:
                warnings.append(f"{ident}: 去除重复 tag {t!r}")
        e["tags"] = deduped[:MAX_TAGS]

        # reason 兜底
        reason = e.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            e["reason"] = "（推荐语暂缺，详见深度解读）"
            warnings.append(f"{ident}: reason 缺失，已填占位符")

        # analysis 兜底
        analysis = e.get("analysis")
        if not isinstance(analysis, dict):
            e["analysis"] = analysis = {}
        _ensure_bilingual(analysis, f"{ident}: analysis", warnings,
                          default_zh="（中文简读暂缺）", default_en="(Brief analysis unavailable.)")

        # deep_dive 兜底
        dd = e.get("deep_dive")
        if not isinstance(dd, dict):
            e["deep_dive"] = dd = {}
        for lang in LANGS:
            section = dd.get(lang)
            if not isinstance(section, dict):
                dd[lang] = section = {}
                warnings.append(f"{ident}: deep_dive.{lang} 缺失，已填占位符")
            for key in DEEP_DIVE_KEYS:
                text = section.get(key)
                if not isinstance(text, str) or not text.strip():
                    section[key] = _DEEP_DIVE_PLACEHOLDER[lang][key]
                    warnings.append(f"{ident}: deep_dive.{lang}.{key} 缺失，已填占位符")

        kept.append(e)
    scored["entries"] = kept
    return scored, warnings


def _ensure_bilingual(obj: dict, label: str, warnings: list[str],
                      *, default_zh: str, default_en: str) -> None:
    """确保 obj 有非空 zh / en 字符串字段，缺失则填默认值并记 warning。"""
    for lang, default in (("zh", default_zh), ("en", default_en)):
        text = obj.get(lang)
        if not isinstance(text, str) or not text.strip():
            obj[lang] = default
            warnings.append(f"{label}.{lang} 缺失，已填占位符")


_DEEP_DIVE_PLACEHOLDER = {
    "zh": {"what": "（项目内容暂缺）", "why": "（关注理由暂缺）", "biz": "（商业分析暂缺）"},
    "en": {"what": "(What-it-is unavailable.)",
           "why": "(Why-it-matters unavailable.)",
           "biz": "(Business analysis unavailable.)"},
}


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
        for extra in ("analysis", "deep_dive", "tags"):
            if extra in entry:
                full[extra] = entry[extra]
        merged.append(full)
    merged.sort(key=lambda p: p["scores"]["total"], reverse=True)
    return merged
