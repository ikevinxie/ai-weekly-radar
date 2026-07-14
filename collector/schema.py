"""Project 数据模型与校验。见 SPEC.md「数据模型」。"""
from __future__ import annotations

import datetime as _dt

SOURCES = ("github", "hackernews", "producthunt", "arxiv", "huggingface", "reddit")
SCORE_KEYS = ("whimsy", "fun", "money")
REQUIRED_FIELDS = ("id", "name", "url", "source", "description", "collected_at", "week", "metrics")


def week_of(date: _dt.date) -> str:
    """ISO 周编号，如 2026-W29。"""
    year, week, _ = date.isocalendar()
    return f"{year}-W{week:02d}"


def make_project(*, id: str, name: str, url: str, source: str, description: str,
                 collected_at: _dt.date, metrics: dict) -> dict:
    return {
        "id": id,
        "name": name,
        "url": url,
        "source": source,
        "description": (description or "").strip(),
        "collected_at": collected_at.isoformat(),
        "week": week_of(collected_at),
        "metrics": metrics,
    }


def validate_project(p: dict, *, require_scores: bool = False) -> list[str]:
    """返回错误列表；空列表表示合法。"""
    errors = []
    if not isinstance(p, dict):
        return ["project 必须是对象"]
    ident = p.get("id", "<无 id>")
    for field in REQUIRED_FIELDS:
        if field not in p:
            errors.append(f"{ident}: 缺少字段 {field}")
    source = p.get("source")
    if source is not None and source not in SOURCES:
        errors.append(f"{ident}: 未知来源 {source!r}")
    pid = p.get("id")
    if isinstance(pid, str) and source and not pid.startswith(source + ":"):
        errors.append(f"{ident}: id 必须以 '{source}:' 开头")
    url = p.get("url")
    if isinstance(url, str) and not url.startswith(("http://", "https://")):
        errors.append(f"{ident}: url 必须是 http(s) 链接")
    if not isinstance(p.get("metrics", {}), dict):
        errors.append(f"{ident}: metrics 必须是对象")

    if require_scores:
        errors.extend(validate_scores(p, ident))
    return errors


def validate_scores(p: dict, ident: str) -> list[str]:
    """校验 p 上的 scores + reason 字段（p 可以是完整 project，也可以是轻量评分条目）。"""
    errors = []
    scores = p.get("scores")
    if not isinstance(scores, dict):
        return [f"{ident}: 缺少 scores 对象"]
    for key in SCORE_KEYS:
        value = scores.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10:
            errors.append(f"{ident}: scores.{key} 必须是 0-10 的整数，实际为 {value!r}")
    expected_total = sum(scores[k] for k in SCORE_KEYS
                         if isinstance(scores.get(k), int) and not isinstance(scores.get(k), bool))
    if scores.get("total") != expected_total:
        errors.append(f"{ident}: scores.total 应为三维之和 {expected_total}，实际为 {scores.get('total')!r}")
    reason = p.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        errors.append(f"{ident}: 缺少非空的 reason")
    return errors
