"""Reddit 周热帖，走 RSS（Atom）——公开 JSON 接口对本环境返回 403。

RSS 无票数字段，依赖 top?t=week 的排序本身作为热度信号。
"""
from __future__ import annotations

import datetime as _dt
import re
import xml.etree.ElementTree as ET

from ..net import fetch_text
from ..schema import make_project

NAME = "reddit"
SUBREDDITS = ("MachineLearning", "LocalLLaMA", "artificial")
_ATOM = "{http://www.w3.org/2005/Atom}"


def urls(today: _dt.date) -> list[str]:
    return [f"https://www.reddit.com/r/{sub}/top.rss?t=week&limit=25" for sub in SUBREDDITS]


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    text = text.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = text.split("submitted by")[0]
    return " ".join(text.split())


def parse(feed_xml: str, today: _dt.date) -> list[dict]:
    root = ET.fromstring(feed_xml)
    projects = []
    for rank, entry in enumerate(root.findall(_ATOM + "entry"), start=1):
        entry_id = (entry.findtext(_ATOM + "id") or "").strip()   # t3_xxxxx
        title = (entry.findtext(_ATOM + "title") or "").strip()
        link_el = entry.find(_ATOM + "link")
        url = link_el.get("href") if link_el is not None else None
        if not entry_id or not title or not url:
            continue
        category = entry.find(_ATOM + "category")
        subreddit = category.get("term") if category is not None else ""
        description = _strip_html(entry.findtext(_ATOM + "content") or "") or title
        projects.append(make_project(
            id=f"{NAME}:{entry_id.removeprefix('t3_')}",
            name=title,
            url=url,
            source=NAME,
            description=description[:500],
            collected_at=today,
            metrics={"week_rank": rank, "subreddit": subreddit},
        ))
    return projects


def fetch(today: _dt.date) -> list[dict]:
    import sys
    import time
    seen, projects = set(), []
    for i, url in enumerate(urls(today)):
        if i:
            time.sleep(8)  # Reddit 对连续请求限流较严
        try:
            batch = parse(fetch_text(url), today)
        except Exception as e:
            print(f"警告: reddit 子版块抓取失败 {url}: {e}", file=sys.stderr)
            continue
        for p in batch:
            if p["id"] not in seen:
                seen.add(p["id"])
                projects.append(p)
    return projects
