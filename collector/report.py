"""生成 docs/ 全套站点（GitHub Pages 从此目录服务）。

docs/index.html      Dashboard（fetch 加载周数据）
docs/data/<week>.json 每周全量已合并项目（总分降序）
docs/data/weeks.json  周索引：trend、奖项、起飞榜
docs/feed.xml         RSS 2.0
"""
from __future__ import annotations

import datetime
import email.utils
import json
import pathlib
from xml.sax.saxutils import escape

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
             out_dir: pathlib.Path = DOCS_DIR) -> pathlib.Path:
    trends = trends or {}
    scored = [p for p in history if isinstance(p.get("scores"), dict)]
    data_dir = out_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    weeks_index, week_projects = [], {}
    for week in weeks(scored):
        projects = sorted(by_week(scored, week),
                          key=lambda p: (-p["scores"]["total"], p["id"]))
        week_projects[week] = projects
        _write_json(data_dir / f"{week}.json", projects)
        weeks_index.append({
            "week": week,
            "count": len(projects),
            "trend": trends.get(week),
            "awards": compute_awards(projects),
        })

    _write_json(data_dir / "weeks.json", {"weeks": weeks_index, "liftoff": liftoff or []})
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
}
:root[data-theme="dark"] {
  --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7;
  --muted: #898781; --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
  --whimsy: #3987e5; --fun: #199e70; --money: #c98500;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    --page: #0d0d0d; --surface: #1a1a19; --ink: #ffffff; --ink-2: #c3c2b7;
    --muted: #898781; --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
    --whimsy: #3987e5; --fun: #199e70; --money: #c98500;
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
.head-links a, #theme-toggle {
  border: 1px solid var(--border); background: var(--surface); text-decoration: none;
  color: var(--ink-2); border-radius: 8px; padding: 4px 10px; cursor: pointer; font-size: 13px;
}
.banner {
  margin: 14px 0 0; padding: 12px 16px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 12px; font-size: 14px;
}
.banner .label { font-weight: 700; margin-right: 6px; }
.awards { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 10px; }
.award {
  font-size: 12.5px; border: 1px solid var(--grid); border-radius: 999px;
  padding: 3px 10px; background: var(--page); cursor: pointer;
}
.award b { font-weight: 650; }
.liftoff { margin-top: 10px; }
.liftoff summary { cursor: pointer; font-size: 13.5px; font-weight: 650; }
.liftoff table { border-collapse: collapse; margin-top: 8px; font-size: 13px; width: 100%; max-width: 720px; }
.liftoff td, .liftoff th { text-align: left; padding: 4px 10px 4px 0; border-bottom: 1px solid var(--grid); }
.liftoff th { color: var(--muted); font-weight: 500; font-size: 12px; }
.liftoff .num { font-variant-numeric: tabular-nums; }
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
input[type="search"] { min-width: 180px; flex: 1; }
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
}
.card-head { display: flex; gap: 8px; align-items: flex-start; }
.name { color: var(--ink); font-weight: 650; font-size: 15px; text-decoration: none; word-break: break-word; }
.name:hover { text-decoration: underline; }
.tag {
  margin-left: auto; flex: none; font-size: 11px; color: var(--ink-2);
  border: 1px solid var(--grid); border-radius: 999px; padding: 1px 8px; white-space: nowrap;
}
.hot { flex: none; font-size: 11px; border-radius: 999px; padding: 1px 8px;
       background: var(--page); border: 1px solid var(--grid); }
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
</style>
</head>
<body>
<header>
  <h1>AI 周报</h1>
  <span class="sub">天马行空 · 有趣 · 有钱途 — 每周五自动收集</span>
  <div class="head-links">
    <a href="feed.xml" title="RSS 订阅">📡 RSS</a>
    <button id="theme-toggle" type="button">🌓 主题</button>
  </div>
</header>
<div class="banner" id="trend" hidden>
  <span class="label">🧭 <span data-i18n="trend">本周风向</span></span><span id="trend-text"></span>
  <div class="awards" id="awards"></div>
</div>
<details class="liftoff" id="liftoff" hidden>
  <summary>🚀 起飞榜 — 历史高分项目 star 增长追踪</summary>
  <table><thead><tr><th>项目</th><th>入库时 ★</th><th>当前 ★</th><th>增幅</th><th>收录周</th></tr></thead>
  <tbody id="liftoff-body"></tbody></table>
