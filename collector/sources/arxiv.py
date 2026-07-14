"""arXiv API：cs.AI / cs.LG 近一周论文（Atom XML）。"""
from __future__ import annotations

import datetime as _dt
import urllib.parse
import xml.etree.ElementTree as ET

from ..net import fetch_text
from ..schema import make_project

NAME = "arxiv"
_API = "http://export.arxiv.org/api/query"
_ATOM = "{http://www.w3.org/2005/Atom}"


def url(today: _dt.date) -> str:
    params = {
        "search_query": "cat:cs.AI OR cat:cs.LG",
        "sortBy": "submittedDate",
        "sortOrder": "descending",
        "max_results": 50,
    }
    return _API + "?" + urllib.parse.urlencode(params)


def parse(feed_xml: str, today: _dt.date) -> list[dict]:
    root = ET.fromstring(feed_xml)
    cutoff = today - _dt.timedelta(days=7)
    projects = []
    for entry in root.findall(_ATOM + "entry"):
        entry_id = (entry.findtext(_ATOM + "id") or "").strip()   # http://arxiv.org/abs/2607.01234v1
        title = " ".join((entry.findtext(_ATOM + "title") or "").split())
        if not entry_id or not title:
            continue
        published = (entry.findtext(_ATOM + "published") or "")[:10]
        if published:
            try:
                if _dt.date.fromisoformat(published) < cutoff:
                    continue
            except ValueError:
                pass
        arxiv_id = entry_id.rsplit("/", 1)[-1]
        summary = " ".join((entry.findtext(_ATOM + "summary") or "").split())
        projects.append(make_project(
            id=f"{NAME}:{arxiv_id}",
            name=title,
            url=f"https://arxiv.org/abs/{arxiv_id}",
            source=NAME,
            description=summary[:500],
            collected_at=today,
            metrics={"published": published},
        ))
    return projects


def fetch(today: _dt.date) -> list[dict]:
    return parse(fetch_text(url(today)), today)
