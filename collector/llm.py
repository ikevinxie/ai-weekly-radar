"""百炼 DashScope API 评分与解读。见 SPEC.md「LLM API 评分」。

通过 OpenAI 兼容接口调用百炼大模型，自动完成候选项目的三维评分、
双语解读和本周风向撰写。纯标准库实现，复用 net.py 的 SSL 回退链。
"""
from __future__ import annotations

import json
import os
import re
import ssl
import sys
import time
import urllib.request
import urllib.error

from .net import USER_AGENT, _CTX
from .scoring import TAGS as _TAGS

API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
DEFAULT_MODEL = "qwen-max"
BATCH_SIZE = 20
MAX_RETRIES = 2
PARSE_RETRIES = 2   # LLM 返回畸形 JSON 时，把错误喂回去让它修，最多额外试这么多次
TIMEOUT = 300


def _api_key() -> str:
    key = os.environ.get("DASHSCOPE_API_KEY", "")
    if not key:
        raise RuntimeError(
            "缺少 DASHSCOPE_API_KEY 环境变量。\n"
            "  GitHub Actions: 在 Settings → Secrets 中添加\n"
            "  本地: export DASHSCOPE_API_KEY=sk-...")
    return key


def _model() -> str:
    return os.environ.get("DASHSCOPE_MODEL", DEFAULT_MODEL)


def chat(prompt: str, *, system: str = "你是一位 AI 项目评审专家。") -> str:
    """调用百炼 API，返回 assistant 回复文本。失败自动重试。"""
    key = _api_key()
    payload = {
        "model": _model(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
    }
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_err: Exception | None = None
    for attempt in range(1 + MAX_RETRIES):
        if attempt:
            time.sleep(2 ** attempt)
        try:
            req = urllib.request.Request(
                API_URL, data=body, method="POST",
                headers={
                    "User-Agent": USER_AGENT,
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}",
                })
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=_CTX) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            return data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, KeyError, IndexError, OSError) as e:
            last_err = e
    raise RuntimeError(f"百炼 API 调用失败（重试 {MAX_RETRIES} 次）: {last_err}")


def extract_json(text: str) -> dict | list:
    """从 LLM 回复中提取 JSON。处理 markdown 代码块围栏和前后缀文本。"""
    # 尝试直接解析
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 去 markdown 代码块围栏
    m = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    # 找第一个 { 或 [ 到最后一个 } 或 ]
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ValueError(f"无法从 LLM 回复中提取 JSON（前 200 字符: {text[:200]}）")


# ---------------------------------------------------------------------------
# 评分 prompt 构建（分批）
# ---------------------------------------------------------------------------

_SCORE_SYSTEM = (
    "你是「每周 AI 项目收集器」的评审。严格按用户要求的 JSON 结构输出，"
    "不要输出任何 JSON 以外的文字。\n"
    "JSON 必须语法合法：所有字符串用双引号、无尾随逗号、无注释、无孤立括号或多余字符；"
    "字符串值内部如需引号请用 \\\" 转义，不要直接换行打断 JSON 结构。")

_BATCH_TEMPLATE = """\
请对下面 {count} 个候选项目逐一评分并撰写双语解读。

## 评分：三个维度，各 0-10 整数

- whimsy（天马行空）：想法的新奇、大胆、跳出常规程度。抄袭常见套路 0-3，有新意 4-6，让人眼前一亮 7-8，疯狂而迷人 9-10
- fun（有趣）：普通人看到会觉得好玩、想立刻试试的程度
- money（有钱途）：商业化潜力、市场空间、变现路径清晰度。论文类通常 money 偏低，除非应用前景明确
- total = whimsy + fun + money

## 每个项目必写

1. reason：一句中文推荐钩子（20-60 字，说人话，突出它为什么值得看）
2. analysis：双语简读，zh 和 en 各 2-3 句
3. deep_dive：双语深度解读，中英各三段（what / why / biz 各 3-5 句）
4. tags：1-3 个主题标签，只能从这个词表里选（**严禁使用词表外的词，如「开源/通信/音频/云/编程/AI」等都不允许，开源项目请用「社区」或主题词代替**）：
   {tags}

## 输出

严格输出 JSON 数组（不要包裹在对象中），每个元素：
{{"id": "<候选id>", "scores": {{"whimsy": 0, "fun": 0, "money": 0, "total": 0}}, "reason": "...", "analysis": {{"zh": "...", "en": "..."}}, "deep_dive": {{"zh": {{"what": "...", "why": "...", "biz": "..."}}, "en": {{"what": "...", "why": "...", "biz": "..."}}}}, "tags": ["agent"]}}

## 候选项目

{candidates}
"""

_TREND_TEMPLATE = """\
下面是本周（{week}）全部 {count} 个已评分 AI 项目的 id 和总分。
请撰写本周风向（trend），严格输出 JSON 对象：

{{"zh": "概览 3-5 句", "en": "overview 3-5 sentences", "deep": {{"zh": "深度 8-12 句，可用空行分段", "en": "deep 8-12 sentences"}}}}

要求：哪些主题扎堆、风往哪吹、代表项目串讲、下周值得盯什么。

## 项目列表

{projects}
"""


def _format_candidates(candidates: list[dict]) -> str:
    lines = []
    for p in candidates:
        metrics = ", ".join(f"{k}={v}" for k, v in (p.get("metrics") or {}).items()
                            if k not in ("hn_link", "reddit_link"))
        lines.append(f"- id: {p['id']}\n  名称: {p['name']}\n  来源: {p['source']} ({metrics})\n"
                     f"  链接: {p['url']}\n  描述: {p.get('description') or '(无)'}")
    return "\n".join(lines)