</details>
<div class="filters">
  <label>周</label><select id="f-week"></select>
  <label>来源</label><select id="f-source"><option value="all">全部</option></select>
  <label>排序</label>
  <select id="f-sort">
    <option value="total">总分</option><option value="whimsy">天马行空</option>
    <option value="fun">有趣</option><option value="money">有钱途</option>
  </select>
  <span class="lang-switch" id="lang-switch">
    <button data-lang="zh" class="on">中</button><button data-lang="en">EN</button>
  </span>
  <input id="f-q" type="search" placeholder="搜索名称 / 描述 / 解读…">
</div>
<div class="count" id="count"></div>
<main id="cards"></main>
<script>
const DIMS = [["whimsy","天马行空"],["fun","有趣"],["money","有钱途"]];
const DEEP_TITLES = {zh: {what: "是什么", why: "为什么值得看", biz: "商业潜力与风险"},
                     en: {what: "What it is", why: "Why it matters", biz: "Business & risks"}};
const SOURCE_LABELS = {github:"GitHub", hackernews:"Hacker News", producthunt:"Product Hunt",
                       arxiv:"arXiv", huggingface:"Hugging Face", reddit:"Reddit"};
const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

const saved = localStorage.getItem("theme");
if (saved) document.documentElement.dataset.theme = saved;
$("theme-toggle").onclick = () => {
  const dark = getComputedStyle(document.documentElement).getPropertyValue("--page").trim() === "#0d0d0d";
  const next = dark ? "light" : "dark";
  document.documentElement.dataset.theme = next;
  localStorage.setItem("theme", next);
};

let WEEKS = [], LIFTOFF = [], CURRENT = [], LANG = localStorage.getItem("lang") || "zh";
const weekCache = {};

async function fetchWeek(week) {
  if (!weekCache[week]) weekCache[week] = await (await fetch(`data/${week}.json`)).json();
  return weekCache[week];
}

function metricsLine(p) {
  const m = p.metrics || {};
  const parts = [];
  if (m.stars) parts.push(`★ ${m.stars}`);
  if (m.points) parts.push(`▲ ${m.points} 分`);
  if (m.upvotes) parts.push(`▲ ${m.upvotes}`);
  if (m.likes) parts.push(`♥ ${m.likes}`);
  if (m.week_rank) parts.push(`周榜 #${m.week_rank}`);
  if (m.subreddit) parts.push(`r/${esc(m.subreddit)}`);
  if (m.comments) parts.push(`💬 ${m.comments}`);
  return parts.join(" · ");
}

function card(p) {
  const bars = DIMS.map(([key, label]) => `
    <span class="dim">${label}</span>
    <span class="track"><span class="fill" style="width:${(p.scores[key] || 0) * 10}%;background:var(--${key})"></span></span>
    <span class="val">${p.scores[key]}</span>`).join("");
  const discuss = (p.metrics || {}).hn_link || (p.metrics || {}).reddit_link;
  const analysis = (p.analysis || {})[LANG];
  const dd = (p.deep_dive || {})[LANG];
  const deepHtml = dd ? `<details class="deep"><summary>🔥 ${LANG === "zh" ? "深度解读" : "Deep dive"}</summary>
      ${["what","why","biz"].map(k => `<h4>${DEEP_TITLES[LANG][k]}</h4><p>${esc(dd[k])}</p>`).join("")}
    </details>` : "";
  return `<article class="card" id="${esc(p.id)}">
    <div class="card-head">
      <a class="name" href="${esc(p.url)}" target="_blank" rel="noopener">${esc(p.name)}</a>
      ${p.deep_dive ? '<span class="hot">🔥 Top 10</span>' : ""}
      <span class="tag">${SOURCE_LABELS[p.source] || esc(p.source)}</span>
    </div>
    <p class="reason">${esc(p.reason)}</p>
    ${analysis ? `<p class="analysis">${esc(analysis)}</p>` : ""}
    ${deepHtml}
    <div class="scores">${bars}</div>
    <div class="total-row">
      <span class="total">总分 ${p.scores.total} / 30</span>
      <span class="meta">${metricsLine(p)}${discuss ? ` · <a href="${esc(discuss)}" target="_blank" rel="noopener">讨论</a>` : ""} · ${p.week}</span>
    </div>
  </article>`;
}

