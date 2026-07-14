"""GitHub Search API：近 7 天创建、AI 相关、按 star 排序。"""
from __future__ import annotations

import datetime as _dt
import urllib.parse

from ..net import fetch_json
from ..schema import make_project

NAME = "github"
_API = "https://api.github.com/search/repositories"


def urls(today: _dt.date) -> list[str]:
    cutoff = (today - _dt.timedelta(days=7)).isoformat()
    queries = [
        f"created:>{cutoff} stars:>50 topic:ai",
        f"created:>{cutoff} stars:>50 llm OR agent OR gpt OR diffusion OR copilot",
    ]
    return [
        _API + "?" + urllib.parse.urlencode({"q": q, "sort": "stars", "order": "desc", "per_page": 30})
        for q in queries
    ]


def parse(payload: dict, today: _dt.date) -> list[dict]:
    projects = []
    for item in payload.get("items") or []:
        full_name = item.get("full_name")
        if not full_name or not item.get("html_url"):
            continue
        projects.append(make_project(
            id=f"{NAME}:{full_name}",
            name=full_name,
            url=item["html_url"],
            source=NAME,
            description=item.get("description") or "",
            collected_at=today,
            metrics={"stars": item.get("stargazers_count", 0),
                     "language": item.get("language") or ""},
        ))
    return projects


def fetch(today: _dt.date) -> list[dict]:
    seen, projects = set(), []
    for url in urls(today):
        for p in parse(fetch_json(url), today):
            if p["id"] not in seen:
                seen.add(p["id"])
                projects.append(p)
    return projects