def _score_batches(candidates: list[dict], *, label: str) -> list[dict]:
    """把候选分批送给 LLM 评分，返回 entries 列表。

    每个 batch 解析失败时，把错误和原文喂回 LLM 重试，最多 PARSE_RETRIES 次。
    """
    all_entries: list[dict] = []
    batches = [candidates[i:i + BATCH_SIZE] for i in range(0, len(candidates), BATCH_SIZE)]
    for idx, batch in enumerate(batches):
        if len(batches) > 1:
            print(f"  {label} {idx + 1}/{len(batches)}（{len(batch)} 个项目）…")
        prompt = _BATCH_TEMPLATE.format(count=len(batch),
                                        tags=" ".join(_TAGS),
                                        candidates=_format_candidates(batch))
        parsed = _chat_json_with_retry(prompt, _SCORE_SYSTEM,
                                       label=f"{label} {idx + 1}/{len(batches)}")
        if isinstance(parsed, dict) and "entries" in parsed:
            parsed = parsed["entries"]
        if not isinstance(parsed, list):
            raise ValueError(f"{label} {idx + 1}: 期望 JSON 数组，得到 {type(parsed).__name__}")
        all_entries.extend(parsed)
    return all_entries


def score_candidates(candidates: list[dict], week: str) -> dict:
    """对全部候选评分，返回 v3 scored 文档。候选多时自动分批。"""
    all_entries = _score_batches(candidates, label="评分批次")

    # trend
    print("  生成本周风向…")
    scored_lines = [f"- {e['id']}  total={(e.get('scores') or {}).get('total', '?')}"
                    for e in all_entries if isinstance(e, dict) and e.get("id")]
    trend_prompt = _TREND_TEMPLATE.format(week=week, count=len(scored_lines),
                                          projects="\n".join(scored_lines))
    trend = _chat_json_with_retry(trend_prompt, _SCORE_SYSTEM, label="trend")
    if not isinstance(trend, dict):
        raise ValueError("trend: 期望 JSON 对象")

    return {"week": week, "trend": trend, "entries": all_entries}


def score_backfill(candidates: list[dict]) -> list[dict]:
    """对分批评分时 LLM 整条漏写的候选定向补评，只返回 entries 数组。

    漏写是概率事件，补评批次小（通常只有几条），LLM 几乎必然全量返回。
    不生成 trend——trend 由 score_candidates 基于全量 entries 统一生成。
    """
    return _score_batches(candidates, label="补评批次")


def _chat_json_with_retry(prompt: str, system: str, *, label: str):
    """调 chat 并 extract_json；解析失败时把错误+原文喂回 LLM 重试。"""
    reply = chat(prompt, system=system)
    last_err: ValueError | None = None
    for attempt in range(PARSE_RETRIES + 1):
        try:
            return extract_json(reply)
        except ValueError as e:
            last_err = e
            if attempt == PARSE_RETRIES:
                break
            print(f"  ⚠ {label} 第 {attempt + 1} 次解析失败，回喂 LLM 修正：{e}",
                  file=sys.stderr)
            fix_prompt = (
                f"你上一次输出无法被 JSON 解析器接受，错误：{e}\n\n"
                f"上一次输出原文：\n{reply}\n\n"
                "请只输出修正后的合法 JSON，不要任何解释、不要 markdown 围栏、"
                "不要前后缀文字。检查：双引号转义、无尾随逗号、无孤立括号、"
                "字符串内不要直接换行。")
            reply = chat(fix_prompt, system=system)
    assert last_err is not None
    raise last_err


# ---------------------------------------------------------------------------
# 大佬之声汇总
# ---------------------------------------------------------------------------

_VOICES_SYSTEM = (
    "你是「AI 周报·大佬之声」栏目的编辑。严格按用户要求的 JSON 结构输出，"
    "不要输出任何 JSON 以外的文字。\n"
    "JSON 必须语法合法：所有字符串用双引号、无尾随逗号、无注释、无孤立括号或多余字符；"
    "字符串值内部如需引号请用 \\\" 转义，不要直接换行打断 JSON 结构。")

_VOICES_TEMPLATE = """\
下面是本周（{week}）AI 建设者们在 X 上的 {count} 条发言。
写一份渐进式汇总，严格输出 JSON 对象：

{{"week": "{week}", "overview": {{"zh": "总览 2-4 句", "en": "..."}}, "themes": [{{"title": {{"zh": "主题名", "en": "Theme"}}, "summary": {{"zh": "2-4 句归纳", "en": "..."}}, "quotes": [{{"author": "原样", "handle": "原样", "text": "原文摘录", "url": "原链接", "date": "YYYY-MM-DD"}}]}}]}}

要求：3-6 个主题，每主题 2-5 条最有代表性的 quotes；url 原样保留；双语地道。

## 本周发言

{posts}
"""


def summarize_voices(posts: list[dict], week: str) -> dict:
    """汇总大佬发言，返回 voices 周汇总文档。"""
    lines = [f"- {p['author']} (@{p['handle']}) {p['date']} [{p.get('likes', 0)} likes]\n"
             f"  {p['text']}\n  {p['url']}" for p in posts]
    prompt = _VOICES_TEMPLATE.format(week=week, count=len(posts),
                                     posts="\n".join(lines))
    doc = _chat_json_with_retry(prompt, _VOICES_SYSTEM, label="voices")
    if not isinstance(doc, dict):
        raise ValueError("voices: 期望 JSON 对象")
    if doc.get("week") != week:
        doc["week"] = week
    return doc
