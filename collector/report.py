"""生成 docs/ 全套站点（GitHub Pages 从此目录服务）。

docs/index.html       Dashboard（fetch 加载周数据；周报视图 + #archive 归档时间线）
docs/data/<week>.json 每周全量已合并项目（总分降序，带 rank）
docs/data/weeks.json  周索引：trend（含 deep）、awards（含得主名）、top3、qr；顶层 qr_site、liftoff
docs/feed.xml         RSS 2.0
"""
from __future__ import annotations

import datetime
import email.utils
import json
import pathlib
from xml.sax.saxutils import escape

from . import qr
from .awards import compute_awards
from .store import ROOT, by_week, weeks

SITE_URL = "https://ikevinxie.github.io/ai-weekly-radar"
SITE_TITLE = "AI 周报 — 天马行空 · 有趣 · 有钱途"
DOCS_DIR = ROOT / "docs"


def _week_friday(week: str) -> datetime.date:
    year, num = week.split("-W")
    return datetime.date.fromisocalendar(int(year), int(num), 5)


def _first_sentence(text: str) -> str:
    for sep in ("。", ". "):
        if sep in text:
            return text.split(sep)[0] + sep.strip()
    return text


def build_feed(weeks_index: list[dict], week_projects: dict[str, list[dict]],
               site_url: str = SITE_URL) -> str:
    items = []
    for info in weeks_index:
        week = info["week"]
        trend_zh = (info.get("trend") or {}).get("zh") or ""
        top = week_projects.get(week, [])[:10]
        top_lines = "\n".join(
            f"{i}. {p['name']}（{p['scores']['total']}分）— {p.get('reason', '')}"
            for i, p in enumerate(top, 1))
        title = f"AI 周报 {week}"
        if trend_zh:
            title += f"：{_first_sentence(trend_zh)}"
        pub = email.utils.format_datetime(datetime.datetime.combine(
            _week_friday(week), datetime.time(20, 0), tzinfo=datetime.timezone.utc))
        items.append(f"""  <item>
   <title>{escape(title)}</title>
   <link>{escape(f"{site_url}/#{week}")}</link>
   <guid isPermaLink="false">{escape(week)}</guid>
   <pubDate>{pub}</pubDate>
   <description>{escape((trend_zh + chr(10) + chr(10) + top_lines).strip())}</description>
  </item>""")
    newline = "\n"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
 <channel>
  <title>{escape(SITE_TITLE)}</title>
  <link>{escape(site_url)}</link>
  <description>每周五自动收集全球天马行空、有趣、有钱途的 AI 项目，Claude 评分与双语解读。</description>
  <language>zh-cn</language>
{newline.join(items)}
 </channel>