function renderBanner(weekInfo) {
  if (!weekInfo) { $("trend").hidden = true; return; }
  const trend = (weekInfo.trend || {})[LANG] || (weekInfo.trend || {}).zh;
  const byId = Object.fromEntries(CURRENT.map(p => [p.id, p]));
  const awardsHtml = (weekInfo.awards || []).map(a => {
    const p = byId[a.project_id];
    return `<span class="award" onclick="document.getElementById('${esc(a.project_id)}')?.scrollIntoView({behavior:'smooth'})">
      ${a.emoji} <b>${esc(a.title[LANG] || a.title.zh)}</b>${p ? " · " + esc(p.name) : ""}</span>`;
  }).join("");
  $("trend-text").textContent = trend || "";
  $("awards").innerHTML = awardsHtml;
  $("trend").hidden = !trend && !awardsHtml;
}

function renderLiftoff() {
  if (!LIFTOFF.length) { $("liftoff").hidden = true; return; }
  $("liftoff").hidden = false;
  $("liftoff-body").innerHTML = LIFTOFF.slice(0, 10).map(r => `<tr>
    <td><a class="name" href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.name)}</a></td>
    <td class="num">${r.stars_then}</td><td class="num">${r.stars_now}</td>
    <td class="num">×${r.ratio}</td><td>${esc(r.week)}</td></tr>`).join("");
}

function render() {
  const source = $("f-source").value, sort = $("f-sort").value,
        q = $("f-q").value.trim().toLowerCase();
  let rows = CURRENT.filter(p =>
    (source === "all" || p.source === source) &&
    (!q || `${p.name} ${p.description} ${p.reason} ${JSON.stringify(p.analysis || "")}`.toLowerCase().includes(q)));
  rows = [...rows].sort((a, b) => (b.scores[sort] ?? 0) - (a.scores[sort] ?? 0)
                                  || b.scores.total - a.scores.total);
  $("cards").innerHTML = rows.map(card).join("") || `<div class="empty">没有匹配的项目</div>`;
  $("count").textContent = `${rows.length} 个项目`;
}

async function loadWeek(week) {
  CURRENT = week === "all"
    ? (await Promise.all(WEEKS.map(w => fetchWeek(w.week)))).flat()
    : await fetchWeek(week);
  const sources = [...new Set(CURRENT.map(p => p.source))].sort();
  const cur = $("f-source").value;
  $("f-source").innerHTML = `<option value="all">全部</option>` +
    sources.map(s => `<option value="${s}">${SOURCE_LABELS[s] || s}</option>`).join("");
  if ([...$("f-source").options].some(o => o.value === cur)) $("f-source").value = cur;
  renderBanner(week === "all" ? null : WEEKS.find(w => w.week === week));
  render();
}

async function init() {
  const meta = await (await fetch("data/weeks.json")).json();
  WEEKS = meta.weeks || [];
  LIFTOFF = meta.liftoff || [];
  if (!WEEKS.length) { $("cards").innerHTML = `<div class="empty">还没有数据</div>`; return; }
  $("f-week").innerHTML = WEEKS.map(w => `<option value="${w.week}">${w.week}</option>`).join("")
                          + `<option value="all">全部周</option>`;
  const hashWeek = location.hash.replace("#", "");
  if (WEEKS.some(w => w.week === hashWeek)) $("f-week").value = hashWeek;
  renderLiftoff();
  document.querySelectorAll("#lang-switch button").forEach(b => {
    b.classList.toggle("on", b.dataset.lang === LANG);
    b.onclick = () => {
      LANG = b.dataset.lang; localStorage.setItem("lang", LANG);
      document.querySelectorAll("#lang-switch button").forEach(x =>
        x.classList.toggle("on", x.dataset.lang === LANG));
      renderBanner($("f-week").value === "all" ? null : WEEKS.find(w => w.week === $("f-week").value));
      render();
    };
  });
  $("f-week").onchange = () => { location.hash = $("f-week").value; loadWeek($("f-week").value); };
  for (const id of ["f-source", "f-sort"]) $(id).onchange = render;
  $("f-q").oninput = render;
  await loadWeek($("f-week").value);
}
init();
</script>
</body>
</html>
"""
