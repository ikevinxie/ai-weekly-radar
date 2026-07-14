"""Hugging Face Hub API：trending spaces + daily papers（免费无 key）。"""
from __future__ import annotations

import datetime as _dt

from ..net import fetch_json
from ..schema import make_project

NAME = "huggingface"
SPACES_URL = "https://huggingface.co/api/spaces?sort=trendingScore&direction=-1&limit=25"
PAPERS_URL = "https://huggingface.co/api/daily_papers?limit=25"


def parse_spaces(payload: list, today: _dt.date) -> list[dict]:
    projects = []
    for item in payload or []:
        space_id = item.get("id")
        if not space_id:
            continue
        projects.append(make_project(
            id=f"{NAME}:space/{space_id}",
            name=space_id,
            url=f"https://huggingface.co/spaces/{space_id}",
            source=NAME,
            description=(item.get("cardData") or {}).get("title")
                        or (item.get("cardData") or {}).get("short_description") or "",
            collected_at=today,
            metrics={"likes": item.get("likes", 0), "kind": "space"},
        ))
    return projects


def parse_papers(payload: list, today: _dt.date) -> list[dict]:
    projects = []
    for item in payload or []:
        paper = item.get("paper") or {}
        paper_id = paper.get("id")
        title = " ".join((paper.get("title") or "").split())
        if not paper_id or not title:
            continue
        summary = " ".join((paper.get("summary") or "").split())
        projects.append(make_project(
            id=f"{NAME}:paper/{paper_id}",
            name=title,
            url=f"https://huggingface.co/papers/{paper_id}",
            source=NAME,
            description=summary[:500],
            collected_at=today,
            metrics={"upvotes": paper.get("upvotes", 0), "kind": "paper"},
        ))
    return projects


def fetch(today: _dt.date) -> list[dict]:
    return parse_spaces(fetch_json(SPACES_URL), today) + parse_papers(fetch_json(PAPERS_URL), today)