</rss>
"""


def generate(history: list[dict], trends: dict[str, dict] | None = None,
             liftoff: list[dict] | None = None,
             voices: dict[str, dict] | None = None,
             out_dir: pathlib.Path = DOCS_DIR) -> pathlib.Path:
    trends = trends or {}
    voices = voices or {}
    scored = [p for p in history if isinstance(p.get("scores"), dict)]
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    weeks_index, week_projects = [], {}
    for week in weeks(scored):
        projects = sorted(by_week(scored, week),
                          key=lambda p: (-p["scores"]["total"], p["id"]))
        for rank, p in enumerate(projects, 1):
            p["rank"] = rank
        week_projects[week] = projects
        _write_json(data_dir / f"{week}.json", projects)
        names = {p["id"]: p["name"] for p in projects}
        awards = [{**a, "project_name": names.get(a["project_id"], "")}
                  for a in compute_awards(projects)]
        weeks_index.append({
            "week": week,
            "date": _week_friday(week).isoformat(),
            "count": len(projects),
            "trend": trends.get(week),
            "voices": voices.get(week),
            "awards": awards,
            "top3": [{"id": p["id"], "name": p["name"], "total": p["scores"]["total"]}
                     for p in projects[:3]],
            "qr": qr.rows(f"{SITE_URL}/#{week}"),
        })

    _write_json(data_dir / "weeks.json", {
        "weeks": weeks_index,
        "liftoff": liftoff or [],
        "qr_site": qr.rows(SITE_URL + "/"),
    })
    (out_dir / "feed.xml").write_text(build_feed(weeks_index, week_projects), encoding="utf-8")
    index = out_dir / "index.html"
    index.write_text(_TEMPLATE, encoding="utf-8")
    return index


def _write_json(path: pathlib.Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")


_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AI 周报 — 天马行空 · 有趣 · 有钱途</title>
<link rel="alternate" type="application/rss+xml" title="AI 周报 RSS" href="feed.xml">
<style>
:root {
  --page: #f9f9f7; --surface: #fcfcfb; --ink: #0b0b0b; --ink-2: #52514e;
  --muted: #898781; --grid: #e1e0d9; --border: rgba(11,11,11,0.10);
  --whimsy: #2a78d6; --fun: #1baf7a; --money: #eda100;
  --shadow: 0 6px 18px rgba(11,11,11,0.10);
}
:root[data-theme="dark"] {
  --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7;
  --muted: #898781; --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
  --whimsy: #3987e5; --fun: #199e70; --money: #c98500;
  --shadow: 0 6px 18px rgba(0,0,0,0.5);
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7;
    --muted: #898781; --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
    --whimsy: #3987e5; --fun: #199e70; --money: #c98500;
    --shadow: 0 6px 18px rgba(0,0,0,0.5);
  }
}
* { box-sizing: border-box; margin: 0; }
body {
  background: var(--page); color: var(--ink);
  font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif;
  padding: 24px clamp(12px, 4vw, 48px) 64px;
}
header { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; margin-bottom: 4px; }
h1 { font-size: 22px; font-weight: 700; }
.sub { color: var(--ink-2); font-size: 13px; }
.head-links { margin-left: auto; display: flex; gap: 8px; }
.head-links a, .head-links button {
  border: 1px solid var(--border); background: var(--surface); text-decoration: none;
  color: var(--ink-2); border-radius: 8px; padding: 4px 10px; cursor: pointer; font-size: 13px;
}
.banner {
  margin: 14px 0 0; padding: 12px 16px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 12px; font-size: 14px;
}
.banner .label { font-weight: 700; margin-right: 6px; }
#trend-deep-btn {
  display: inline-block; margin-left: 8px; border: 0; background: none; cursor: pointer;
  color: var(--whimsy); font-size: 13px; padding: 0;
}
#trend-deep { margin-top: 8px; padding-top: 8px; border-top: 1px dashed var(--grid);
              color: var(--ink-2); font-size: 13.5px; }
#trend-deep p + p { margin-top: 8px; }
.awards { display: flex; gap: 8px; flex-wrap: nowrap; overflow-x: auto; margin-top: 10px;
          padding-bottom: 4px; scrollbar-width: thin; }
.award {
  flex: none; display: inline-flex; align-items: baseline; gap: 4px; max-width: 260px;
  font-size: 12px; border: 1px solid var(--grid); border-radius: 999px;
  padding: 3px 10px; background: var(--page); cursor: pointer; white-space: nowrap;
  transition: border-color .15s ease;
}
.award:hover { border-color: var(--whimsy); }
.award b { font-weight: 650; }
.award .award-lead { flex: none; }
.award .award-proj { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; }
/* 大佬之声 */
.voices { margin-top: 10px; padding: 12px 16px; background: var(--surface);
          border: 1px solid var(--border); border-radius: 12px; }
.voices .label { font-weight: 700; font-size: 14px; }
.voices-overview { font-size: 13.5px; color: var(--ink-2); margin-top: 6px; }
.voice-theme { border: 1px solid var(--grid); border-radius: 10px; margin-top: 8px; padding: 8px 12px; }
.voice-theme summary { cursor: pointer; font-size: 13px; font-weight: 650; }
.voice-theme summary .hint { font-weight: 400; color: var(--muted); font-size: 12px; }
.voice-summary { font-size: 12.5px; color: var(--ink-2); margin: 8px 0 4px; }
.quote { border-left: 3px solid var(--grid); padding: 4px 0 4px 10px; margin-top: 8px; }
.quote .q-author { font-size: 12px; font-weight: 650; }
.quote .q-author a { color: var(--ink); text-decoration: none; }
.quote .q-author .q-date { color: var(--muted); font-weight: 400; }
.quote .q-text { font-size: 12.5px; color: var(--ink-2); margin-top: 2px; white-space: pre-line; }
.quote .q-link { font-size: 11.5px; }
.quote .q-link a { color: var(--whimsy); text-decoration: none; }
section.fold { margin-top: 10px; }
section.fold > details > summary { cursor: pointer; font-size: 13.5px; font-weight: 650; padding: 4px 0; }
.liftoff table { border-collapse: collapse; margin-top: 8px; font-size: 13px; width: 100%; max-width: 860px; }
.liftoff td, .liftoff th { text-align: left; padding: 5px 12px 5px 0; border-bottom: 1px solid var(--grid); vertical-align: top; }
.liftoff th { color: var(--muted); font-weight: 500; font-size: 12px; }
.liftoff .num { font-variant-numeric: tabular-nums; white-space: nowrap; }
.liftoff .intro { color: var(--ink-2); font-size: 12px; margin-top: 2px; }
#quadrant-wrap { background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
                 padding: 10px; margin-top: 8px; max-width: 720px; }
#quadrant { width: 100%; height: auto; display: block; }
.q-label { font-size: 11px; fill: var(--muted); }
.q-axis { font-size: 11.5px; fill: var(--ink-2); font-weight: 600; }
.q-dot { fill: var(--whimsy); fill-opacity: .78; stroke: var(--surface); stroke-width: 1.5; cursor: pointer;
         transition: r .12s ease; }
.q-dot:hover { fill-opacity: 1; }
.q-name { font-size: 10.5px; fill: var(--ink-2); pointer-events: none; }
#q-tip { position: fixed; z-index: 30; background: var(--surface); border: 1px solid var(--border);
         border-radius: 8px; box-shadow: var(--shadow); padding: 6px 10px; font-size: 12px;
         pointer-events: none; display: none; max-width: 260px; }
.filters {
  display: flex; gap: 10px; flex-wrap: wrap; align-items: center;
  margin: 14px 0 6px; padding: 10px 12px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
}
.filters label { color: var(--muted); font-size: 12px; }
select, input[type="search"] {
  background: var(--page); color: var(--ink); border: 1px solid var(--grid);
  border-radius: 8px; padding: 5px 8px; font-size: 13px;
}
.week-nav { border: 1px solid var(--grid); background: var(--page); color: var(--ink-2);
            border-radius: 8px; padding: 5px 7px; font-size: 11px; cursor: pointer; }
.week-nav:disabled { opacity: .35; cursor: default; }
input[type="search"] { min-width: 160px; flex: 1; }
.lang-switch { display: flex; border: 1px solid var(--grid); border-radius: 8px; overflow: hidden; }
.lang-switch button {
  border: 0; background: var(--page); color: var(--ink-2); padding: 5px 10px;
  font-size: 13px; cursor: pointer;
}
.lang-switch button.on { background: var(--ink); color: var(--page); }
.count { color: var(--muted); font-size: 12px; margin: 8px 2px 14px; }
#cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 14px; }
.card {
  background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
  padding: 14px 16px; display: flex; flex-direction: column; gap: 8px;
  transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
}
.card:hover { transform: translateY(-2px); box-shadow: var(--shadow); border-color: var(--whimsy); }
@media (prefers-reduced-motion: reduce) {
  .card { transition: border-color .15s ease; }
  .card:hover { transform: none; box-shadow: none; }
}
@keyframes card-locate {
  0%, 50% { border-color: var(--money); box-shadow: 0 0 0 4px color-mix(in srgb, var(--money) 45%, transparent), var(--shadow); transform: scale(1.015); }
  25%, 75% { border-color: var(--money); box-shadow: 0 0 0 1px color-mix(in srgb, var(--money) 25%, transparent); transform: scale(1); }
  100% { border-color: var(--border); box-shadow: none; transform: scale(1); }
}
.card.flash { animation: card-locate 2.4s ease-out; }
@media (prefers-reduced-motion: reduce) {
  .card.flash { animation: none; border-color: var(--money); box-shadow: 0 0 0 3px color-mix(in srgb, var(--money) 40%, transparent); }
}
.card-head { display: flex; gap: 8px; align-items: flex-start; flex-wrap: wrap; }
.name { color: var(--ink); font-weight: 650; font-size: 15px; text-decoration: none; word-break: break-word; }
.name:hover { text-decoration: underline; }
.tag {
  margin-left: auto; flex: none; font-size: 11px; color: var(--ink-2);
  border: 1px solid var(--grid); border-radius: 999px; padding: 1px 8px; white-space: nowrap;
}
.hot, .medal { flex: none; font-size: 11px; border-radius: 999px; padding: 1px 8px;
       background: var(--page); border: 1px solid var(--grid); }
.medal { cursor: default; }
.topic { font-size: 11px; color: var(--ink-2); border: 1px dashed var(--grid);
         border-radius: 999px; padding: 1px 8px; cursor: pointer; background: none; }
.topic:hover { border-color: var(--whimsy); color: var(--whimsy); }
.topics { display: flex; gap: 6px; flex-wrap: wrap; }
.reason { font-size: 13.5px; color: var(--ink); }
.reason::before { content: "💡 "; }
.analysis { font-size: 12.5px; color: var(--ink-2); }
.deep { border: 1px solid var(--grid); border-radius: 10px; padding: 8px 10px; }
.deep summary { cursor: pointer; font-size: 12.5px; font-weight: 650; color: var(--ink); }
.deep h4 { font-size: 12px; margin: 8px 0 2px; color: var(--muted); font-weight: 650; }
.deep p { font-size: 12.5px; color: var(--ink-2); }
.scores { display: grid; grid-template-columns: auto 1fr auto; gap: 4px 8px; align-items: center; margin-top: 2px; }
.dim { font-size: 11.5px; color: var(--ink-2); }
.track { display: block; height: 6px; background: var(--grid); border-radius: 4px; overflow: hidden; }
.fill { display: block; height: 100%; border-radius: 4px; }
.val { font-size: 11.5px; color: var(--ink); font-variant-numeric: tabular-nums; min-width: 2ch; text-align: right; }
.total-row { display: flex; align-items: center; gap: 8px; margin-top: 2px; }
.total { font-size: 12px; font-weight: 700; }
.meta { margin-left: auto; font-size: 11px; color: var(--muted); }
.meta a { color: var(--muted); }
.empty { color: var(--muted); padding: 40px 8px; text-align: center; grid-column: 1 / -1; }
/* 归档时间线 */
#archive-view { display: none; max-width: 860px; }
#archive-view h2 { font-size: 17px; margin: 18px 0 6px; }
.timeline { position: relative; margin-top: 14px; padding-left: 22px; }
.timeline::before { content: ""; position: absolute; left: 6px; top: 6px; bottom: 6px;
                    width: 2px; background: var(--grid); }
.tl-item { position: relative; margin-bottom: 16px; }
.tl-item::before { content: ""; position: absolute; left: -20px; top: 14px; width: 10px; height: 10px;
                   border-radius: 50%; background: var(--whimsy); border: 2px solid var(--page); }
.tl-card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
           padding: 12px 16px; cursor: pointer;
           transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease; }
.tl-card:hover { transform: translateY(-2px); box-shadow: var(--shadow); border-color: var(--whimsy); }
.tl-head { display: flex; gap: 10px; align-items: baseline; flex-wrap: wrap; }
.tl-week { font-weight: 700; font-size: 15px; }
.tl-date, .tl-count { color: var(--muted); font-size: 12px; }
.tl-trend { font-size: 13px; color: var(--ink-2); margin-top: 6px; }
.tl-awards { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 8px; font-size: 12px; color: var(--ink-2); }
.tl-top3 { margin-top: 6px; font-size: 12.5px; color: var(--ink-2); }
/* 分享 */
#share-fab { position: fixed; right: 22px; bottom: 22px; z-index: 20;
  width: 48px; height: 48px; border-radius: 50%; border: 1px solid var(--border);
  background: var(--surface); box-shadow: var(--shadow); cursor: pointer; font-size: 20px; }
#share-panel { position: fixed; right: 22px; bottom: 80px; z-index: 20; display: none;
  background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
  box-shadow: var(--shadow); padding: 14px; width: 230px; text-align: center; }
#share-panel.open { display: block; }
#qr-canvas { width: 160px; height: 160px; image-rendering: pixelated;
             background: #fff; padding: 6px; border-radius: 8px; }
.share-hint { font-size: 11.5px; color: var(--muted); margin: 6px 0 10px; }
.share-row { display: flex; gap: 6px; justify-content: center; flex-wrap: wrap; }
.share-row a, .share-row button { border: 1px solid var(--grid); background: var(--page);
  color: var(--ink-2); text-decoration: none; border-radius: 8px; padding: 4px 8px;
  font-size: 12px; cursor: pointer; }
</style>
</head>
<body>
<header>
  <h1>AI 周报</h1>
  <span class="sub" data-ui="sub"></span>
  <div class="head-links">
    <button id="nav-archive" type="button"></button>
    <a href="feed.xml" title="RSS">📡 RSS</a>
    <button id="theme-toggle" type="button">🌓</button>
  </div>
</header>

<div id="week-view">
  <div class="banner" id="trend" hidden>
    <span class="label">🧭 <span data-ui="trend"></span></span><span id="trend-text"></span>
    <button id="trend-deep-btn" type="button"></button>
    <div id="trend-deep" hidden></div>
    <div class="awards" id="awards"></div>
  </div>
  <div class="voices" id="voices" hidden>
    <span class="label">🎙️ <span data-ui="voices"></span></span>
    <div class="voices-overview" id="voices-overview"></div>
    <div id="voices-themes"></div>
  </div>
  <section class="fold"><details id="quadrant-det">
    <summary data-ui="quadrant"></summary>
    <div id="quadrant-wrap"></div>
  </details></section>
  <section class="fold liftoff"><details id="liftoff" hidden>
    <summary data-ui="liftoff"></summary>
    <table><thead><tr id="liftoff-head"></tr></thead><tbody id="liftoff-body"></tbody></table>
  </details></section>
  <div class="filters">
    <label data-ui="week"></label>
    <button id="week-prev" type="button" class="week-nav" title="◀">◀</button>
    <select id="f-week"></select>
    <button id="week-next" type="button" class="week-nav" title="▶">▶</button>
    <label data-ui="source"></label><select id="f-source"></select>
    <label data-ui="tag"></label><select id="f-tag"></select>
    <label data-ui="sort"></label><select id="f-sort"></select>
    <span class="lang-switch" id="lang-switch">
      <button data-lang="zh" class="on">中</button><button data-lang="en">EN</button>
    </span>
    <input id="f-q" type="search">
  </div>
  <div class="count" id="count"></div>
  <main id="cards"></main>
</div>

<div id="archive-view">
  <h2 data-ui="archiveTitle"></h2>
  <div class="timeline" id="timeline"></div>
</div>

<div id="q-tip"></div>
<button id="share-fab" type="button" title="Share">📤</button>
<div id="share-panel">
  <canvas id="qr-canvas" width="160" height="160"></canvas>
  <div class="share-hint" data-ui="scanQr"></div>
  <div class="share-row" id="share-links"></div>
</div>

<script>
const SITE_URL = "https://ikevinxie.github.io/ai-weekly-radar";
const DIM_KEYS = ["whimsy", "fun", "money"];
const SOURCE_LABELS = {github:"GitHub", hackernews:"Hacker News", producthunt:"Product Hunt",
                       arxiv:"arXiv", huggingface:"Hugging Face", reddit:"Reddit"};
const TAG_EN = {"agent":"Agent","视频":"Video","语音":"Voice","图像":"Image","文本":"Text",
  "编码":"Coding","安全":"Security","基建":"Infra","硬件":"Hardware","机器人":"Robotics",
  "论文":"Paper","数据":"Data","效率":"Productivity","创意":"Creative","社区":"Community",
  "商业":"Business","教育":"Education","金融":"Finance","游戏":"Gaming","医疗":"Health"};
const UI = {
  zh: {sub:"天马行空 · 有趣 · 有钱途 — 每周五自动收集", archive:"📅 历史周报", back:"◀ 返回周报",
    trend:"本周风向", trendDeepShow:"展开深度分析 ▾", trendDeepHide:"收起深度分析 ▴",
    quadrant:"🎯 本周象限图 — 天马行空 × 有钱途", liftoff:"🚀 起飞榜 — 历史高分项目 star 增长追踪",
    week:"周", source:"来源", tag:"标签", sort:"排序", all:"全部", allWeeks:"全部周",
    search:"搜索名称 / 描述 / 解读…", items:"个项目", totalOf:"总分", deep:"深度解读",
    voices:"大佬之声 — 本周他们在说什么", quotesN:"条原文",
    top10:"Top 10", noMatch:"没有匹配的项目", noData:"还没有数据", copyLink:"复制链接",
    copied:"已复制 ✓", scanQr:"扫码打开当前页面", discuss:"讨论", weekRank:"周榜",
    dims:{whimsy:"天马行空", fun:"有趣", money:"有钱途"},
    deepTitles:{what:"是什么", why:"为什么值得看", biz:"商业潜力与风险"},
    quad:["🚀 又疯又赚", "💼 闷声发财", "🎈 纯属好玩", "😴 安静路过"],
    liftoffCols:["项目", "入库时 ★", "当前 ★", "增幅", "收录周"],
    archiveTitle:"📅 历史周报时间线", top3:"当周 Top 3", points:"分"},
  en: {sub:"Whimsical · Fun · Money-smelling — auto-collected every Friday", archive:"📅 Archive",
    back:"◀ Back to weekly", trend:"This Week's Trend", trendDeepShow:"Show deep analysis ▾",
    trendDeepHide:"Hide deep analysis ▴", quadrant:"🎯 Quadrant — Whimsy × Money",
    liftoff:"🚀 Liftoff Board — star growth of past high scorers",
    week:"Week", source:"Source", tag:"Tag", sort:"Sort", all:"All", allWeeks:"All weeks",
    search:"Search name / description / analysis…", items:"projects", totalOf:"Total",
    deep:"Deep dive", voices:"Builder Voices — what they said this week", quotesN:"quotes",
    top10:"Top 10", noMatch:"No matching projects", noData:"No data yet",
    copyLink:"Copy link", copied:"Copied ✓", scanQr:"Scan to open this page", discuss:"discuss",
    weekRank:"rank", dims:{whimsy:"Whimsy", fun:"Fun", money:"Money"},
    deepTitles:{what:"What it is", why:"Why it matters", biz:"Business & risks"},
    quad:["🚀 Wild & rich", "💼 Quiet money", "🎈 Just for fun", "😴 Passing by"],
    liftoffCols:["Project", "★ then", "★ now", "Growth", "Week"],
    archiveTitle:"📅 Weekly Archive Timeline", top3:"Top 3", points:"pts"},
};
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const t = () => UI[LANG];

const savedTheme = localStorage.getItem("theme");
if (savedTheme) document.documentElement.dataset.theme = savedTheme;
$("theme-toggle").onclick = () => {
  const dark = getComputedStyle(document.documentElement).getPropertyValue("--page").trim() === "#0d0d0d";
  const next = dark ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("theme", next);
};

let WEEKS = [], LIFTOFF = [], QR_SITE = [], CURRENT = [], AWARD_BY_ID = {};
let LANG = localStorage.getItem("lang") || "zh";
const weekCache = {};

async function fetchWeek(week) {
  if (!weekCache[week]) weekCache[week] = await (await fetch(`data/${week}.json`)).json();
  return weekCache[week];
}
const weekInfo = () => WEEKS.find(w => w.week === $("f-week").value);
const inArchive = () => location.hash === "#archive";

function applyUiStrings() {
  document.documentElement.lang = LANG === "zh" ? "zh-CN" : "en";
  document.querySelectorAll("[data-ui]").forEach(el => {
    const val = t()[el.dataset.ui];
    if (val) el.textContent = val;
  });
  $("nav-archive").textContent = inArchive() ? t().back : t().archive;
  $("f-q").placeholder = t().search;
  $("f-sort").innerHTML = [["total", t().totalOf], ...DIM_KEYS.map(k => [k, t().dims[k]])]
    .map(([v, l]) => `<option value="${v}">${l}</option>`).join("");
  document.querySelectorAll("#lang-switch button").forEach(b =>
    b.classList.toggle("on", b.dataset.lang === LANG));
}

function tagLabel(tag) { return LANG === "zh" ? tag : (TAG_EN[tag] || tag); }

function metricsLine(p) {
  const m = p.metrics || {};
  const parts = [];
  if (m.stars) parts.push(`★ ${m.stars}`);
  if (m.points) parts.push(`▲ ${m.points}`);
  if (m.upvotes) parts.push(`▲ ${m.upvotes}`);
  if (m.likes) parts.push(`♥ ${m.likes}`);
  if (m.week_rank) parts.push(`${t().weekRank} #${m.week_rank}`);
  if (m.subreddit) parts.push(`r/${esc(m.subreddit)}`);
  if (m.comments) parts.push(`💬 ${m.comments}`);
  return parts.join(" · ");
}

function card(p) {
  const bars = DIM_KEYS.map(key => `
    <span class="dim">${t().dims[key]}</span>
    <span class="track"><span class="fill" style="width:${(p.scores[key] || 0) * 10}%;background:var(--${key})"></span></span>
    <span class="val">${p.scores[key]}</span>`).join("");
  const discuss = (p.metrics || {}).hn_link || (p.metrics || {}).reddit_link;
  const analysis = (p.analysis || {})[LANG];
  const dd = (p.deep_dive || {})[LANG];
  const medals = (AWARD_BY_ID[p.id] || []).map(a =>
    `<span class="medal" title="${esc(a.title[LANG] || a.title.zh)}">${a.emoji}</span>`).join("");
  const topics = (p.tags || []).map(tag =>
    `<button class="topic" data-tag="${esc(tag)}" type="button">#${esc(tagLabel(tag))}</button>`).join("");
  // 降密度：双语简读收进「深度解读」折叠区作导语
  const deepHtml = (analysis || dd) ? `<details class="deep"><summary>🔍 ${t().deep}</summary>
      ${analysis ? `<p class="analysis">${esc(analysis)}</p>` : ""}
      ${dd ? ["what","why","biz"].map(k => `<h4>${t().deepTitles[k]}</h4><p>${esc(dd[k])}</p>`).join("") : ""}
    </details>` : "";
  const rankBadge = p.rank === 1 ? "🥇" : p.rank === 2 ? "🥈" : p.rank === 3 ? "🥉"
                    : (p.rank && p.rank <= 10 ? "🔥" : "");
  return `<article class="card" id="${esc(p.id)}">
    <div class="card-head">
      <a class="name" href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.name)}</a>
      ${rankBadge ? `<span class="hot">${rankBadge} ${p.rank <= 3 ? "#" + p.rank : t().top10}</span>` : ""}
      ${medals}
      <span class="tag">${SOURCE_LABELS[p.source] || esc(p.source)}</span>
    </div>
    <p class="reason">${esc(p.reason)}</p>
    ${deepHtml}
    ${topics ? `<div class="topics">${topics}</div>` : ""}
    <div class="scores">${bars}</div>
    <div class="total-row">
      <span class="total">${t().totalOf} ${p.scores.total} / 30</span>
      <span class="meta">${metricsLine(p)}${discuss ? ` · <a href="${esc(discuss)}" target="_blank" rel="noopener">${t().discuss}</a>` : ""} · ${p.week}</span>
    </div>
  </article>`;
}

function scrollToCard(pid) {
  const el = document.getElementById(pid);
  if (!el) return;
  el.scrollIntoView({behavior: "smooth", block: "center"});
  el.classList.remove("flash");
  void el.offsetWidth;             // 重启动画，连续点击也能再次闪烁
  el.classList.add("flash");
  setTimeout(() => el.classList.remove("flash"), 2600);
}

function renderBanner(info) {
  if (!info) { $("trend").hidden = true; $("voices").hidden = true; return; }
  const trend = (info.trend || {})[LANG] || (info.trend || {}).zh;
  const deep = ((info.trend || {}).deep || {})[LANG] || ((info.trend || {}).deep || {}).zh;
  const awardsHtml = (info.awards || []).map(a => {
    const title = a.title[LANG] || a.title.zh;
    const full = a.emoji + " " + title + (a.project_name ? " · " + a.project_name : "");
    return `<span class="award" data-pid="${esc(a.project_id)}" title="${esc(full)}">` +
      `<span class="award-lead">${a.emoji} <b>${esc(title)}</b></span>` +
      (a.project_name ? `<span class="award-proj">· ${esc(a.project_name)}</span>` : "") +
      `</span>`;
  }).join("");
  $("trend-text").textContent = trend || "";
  $("trend-deep").hidden = true;
  // 深度分析按空行分段渲染
  $("trend-deep").innerHTML = (deep || "").split(/\\n{2,}|\\n/).filter(s => s.trim())
    .map(s => `<p>${esc(s)}</p>`).join("");
  $("trend-deep-btn").textContent = t().trendDeepShow;
  $("trend-deep-btn").style.display = deep ? "" : "none";
  $("awards").innerHTML = awardsHtml;
  document.querySelectorAll("#awards .award").forEach(el =>
    el.onclick = () => scrollToCard(el.dataset.pid));
  $("trend").hidden = !trend && !awardsHtml;
  renderVoices(info.voices);
}

function renderVoices(v) {
  if (!v || !v.overview) { $("voices").hidden = true; return; }
  $("voices").hidden = false;
  $("voices-overview").textContent = v.overview[LANG] || v.overview.zh || "";
  $("voices-themes").innerHTML = (v.themes || []).map(theme => {
    const title = (theme.title || {})[LANG] || (theme.title || {}).zh || "";
    const summary = (theme.summary || {})[LANG] || (theme.summary || {}).zh || "";
    const quotes = (theme.quotes || []).map(q => `<div class="quote">
      <div class="q-author"><a href="${esc(q.url)}" target="_blank" rel="noopener">${esc(q.author)}</a>
        <span class="q-date">@${esc(q.handle || "")} · ${esc(q.date || "")}</span></div>
      <div class="q-text">${esc(q.text)}</div>
      <div class="q-link"><a href="${esc(q.url)}" target="_blank" rel="noopener">↗ ${LANG === "zh" ? "原文" : "source"}</a></div>
    </div>`).join("");
    return `<details class="voice-theme"><summary>${esc(title)}
        <span class="hint">· ${(theme.quotes || []).length} ${t().quotesN}</span></summary>
      <div class="voice-summary">${esc(summary)}</div>${quotes}
    </details>`;
  }).join("");
}
$("trend-deep-btn").onclick = () => {
  const box = $("trend-deep");
  box.hidden = !box.hidden;
  $("trend-deep-btn").textContent = box.hidden ? t().trendDeepShow : t().trendDeepHide;
};

function renderLiftoff() {
  const det = $("liftoff");
  if (!LIFTOFF.length) { det.hidden = true; return; }
  det.hidden = false;
  $("liftoff-head").innerHTML = t().liftoffCols.map(c => `<th>${c}</th>`).join("");
  $("liftoff-body").innerHTML = LIFTOFF.slice(0, 10).map(r => {
    const intro = LANG === "zh" ? (r.reason || "") : ((r.analysis || {}).en || r.reason || "");
    return `<tr>
    <td><a class="name" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name)}</a>
      ${intro ? `<div class="intro">${esc(intro)}</div>` : ""}</td>
    <td class="num">${r.stars_then}</td><td class="num">${r.stars_now}</td>
    <td class="num">×${r.ratio}</td><td class="num">${esc(r.week)}</td></tr>`;
  }).join("");
}

function hash32(s) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
  return (h >>> 0) / 4294967295;
}

function renderQuadrant() {
  const W = 720, H = 460, P = 44;
  const sx = v => P + v / 10 * (W - 2 * P);
  const sy = v => H - P - v / 10 * (H - 2 * P);
  const pts = CURRENT.map(p => {
    const jx = (hash32(p.id) - 0.5) * 0.62, jy = (hash32(p.id + "y") - 0.5) * 0.62;
    return {p, x: sx(Math.min(10, Math.max(0, p.scores.whimsy + jx))),
            y: sy(Math.min(10, Math.max(0, p.scores.money + jy)))};
  });
  const awarded = new Set(Object.keys(AWARD_BY_ID));
  const labels = pts.filter(o => awarded.has(o.p.id)).slice(0, 6).map(o =>
    `<text class="q-name" x="${o.x + 8}" y="${o.y + 3}">${esc(o.p.name.slice(0, 22))}</text>`).join("");
  const [q1, q2, q3, q4] = t().quad;
  $("quadrant-wrap").innerHTML = `<svg id="quadrant" viewBox="0 0 ${W} ${H}" role="img">
    <line x1="${P}" y1="${sy(5)}" x2="${W - P}" y2="${sy(5)}" stroke="var(--grid)" stroke-dasharray="4 4"/>
    <line x1="${sx(5)}" y1="${P}" x2="${sx(5)}" y2="${H - P}" stroke="var(--grid)" stroke-dasharray="4 4"/>
    <line x1="${P}" y1="${H - P}" x2="${W - P}" y2="${H - P}" stroke="var(--grid)"/>
    <line x1="${P}" y1="${P}" x2="${P}" y2="${H - P}" stroke="var(--grid)"/>
    <text class="q-axis" x="${W - P}" y="${H - P + 26}" text-anchor="end">${t().dims.whimsy} →</text>
    <text class="q-axis" x="${P - 30}" y="${P - 12}">${t().dims.money} ↑</text>
    <text class="q-label" x="${W - P - 4}" y="${P + 12}" text-anchor="end">${q1}</text>
    <text class="q-label" x="${P + 4}" y="${P + 12}">${q2}</text>
    <text class="q-label" x="${W - P - 4}" y="${H - P - 8}" text-anchor="end">${q3}</text>
    <text class="q-label" x="${P + 4}" y="${H - P - 8}">${q4}</text>
    ${pts.map(o => `<circle class="q-dot" r="5.5" cx="${o.x}" cy="${o.y}" data-pid="${esc(o.p.id)}"/>`).join("")}
    ${labels}
  </svg>`;
  const tip = $("q-tip");
  document.querySelectorAll(".q-dot").forEach(dot => {
    const p = CURRENT.find(x => x.id === dot.dataset.pid);
    dot.onmousemove = e => {
      tip.style.display = "block";
      tip.style.left = Math.min(e.clientX + 14, innerWidth - 280) + "px";
      tip.style.top = (e.clientY + 14) + "px";
      tip.innerHTML = `<b>${esc(p.name)}</b><br>${DIM_KEYS.map(k =>
        `${t().dims[k]} ${p.scores[k]}`).join(" · ")}`;
    };
    dot.onmouseleave = () => tip.style.display = "none";
    dot.onclick = () => { tip.style.display = "none"; scrollToCard(p.id); };
  });
}

function render() {
  const source = $("f-source").value, tag = $("f-tag").value,
        sort = $("f-sort").value, q = $("f-q").value.trim().toLowerCase();
  let rows = CURRENT.filter(p =>
    (source === "all" || p.source === source) &&
    (tag === "all" || (p.tags || []).includes(tag)) &&
    (!q || `${p.name} ${p.description} ${p.reason} ${JSON.stringify(p.analysis || "")}`.toLowerCase().includes(q)));
  rows = [...rows].sort((a, b) => (b.scores[sort] ?? 0) - (a.scores[sort] ?? 0)
                                  || b.scores.total - a.scores.total);
  $("cards").innerHTML = rows.map(card).join("") || `<div class="empty">${t().noMatch}</div>`;
  $("count").textContent = `${rows.length} ${t().items}`;
  document.querySelectorAll(".topic").forEach(el => el.onclick = () => {
    $("f-tag").value = el.dataset.tag;
    render();
  });
}

function rebuildFilters() {
  const keep = (sel, val) => [...sel.options].some(o => o.value === val) ? val : "all";
  const src = $("f-source").value, tg = $("f-tag").value;
  const sources = [...new Set(CURRENT.map(p => p.source))].sort();
  $("f-source").innerHTML = `<option value="all">${t().all}</option>` +
    sources.map(s => `<option value="${s}">${SOURCE_LABELS[s] || s}</option>`).join("");
  $("f-source").value = keep($("f-source"), src);
  const tags = [...new Set(CURRENT.flatMap(p => p.tags || []))].sort();
  $("f-tag").innerHTML = `<option value="all">${t().all}</option>` +
    tags.map(x => `<option value="${x}">#${tagLabel(x)}</option>`).join("");
  $("f-tag").value = keep($("f-tag"), tg);
}

async function loadWeek(week) {
  CURRENT = week === "all"
    ? (await Promise.all(WEEKS.map(w => fetchWeek(w.week)))).flat()
    : await fetchWeek(week);
  const info = week === "all" ? null : weekInfo();
  AWARD_BY_ID = {};
  for (const a of (info?.awards || [])) (AWARD_BY_ID[a.project_id] ??= []).push(a);
  rebuildFilters();
  renderBanner(info);
  renderQuadrant();
  render();
  renderShare();
  const opts = [...$("f-week").options].map(o => o.value).filter(v => v !== "all");
  const idx = opts.indexOf($("f-week").value);
  $("week-prev").disabled = idx < 0 || idx >= opts.length - 1;
  $("week-next").disabled = idx <= 0;
}

function renderArchive() {
  $("timeline").innerHTML = WEEKS.map(w => {
    const trend = (w.trend || {})[LANG] || (w.trend || {}).zh || "";
    const awards = (w.awards || []).map(a =>
      `<span>${a.emoji} ${esc(a.title[LANG] || a.title.zh)} · ${esc(a.project_name)}</span>`).join("");
    const top3 = (w.top3 || []).map((p, i) =>
      `${i + 1}. ${esc(p.name)}（${p.total}${t().points}）`).join("　");
    return `<div class="tl-item"><div class="tl-card" data-week="${w.week}">
      <div class="tl-head"><span class="tl-week">${w.week}</span>
        <span class="tl-date">${w.date || ""}</span>
        <span class="tl-count">${w.count} ${t().items}</span></div>
      ${trend ? `<div class="tl-trend">🧭 ${esc(trend)}</div>` : ""}
      ${top3 ? `<div class="tl-top3">${t().top3}: ${top3}</div>` : ""}
      ${awards ? `<div class="tl-awards">${awards}</div>` : ""}
    </div></div>`;
  }).join("") || `<div class="empty">${t().noData}</div>`;
  document.querySelectorAll(".tl-card").forEach(el =>
    el.onclick = () => { location.hash = el.dataset.week; });
}

/* ---- 分享 ---- */
function currentShare() {
  if (inArchive()) return {url: SITE_URL + "/#archive", qr: QR_SITE};
  const info = weekInfo();
  if (info) return {url: `${SITE_URL}/#${info.week}`, qr: info.qr || QR_SITE};
  return {url: SITE_URL + "/", qr: QR_SITE};
}

function drawQr(rows) {
  const canvas = $("qr-canvas");
  const ctx = canvas.getContext("2d");
  const n = rows.length;
  const scale = Math.floor(160 / n) || 1;
  canvas.width = canvas.height = n * scale;
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = "#000000";
  for (let r = 0; r < n; r++)
    for (let c = 0; c < n; c++)
      if (rows[r][c] === "1") ctx.fillRect(c * scale, r * scale, scale, scale);
}

function renderShare() {
  const {url, qr} = currentShare();
  if (qr && qr.length) drawQr(qr);
  const text = document.title;
  const enc = encodeURIComponent;
  $("share-links").innerHTML = `
    <button id="copy-link" type="button">🔗 ${t().copyLink}</button>
    <a href="https://service.weibo.com/share/share.php?url=${enc(url)}&title=${enc(text)}" target="_blank" rel="noopener">微博</a>
    <a href="https://twitter.com/intent/tweet?url=${enc(url)}&text=${enc(text)}" target="_blank" rel="noopener">X</a>
    <a href="https://t.me/share/url?url=${enc(url)}&text=${enc(text)}" target="_blank" rel="noopener">Telegram</a>
    <a href="https://www.linkedin.com/sharing/share-offsite/?url=${enc(url)}" target="_blank" rel="noopener">LinkedIn</a>`;
  $("copy-link").onclick = async () => {
    try { await navigator.clipboard.writeText(url); } catch (e) {
      const ta = document.createElement("textarea");
      ta.value = url; document.body.appendChild(ta); ta.select();
      document.execCommand("copy"); ta.remove();
    }
    $("copy-link").textContent = t().copied;
    setTimeout(renderShare, 1200);
  };
}
$("share-fab").onclick = () => $("share-panel").classList.toggle("open");
document.addEventListener("click", e => {
  if (!$("share-panel").contains(e.target) && e.target !== $("share-fab"))
    $("share-panel").classList.remove("open");
});

/* ---- 路由 ---- */
async function route() {
  applyUiStrings();
  if (inArchive()) {
    $("week-view").style.display = "none";
    $("archive-view").style.display = "block";
    renderArchive();
  } else {
    $("archive-view").style.display = "none";
    $("week-view").style.display = "block";
    const hashWeek = location.hash.replace("#", "");
    if (WEEKS.some(w => w.week === hashWeek)) $("f-week").value = hashWeek;
    else if (hashWeek === "all") $("f-week").value = "all";
    await loadWeek($("f-week").value);
  }
  renderShare();
}

$("nav-archive").onclick = () => {
  location.hash = inArchive() ? ($("f-week").value || "") : "archive";
};
window.addEventListener("hashchange", route);

async function init() {
  const meta = await (await fetch("data/weeks.json")).json();
  WEEKS = meta.weeks || [];
  LIFTOFF = meta.liftoff || [];
  QR_SITE = meta.qr_site || [];
  applyUiStrings();
  if (!WEEKS.length) { $("cards").innerHTML = `<div class="empty">${t().noData}</div>`; return; }
  $("f-week").innerHTML = WEEKS.map(w => `<option value="${w.week}">${w.week}</option>`).join("")
                          + `<option value="all">${t().allWeeks}</option>`;
  renderLiftoff();
  document.querySelectorAll("#lang-switch button").forEach(b => {
    b.onclick = () => {
      LANG = b.dataset.lang; localStorage.setItem("lang", LANG);
      applyUiStrings(); renderLiftoff();
      if (inArchive()) renderArchive();
      else { rebuildFilters(); renderBanner($("f-week").value === "all" ? null : weekInfo());
             renderQuadrant(); render(); }
      renderShare();
    };
  });
  $("f-week").onchange = () => { location.hash = $("f-week").value; };
  const stepWeek = dir => {
    const options = [...$("f-week").options].map(o => o.value).filter(v => v !== "all");
    const i = options.indexOf($("f-week").value);
    const next = options[i + dir];                 // 列表按新→旧排；▶=更新的一周
    if (next) location.hash = next;
  };
  $("week-prev").onclick = () => stepWeek(1);
  $("week-next").onclick = () => stepWeek(-1);
  for (const id of ["f-source", "f-tag", "f-sort"]) $(id).onchange = render;
  $("f-q").oninput = render;
  await route();
}
init();
</script>
</body>
</html>
"""
