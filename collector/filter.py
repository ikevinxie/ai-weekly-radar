"""规则粗筛：AI 关键词、热度阈值、跨周去重、每源截断。见 SPEC.md「粗筛规则」。"""
from __future__ import annotations

import re

# 短词用词边界避免误命中（如 email 里的 ai）；长词直接子串匹配
_SHORT_TOKENS = ("ai", "llm", "gpt", "rag", "agent", "agents", "genai", "ml")
_LONG_TOKENS = (
    "machine learning", "deep learning", "neural", "diffusion", "transformer",
    "chatbot", "copilot", "openai", "anthropic", "claude", "gemini", "llama",
    "mistral", "deepseek", "qwen", "generative", "multimodal", "embedding",
    "fine-tun", "finetun", "prompt", "text-to-", "speech-to-", "voice clone",
    "artificial intelligence", "大模型", "智能体",
)
_PATTERN = re.compile(
    "|".join([r"\b(?:%s)\b" % "|".join(_SHORT_TOKENS)] + [re.escape(t) for t in _LONG_TOKENS]),
    re.IGNORECASE,
)

# arXiv / Hugging Face 天然 AI 相关，跳过关键词过滤
KEYWORD_SOURCES = {"github", "hackernews", "producthunt", "reddit"}

PER_SOURCE_LIMIT = 10


def is_ai_related(project: dict) -> bool:
    if project.get("source") not in KEYWORD_SOURCES:
        return True
    text = f"{project.get('name', '')} {project.get('description', '')}"
    return bool(_PATTERN.search(text))


def passes_threshold(project: dict) -> bool:
    """热度阈值。GitHub/HN 的查询本身已带阈值，这里兜底；PH/arXiv/Reddit(RSS 无票数)不设。"""
    metrics = project.get("metrics") or {}
    source = project.get("source")
    if source == "github":
        return metrics.get("stars", 0) >= 50
    if source == "hackernews":
        return metrics.get("points", 0) >= 50
    if source == "huggingface":
        if metrics.get("kind") == "space":
            return metrics.get("likes", 0) >= 20
        return metrics.get("upvotes", 0) >= 10
    return True


def _heat(project: dict):
    """每源内部排序热度，越大越热。Reddit 用周榜名次取负。"""
    m = project.get("metrics") or {}
    if "week_rank" in m:
        return -m["week_rank"]
    return m.get("stars") or m.get("points") or m.get("upvotes") or m.get("likes") or 0


def filter_projects(projects: list[dict], known_ids: set[str],
                    per_source_limit: int = PER_SOURCE_LIMIT) -> list[dict]:
    by_source: dict[str, list[dict]] = {}
    seen: set[str] = set()
    for p in projects:
        pid = p.get("id")
        if not pid or pid in known_ids or pid in seen:
            continue
        if not is_ai_related(p) or not passes_threshold(p):
            continue
        seen.add(pid)
        by_source.setdefault(p["source"], []).append(p)

    result = []
    for source in sorted(by_source):
        ranked = sorted(by_source[source], key=_heat, reverse=True)
        result.extend(ranked[:per_source_limit])
    return result
