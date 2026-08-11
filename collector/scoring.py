"""LLM 评分环节：分类+评分 prompt 模板、评分文件校验、评分/新闻合并。

v4 评分文件 data/scored/<week>.json 是对象（见 SPEC.md「评分文件格式」）：
    {"week": "...", "trend": {"zh", "en", "deep": {"zh", "en"}},
     "entries": [{"id", "scores", "reason", "analysis", "deep_dive", "tags"}, ...],
     "news": [{"id", "title": {"zh", "en"}, "newsworthy", "summary": {"zh", "en"}}, ...],
     "skipped": [{"id", "reason"}, ...]}
entries ∪ news ∪ skipped 恰好覆盖全部候选 id。
项目条目必须有 deep_dive 与 1-3 个词表内 tags。
v1/v2/v3 旧格式仅在合并历史数据时兼容读取（缺 news/skipped 按空处理）。
"""
from __future__ import annotations

import json

from .schema import SCORE_KEYS, validate_scores

TOP_BADGE_COUNT = 10
# 每周展示规模：项目总分 Top 30、新闻价值 Top 10（见 SPEC.md「AI 项目 vs AI 新闻」）
PROJECTS_DISPLAY_LIMIT = 30
NEWS_DISPLAY_LIMIT = 10
DEEP_DIVE_KEYS = ("what", "why", "biz")
LANGS = ("zh", "en")
TAGS = ("agent", "视频", "语音", "图像", "文本", "编码", "安全", "基建", "硬件", "机器人",
        "论文", "数据", "效率", "创意", "社区", "商业", "教育", "金融", "游戏", "医疗", "开源")
MAX_TAGS = 3
# LLM 常写的英文 tag → 词表规范值。漂移先软映射，映射不了的才丢（避免整条丢弃）。
# 词表内的规范值（含 agent）不走映射，原样保留。
_TAG_ALIASES = {
    "video": "视频", "videos": "视频", "voice": "语音", "audio": "语音", "speech": "语音",
    "image": "图像", "images": "图像", "vision": "图像", "text": "文本",
    "coding": "编码", "code": "编码", "developer": "编码", "security": "安全",
    "safety": "安全", "infra": "基建", "infrastructure": "基建", "hardware": "硬件",
    "robotics": "机器人", "robot": "机器人", "paper": "论文", "papers": "论文",
    "research": "论文", "data": "数据", "dataset": "数据", "productivity": "效率",
    "creative": "创意", "art": "创意", "community": "社区", "business": "商业",
    "startup": "商业", "education": "教育", "finance": "金融", "fintech": "金融",
    "gaming": "游戏", "game": "游戏", "health": "医疗", "healthcare": "医疗",
    "medical": "医疗", "open-source": "开源", "opensource": "开源", "open source": "开源",
    "agent": "agent", "agents": "agent", "agentic": "agent",
    "科研": "论文", "research paper": "论文",
}

