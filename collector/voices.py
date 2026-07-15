"""大佬之声：AI 建设者社交发言的每日采集与每周汇总。见 SPEC.md「大佬之声」。

数据源：follow-builders 公开聚合 feed（免 key，24h 滚动窗口）。
每日快照存 data/voices/daily/（.gitignore，不发布）；每周汇总 data/voices/<week>.json 随周报发布。
"""
from __future__ import annotations

import datetime as _dt
import json
import pathlib

from .net import fetch_json
from .schema import week_of
from .store import ROOT

FEED_URL = "https://raw.githubusercontent.com/zarazhangrui/follow-builders/main/feed-x.json"
DAILY_DIR = ROOT / "data" / "voices" / "daily"
WEEKLY_DIR = ROOT / "data" / "voices"
LANGS = ("zh", "en")


def parse_feed(payload: dict) -> list[dict]:
    """归一化 feed 为发言列表。畸形条目跳过。"""
    posts = []
    for builder in payload.get("x") or []:
        author = (builder.get("name") or "").strip()
        handle = (builder.get("handle") or "").strip()
        for tweet in builder.get("tweets") or []:
            text = (tweet.get("text") or "").strip()
            url = tweet.get("url")
            if not text or not url:
                continue
            posts.append({
                "author": author or handle,
                "handle": handle,
                "text": text,
                "url": url,
                "date": (tweet.get("createdAt") or "")[:10],
                "likes": tweet.get("likes") or 0,
            })
    return posts


def collect_daily(today: _dt.date, path_dir: pathlib.Path = DAILY_DIR) -> pathlib.Path:
    posts = parse_feed(fetch_json(FEED_URL))
    path_dir.mkdir(parents=True, exist_ok=True)
    path = path_dir / f"{today.isoformat()}.json"
    path.write_text(json.dumps(posts, ensure_ascii=False, indent=1), encoding="utf-8")
    return path


def load_week_posts(week: str, path_dir: pathlib.Path = DAILY_DIR) -> list[dict]:
    """聚合该 ISO 周的每日快照，按 url 去重（feed 是 24h 滚动窗口，跨日有重叠）。"""
    if not path_dir.exists():
        return []
    seen, posts = set(), []
    for path in sorted(path_dir.glob("*.json")):
        try:
            day = _dt.date.fromisoformat(path.stem)
        except ValueError:
            continue
        if week_of(day) != week:
            continue
        for post in json.loads(path.read_text(encoding="utf-8")):
            if post.get("url") and post["url"] not in seen:
                seen.add(post["url"])
                posts.append(post)
    return posts


def weekly_path(week: str) -> pathlib.Path:
    return WEEKLY_DIR / f"{week}.json"


def build_prompt(posts: list[dict], week: str) -> str:
    lines = [f"- {p['author']} (@{p['handle']}) {p['date']} [{p.get('likes', 0)} likes]\n"
             f"  {p['text']}\n  {p['url']}" for p in posts]
    return PROMPT_TEMPLATE.format(week=week, count=len(posts),
                                  output_path=str(weekly_path(week)),
                                  posts="\n".join(lines))


PROMPT_TEMPLATE = """\
你是「AI 周报·大佬之声」栏目的编辑。下面是本周（{week}）AI 建设者们在 X 上的 {count} 条发言。

任务：写一份**渐进式**汇总（全局 → 主题 → 原文），写入 {output_path}：

{{
  "week": "{week}",
  "overview": {{"zh": "本周大佬叙事总览，2-4 句，抓住最大的共同信号", "en": "..."}},
  "themes": [{{
    "title": {{"zh": "主题名（4-10 字）", "en": "Theme name"}},
    "summary": {{"zh": "该主题下大家在说什么、为什么重要，2-4 句", "en": "..."}},
    "quotes": [{{"author": "原样", "handle": "原样", "text": "原文摘录（可截断到 200 字内）",
                "url": "原链接原样保留", "date": "YYYY-MM-DD"}}]
  }}]
}}

要求：
1. 3-6 个主题，每主题挑 2-5 条**最有代表性**的发言做 quotes，宁缺毋滥——不是罗列全部
2. 闲聊、纯转发、无信息量的发言直接舍弃
3. overview 和 summary 要有观点和归纳，不是发言的复述
4. url 必须原样保留；quotes 的 author/handle/date 与输入一致
5. 双语都要地道
6. 同时，把这些发言里的信号融入本周风向（trend / trend.deep）的撰写

## 本周发言

{posts}
"""


def validate_weekly(doc) -> list[str]:
    """校验周汇总结构。返回错误列表，空为通过。"""
    if not isinstance(doc, dict):
        return ["voices 周汇总必须是对象"]
    errors = []
    if not isinstance(doc.get("week"), str) or not doc["week"].strip():
        errors.append("voices: 缺少 week")
    overview = doc.get("overview")
    for lang in LANGS:
        if not isinstance(overview, dict) or not str(overview.get(lang) or "").strip():
            errors.append(f"voices: overview.{lang} 缺失或为空")
    themes = doc.get("themes")
    if not isinstance(themes, list) or not themes:
        errors.append("voices: themes 必须是非空数组")
        return errors
    for i, theme in enumerate(themes):
        ident = f"voices.themes[{i}]"
        if not isinstance(theme, dict):
            errors.append(f"{ident}: 必须是对象")
            continue
        for field in ("title", "summary"):
            obj = theme.get(field)
            for lang in LANGS:
                if not isinstance(obj, dict) or not str(obj.get(lang) or "").strip():
                    errors.append(f"{ident}: {field}.{lang} 缺失或为空")
        quotes = theme.get("quotes")
        if not isinstance(quotes, list) or not quotes:
            errors.append(f"{ident}: quotes 必须是非空数组")
            continue
        for j, quote in enumerate(quotes):
            if not isinstance(quote, dict) or not quote.get("text") or \
               not str(quote.get("url") or "").startswith("http"):
                errors.append(f"{ident}.quotes[{j}]: 缺少 text 或合法 url")
    return errors


def load_weekly(week: str) -> dict | None:
    """读取并校验周汇总；不存在返回 None，不合格抛 ValueError。"""
    path = weekly_path(week)
    if not path.exists():
        return None
    doc = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_weekly(doc)
    if errors:
        raise ValueError("；".join(errors))
    return doc
