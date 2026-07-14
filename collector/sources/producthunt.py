"""Product Hunt 官方 Atom feed（免费无 key）。"""
from __future__ import annotations

import datetime as _dt
import xml.etree.ElementTree as ET

from ..net import fetch_text
from ..schema import make_project

NAME = "producthunt"
FEED_URL = "https://www.producthunt.com/feed"
_ATOM = "{http://www.w3.org/2005/Atom}"


def _strip_html(text: str) -> str:
    import re
    text = re.sub(r"<[^>]+>", " ", text or "").replace("&amp;", "&")
    text = re.sub(r"\s*Discussion\s*\|\s*Link\s*$", "", " ".join(text.split()))
    return text.strip()


def parse(feed_xml: str, today: _dt.date) -> list[dict]:
    root = ET.fromstring(feed_xml)
    cutoff = today - _dt.timedelta(days=7)
    projects = []
    for entry in root.findall(_ATOM + "entry"):
        entry_id = (entry.findtext(_ATOM + "id") or "").strip()
        title = (entry.findtext(_ATOM + "title") or "").strip()
        link_el = entry.find(_ATOM + "link")
        url = link_el.get("href") if link_el is not None else None
        if not entry_id or not title or not url:
            continue
        published = (entry.findtext(_ATOM + "published") or "")[:10]
        if published:
            try:
                if _dt.date.fromisoformat(published) < cutoff:
                    continue
            except ValueError:
                pass
        projects.append(make_project(
            id=f"{NAME}:{entry_id.rstrip('/').rsplit('/', 1)[-1]}",
            name=title,
            url=url,
            source=NAME,
            description=_strip_html(entry.findtext(_ATOM + "content") or ""),
            collected_at=today,
            metrics={"published": published},
        ))
    return projects


def fetch(today: _dt.date) -> list[dict]:
    return parse(fetch_text(FEED_URL), today)