PROMPT_TEMPLATE = """\
你是「每周 AI 项目收集器」的评审。请对下面 {count} 个候选逐一**分类**并处理。

## 第一步：分类（每个候选三选一，三个列表的 id 合起来恰好覆盖全部候选，不增不减）

- **项目（entries）**：已经做出来或正在做的 AI 项目，有具体产物——工具、产品、
  开源库、模型权重、demo/space、论文。**论文就是项目（研究产物）**：arXiv /
  Hugging Face 论文、Reddit [R] 研究帖一律归项目，不是新闻，也不要跳过。
  HF space / demo / 能跑起来的代码仓库同理，都是项目。
- **新闻（news）**：本周发生的 AI **事件**——模型发布/升级、公司动态、榜单、政策、
  融资、事故、丑闻、争议。**模型发布/升级公告是新闻，不是项目**（即使标题像产品
  介绍、即使你想给它打高分）。例：候选「Qwen3.8-Max: A New Bar for Coding」是模型
  发布通稿 → news；「某模型登顶榜单」也是 news。候选名称是新闻标题式（含 发布/
  开源了/ranked/a new bar/now available 等）时，通常是新闻。研究论文不是新闻。
- **跳过（skipped）**：**慎用**！只用于纯观点/吐槽/闲聊、毫无信息量与展示价值的
  帖子。**有新闻价值的事件严禁跳过**——公司动态、丑闻、政策、重大发布哪怕内容
  敏感也必须归 news。拿不准时宁可归项目。给一句理由。

## 项目：三维评分，各 0-10 整数

- whimsy（天马行空）：想法的新奇、大胆、跳出常规程度。抄袭常见套路 0-3，有新意 4-6，让人眼前一亮 7-8，疯狂而迷人 9-10
- fun（有趣）：普通人看到会觉得好玩、想立刻试试的程度
- money（有钱途）：商业化潜力、市场空间、变现路径清晰度。论文类通常 money 偏低，除非应用前景明确
- total = whimsy + fun + money

每个项目必写：
1. reason：一句中文推荐钩子（20-60 字，说人话，突出它为什么值得看）
2. analysis：双语简读，zh 和 en 各 2-3 句——比 reason 更具体：它做了什么、亮点/局限是什么
3. deep_dive：双语深度解读，中英各三段：
   - what：它是什么、怎么运作（3-5 句）
   - why：为什么值得关注、放在本周/行业背景里看意味着什么（3-5 句）
   - biz：商业潜力与风险——市场、变现路径、竞争与隐忧（3-5 句）
4. tags：1-{max_tags} 个主题标签，只能从这个词表里选：
   {tags}

## 新闻：按新闻价值评分（newsworthy 0-10 整数）

看影响面、新鲜度、对从业者的实际意义。大模型更新可以入选但不保证入选——
只收真正有价值的，每周最终只展示 Top 10。每条新闻必写：
1. title：双语标题（zh 中文、en 英文），简明点出事件本身
2. summary：双语摘要，zh 和 en 各 2-3 句——发生了什么、为什么重要

## 本周风向（trend）

纵览全部**项目**，写本周趋势归纳：
- zh / en：概览版各 3-5 句——哪些主题扎堆出现、风往哪吹、有什么值得玩味的信号
- deep.zh / deep.en：深度版各 5-8 句——主题展开、点名代表项目串讲、下周值得盯什么

## 输出

严格按以下 JSON 结构写入 {output_path}：

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
  }}],
  "news": [{{
    "id": "<候选id>",
    "title": {{"zh": "...", "en": "..."}},
    "newsworthy": 0,
    "summary": {{"zh": "...", "en": "..."}}
  }}],
  "skipped": [{{"id": "<候选id>", "reason": "..."}}]
}}

写完后运行 `python3 -m collector validate {week}` 校验，若报错请修正后重跑。

## 候选

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


def _validate_news_item(item, candidate_ids: set, seen: set, errors: list[str]) -> None:
    if not isinstance(item, dict):
        errors.append(f"news 条目必须是对象: {json.dumps(item, ensure_ascii=False)[:80]}")
        return
    ident = item.get("id")
    if ident not in candidate_ids:
        errors.append(f"{ident}: news 条目不在候选列表中")
        return
    if ident in seen:
        errors.append(f"{ident}: 同时出现在多个分类（entries/news/skipped）或重复")
        return
    seen.add(ident)
    newsworthy = item.get("newsworthy")
    if not isinstance(newsworthy, int) or isinstance(newsworthy, bool) \
            or not 0 <= newsworthy <= 10:
        errors.append(f"{ident}: newsworthy 必须是 0-10 的整数，实际为 {newsworthy!r}")
    errors.extend(_validate_bilingual(item.get("title"), ident, "title"))
    errors.extend(_validate_bilingual(item.get("summary"), ident, "summary"))


def validate_scored(candidates: list[dict], scored) -> list[str]:
    """校验 v4 评分文件（兼容 v3：缺 news/skipped 按空处理）。返回错误列表，空为通过。"""
    if not isinstance(scored, dict):
        return ["评分文件必须是对象 {week, trend, entries, news, skipped}（v4 格式，见 SPEC.md）"]
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

    news = scored.get("news") or []
    if not isinstance(news, list):
        errors.append("news 必须是数组")
        news = []
    for item in news:
        _validate_news_item(item, candidate_ids, seen, errors)

    skipped = scored.get("skipped") or []
    if not isinstance(skipped, list):
        errors.append("skipped 必须是数组")
        skipped = []
    for item in skipped:
        if not isinstance(item, dict):
            errors.append(f"skipped 条目必须是对象: {json.dumps(item, ensure_ascii=False)[:80]}")
            continue
        ident = item.get("id")
        if ident not in candidate_ids:
            errors.append(f"{ident}: skipped 条目不在候选列表中")
            continue
        if ident in seen:
            errors.append(f"{ident}: 同时出现在多个分类（entries/news/skipped）或重复")
            continue
        seen.add(ident)
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            errors.append(f"{ident}: skipped 缺少非空的 reason")

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

    处理的偏差：
    1. ID 幻觉：entry/news/skipped 的 id 不在 candidates 列表里 → 整条丢弃
       （LLM 抄错 id / 编造 id）。
    2. tag 漂移：丢未知 tag、丢清洗后 tags 为空的 entry、去重、截断到 MAX_TAGS。
    3. 必填字段漏写 / 空字符串：reason / analysis.{zh,en} /
       deep_dive.{zh,en}.{what,why,biz} / trend.{zh,en,deep.*} /
       news.title.{zh,en} / news.summary.{zh,en} / skipped.reason 自动填占位符。
    4. scores 漂移：维度分非 0-10 整数（字符串 / 浮点 / 超界）→ 强转并 clamp；
       total 不等于三维之和 → 重算（LLM 算错 total 是高频事件）。
       news.newsworthy 同样强转 clamp 到 0-10。
    5. 分类重叠：同一 id 既在 entries 又在 news → 按新闻处理（收紧项目口径）；
       既在 skipped 又在 entries/news → 留有数据的分类。
    6. 整条漏写：候选 id 在 entries ∪ news ∪ skipped 里完全缺失（LLM 分批评分时
       概率性漏写、或被 1/2 丢弃）→ 生成占位条目（零分、placeholder=True），
       让 validate 的全量覆盖检查通过；merge_scored 跳过占位条目，不入库、不上站。
    7. 结构垃圾：entries/news/skipped 不是数组 → 重置为空；
       条目不是对象 / 重复 id → 整条丢弃。

    就地修改 scored，返回 (scored, warnings)。warnings 非空时调用方应打印，
    便于运维观察 LLM 偏差频率；但 pipeline 不会因为这些偏差挂掉。

    candidates 为 None 时跳过 ID 检查与漏写兜底（兼容旧调用 / 单测）。

    传了 candidates 时，sanitize 之后对全量 candidates 跑 validate_scored 应该
    0 错——覆盖率由占位条目兜底，validate 只兜真正的结构性硬错。
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
        warnings.append(f"entries 不是数组（{type(entries).__name__}），重置为空")
        entries = scored["entries"] = []
    candidate_ids = {c.get("id") for c in (candidates or []) if c.get("id")}
    tag_set = set(TAGS)
    kept: list = []
    kept_ids: set = set()
    for e in entries:
        if not isinstance(e, dict):
            warnings.append(f"条目不是对象（{type(e).__name__}），整条丢弃")
            continue
        ident = e.get("id", "?")

        # ID 幻觉检查：LLM 抄错 / 编造 id 时整条丢，避免 validate 硬错
        if candidate_ids and ident not in candidate_ids:
            warnings.append(f"{ident}: 不在候选列表（疑似 LLM 抄错 id），整条丢弃")
            continue
        if ident in kept_ids:
            warnings.append(f"{ident}: 重复评分，整条丢弃")
            continue

        # tag 规范化（词表外 tag 先尝试英文别名映射，实在不认识的才丢）
        raw = e.get("tags")
        if not isinstance(raw, list):
            warnings.append(f"{ident}: tags 不是数组（{type(raw).__name__}），整条丢弃")
            continue
        cleaned: list = []
        dropped: list = []
        for t in raw:
            if not isinstance(t, str):
                dropped.append(t)
                continue
            if t in tag_set:
                cleaned.append(t)
                continue
            alias = _TAG_ALIASES.get(t.strip().lower())
            if alias:
                cleaned.append(alias)
                warnings.append(f"{ident}: tag {t!r} 映射为词表项 {alias!r}")
            else:
                dropped.append(t)
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

        # scores 规范化：LLM 算错 total / 写字符串 / 超界都会让 validate 硬错
        _normalize_scores(e, ident, warnings)

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
        kept_ids.add(ident)

    # ---- news 兜底 ----
    names = {c.get("id"): c.get("name") for c in (candidates or []) if c.get("id")}
    news_raw = scored.get("news")
    if not isinstance(news_raw, list):
        if news_raw is not None:
            warnings.append(f"news 不是数组（{type(news_raw).__name__}），重置为空")
        news_raw = []
    news_kept: list = []
    news_ids: set = set()
    for n in news_raw:
        if not isinstance(n, dict):
            warnings.append(f"news 条目不是对象（{type(n).__name__}），整条丢弃")
            continue
        ident = n.get("id", "?")
        if candidate_ids and ident not in candidate_ids:
            warnings.append(f"{ident}: news 条目不在候选列表（疑似 LLM 抄错 id），整条丢弃")
            continue
        if ident in news_ids:
            warnings.append(f"{ident}: news 条目重复，整条丢弃")
            continue
        worth = n.get("newsworthy")
        if not (isinstance(worth, int) and not isinstance(worth, bool) and 0 <= worth <= 10):
            fixed = _coerce_score(worth)
            warnings.append(f"{ident}: newsworthy 非法（{worth!r}），已修正为 {fixed}")
            n["newsworthy"] = fixed
        title = n.get("title")
        if not isinstance(title, dict):
            n["title"] = title = {}
        # title 缺失时优先用候选原名兜底，比占位文案可读
        _ensure_bilingual(title, f"{ident}: title", warnings,
                          default_zh=names.get(ident) or "（标题暂缺）",
                          default_en=names.get(ident) or "(Title unavailable.)")
        summary = n.get("summary")
        if not isinstance(summary, dict):
            n["summary"] = summary = {}
        _ensure_bilingual(summary, f"{ident}: summary", warnings,
                          default_zh="（新闻摘要暂缺）",
                          default_en="(News summary unavailable.)")
        news_kept.append(n)
        news_ids.add(ident)

    # ---- skipped 兜底 ----
    skipped_raw = scored.get("skipped")
    if not isinstance(skipped_raw, list):
        if skipped_raw is not None:
            warnings.append(f"skipped 不是数组（{type(skipped_raw).__name__}），重置为空")
        skipped_raw = []
    skipped_kept: list = []
    skipped_ids: set = set()
    for s in skipped_raw:
        if not isinstance(s, dict):
            warnings.append(f"skipped 条目不是对象（{type(s).__name__}），整条丢弃")
            continue
        ident = s.get("id", "?")
        if candidate_ids and ident not in candidate_ids:
            warnings.append(f"{ident}: skipped 条目不在候选列表，整条丢弃")
            continue
        if ident in skipped_ids:
            warnings.append(f"{ident}: skipped 条目重复，整条丢弃")
            continue
        reason = s.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            s["reason"] = "（未给出理由）"
            warnings.append(f"{ident}: skipped reason 缺失，已填占位符")
        skipped_kept.append(s)
        skipped_ids.add(ident)

    # ---- 分类重叠消解 ----
    # 同一 id 既当项目又当新闻 → 按新闻处理（收紧项目口径：模型发布/行业新闻不进项目区）
    both = kept_ids & news_ids
    for ident in sorted(both):
        warnings.append(f"{ident}: 同时出现在 entries 和 news，按新闻处理")
    kept = [e for e in kept if e.get("id") not in both]
    kept_ids -= both
    # skipped 与有数据的分类重叠 → 留有数据的
    overlap = skipped_ids & (kept_ids | news_ids)
    for ident in sorted(overlap):
        warnings.append(f"{ident}: 同时出现在 skipped 和 项目/新闻，保留有数据的分类")
    skipped_kept = [s for s in skipped_kept if s.get("id") not in overlap]
    skipped_ids -= overlap

    # ---- 整条漏写兜底 ----
    # 占位条目让 validate 的全量覆盖检查通过；merge_scored 跳过它们，不入库。
    if candidate_ids:
        for cid in sorted(candidate_ids - kept_ids - news_ids - skipped_ids):
            kept.append(_placeholder_entry(cid))
            warnings.append(f"{cid}: 整条漏写，已生成占位条目（零分，不入库）")
    scored["entries"] = kept
    scored["news"] = news_kept
    scored["skipped"] = skipped_kept
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


def _coerce_score(value) -> int:
    """把 LLM 写的维度分强转成 0-10 整数；转不了给 0。"""
    if isinstance(value, bool):
        return 0
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return 0
    return max(0, min(10, n))


def _normalize_scores(entry: dict, ident: str, warnings: list[str]) -> None:
    """维度分 clamp 到 0-10 整数、total 重算为三维之和。"""
    scores = entry.get("scores")
    if not isinstance(scores, dict):
        entry["scores"] = {key: 0 for key in SCORE_KEYS} | {"total": 0}
        warnings.append(f"{ident}: scores 缺失，已填零分")
        return
    for key in SCORE_KEYS:
        value = scores.get(key)
        if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 10:
            continue
        fixed = _coerce_score(value)
        scores[key] = fixed
        warnings.append(f"{ident}: scores.{key} 非法（{value!r}），已修正为 {fixed}")
    total = sum(scores[key] for key in SCORE_KEYS)
    if scores.get("total") != total:
        warnings.append(f"{ident}: scores.total 应为三维之和 {total}，"
                        f"实际 {scores.get('total')!r}，已修正")
        scores["total"] = total


def _placeholder_entry(cid: str) -> dict:
    """整条漏写候选的占位条目：结构合法能通过 validate，但 placeholder=True，
    merge_scored 会跳过，不入库、不上站、不进飞书卡片。"""
    return {
        "id": cid,
        "placeholder": True,
        "scores": {key: 0 for key in SCORE_KEYS} | {"total": 0},
        "reason": "（本周该候选被 LLM 漏评，占位条目，不入库）",
        "analysis": {"zh": "（中文简读暂缺）", "en": "(Brief analysis unavailable.)"},
        "deep_dive": {lang: dict(_DEEP_DIVE_PLACEHOLDER[lang]) for lang in LANGS},
        "tags": ["创意"],
    }


def merge_scored(candidates: list[dict], scored,
                 limit: int = PROJECTS_DISPLAY_LIMIT) -> list[dict]:
    """把评分条目合并回候选，返回完整 project 列表（按总分降序，截断 Top limit）。

    占位条目（placeholder=True，sanitize 为漏写候选生成的零分条目）不合并。
    limit 之外的项目不入库、不上站、不进飞书——每周只展示最值得看的
    PROJECTS_DISPLAY_LIMIT 个（见 SPEC.md「AI 项目 vs AI 新闻」）。兼容 v1/v2/v3。
    """
    by_id = {e["id"]: e for e in _entries_of(scored)
             if isinstance(e, dict) and e.get("id") and not e.get("placeholder")}
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
    merged.sort(key=lambda p: (-p["scores"]["total"], p["id"]))
    return merged[:limit]


def merge_news(candidates: list[dict], scored,
               limit: int = NEWS_DISPLAY_LIMIT) -> list[dict]:
    """取出新闻条目，按新闻价值降序取 Top limit，并从候选补齐展示字段。

    url / source / name / metrics 一律取候选原值（LLM 不写链接，杜绝幻觉 url）。
    title / summary 缺失语言回退候选原名或空。兼容 v3（无 news 返回空列表）。
    """
    if not isinstance(scored, dict):
        return []
    by_id = {p["id"]: p for p in candidates if p.get("id")}
    items = []
    for n in scored.get("news") or []:
        if not isinstance(n, dict) or not n.get("id"):
            continue
        cand = by_id.get(n["id"]) or {}
        title = n.get("title") if isinstance(n.get("title"), dict) else {}
        items.append({
            "id": n["id"],
            "title": {"zh": title.get("zh") or cand.get("name", ""),
                      "en": title.get("en") or cand.get("name", "")},
            "newsworthy": n.get("newsworthy") or 0,
            "summary": n.get("summary") or {},
            "name": cand.get("name", ""),
            "url": cand.get("url", ""),
            "source": cand.get("source", ""),
            "metrics": cand.get("metrics") or {},
        })
    items.sort(key=lambda x: (-x["newsworthy"], x["id"]))
    return items[:limit]
