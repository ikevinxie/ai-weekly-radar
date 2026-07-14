"""Hacker News（Algolia API）：近 7 天 Show HN 及高分帖。"""
from __future__ import annotations

import datetime as _dt
import urllib.parse

from ..net import fetch_json
from ..schema import make_project

NAME = "hackernews"
_API = "https://hn.algolia.com/api/v1/search"


def urls(today: _dt.date) -> list[str]:
    cutoff_ts = int(_dt.datetime.combine(today - _dt.timedelta(days=7), _dt.time(),
                                         tzinfo=_dt.timezone.utc).timestamp())
    params = [
        {"tags": "show_hn", "numericFilters": f"points>50,created_at_i>{cutoff_ts}", "hitsPerPage": 50},
        {"query": "AI", "tags": "story", "numericFilters": f"points>100,created_at_i>{cutoff_ts}", "hitsPerPage": 50},
    ]
    return [_API + "?" + urllib.parse.urlencode(p) for p in params]


def parse(payload: dict, today: _dt.date) -> list[dict]:
    projects = []
    for hit in payload.get("hits") or []:
        object_id = hit.get("objectID")
        title = (hit.get("title") or "").strip()
        if not object_id or not title:
            continue
        hn_link = f"https://news.ycombinator.com/item?id={object_id}"
        projects.append(make_project(
            id=f"{NAME}:{object_id}",
            name=title.removeprefix("Show HN: ").strip(),
            url=hit.get("url") or hn_link,
            source=NAME,
            description=title,
            collected_at=today,
            metrics={"points": hit.get("points") or 0,
                     "comments": hit.get("num_comments") or 0,
                     "hn_link": hn_link},
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
