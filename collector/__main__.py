"""CLI 入口。用法见 CLAUDE.md「运行方式」。"""
from __future__ import annotations

import datetime
import json
import sys

from . import filter as filter_mod
from . import scoring, store
from .schema import week_of
from .sources import arxiv, github, hackernews, huggingface, producthunt, reddit

ALL_SOURCES = (github, hackernews, producthunt, arxiv, huggingface, reddit)


def cmd_collect(args: list[str]) -> int:
    today = datetime.date.fromisoformat(args[0]) if args else datetime.date.today()
    week = week_of(today)

    collected = []
    for mod in ALL_SOURCES:
        try:
            batch = mod.fetch(today)
            print(f"ok   {mod.NAME}: {len(batch)} 条")
            collected.extend(batch)
        except Exception as e:
            print(f"警告 {mod.NAME}: 抓取失败，已跳过 — {e}", file=sys.stderr)

    history = store.load()
    candidates = filter_mod.filter_projects(collected, store.known_ids(history))
    path = store.CANDIDATES_DIR / f"{week}.json"
    store.save(candidates, path)

    by_source = {}
    for p in candidates:
        by_source[p["source"]] = by_source.get(p["source"], 0) + 1
    print(f"\n粗筛后候选 {len(candidates)} 条（原始 {len(collected)} 条）→ {path}")
    print("  " + ", ".join(f"{k}: {v}" for k, v in sorted(by_source.items())))
    print(f"\n下一步：python3 -m collector prompt {week}")
    return 0


def _load_week(week: str) -> tuple[list[dict], "object", "object"]:
    candidates_path = store.CANDIDATES_DIR / f"{week}.json"
    scored_path = store.SCORED_DIR / f"{week}.json"
    if not candidates_path.exists():
        print(f"错误: 候选文件不存在 {candidates_path}", file=sys.stderr)
        sys.exit(1)
    return store.load(candidates_path), candidates_path, scored_path


def cmd_prompt(args: list[str]) -> int:
    week = args[0] if args else week_of(datetime.date.today())
    candidates, _, scored_path = _load_week(week)
    print(scoring.build_prompt(candidates, week, str(scored_path)))
    return 0


def cmd_validate(args: list[str]) -> int:
    week = args[0] if args else week_of(datetime.date.today())
    candidates, _, scored_path = _load_week(week)
    if not scored_path.exists():
        print(f"错误: 评分文件不存在 {scored_path}", file=sys.stderr)
        return 1
    try:
        scored = json.loads(scored_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"错误: 评分文件不是合法 JSON — {e}", file=sys.stderr)
        return 1
    errors = scoring.validate_scored(candidates, scored)
    if errors:
        print(f"校验失败，共 {len(errors)} 处：", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    entry_count = len(scored.get("entries", [])) if isinstance(scored, dict) else len(scored)
    print(f"校验通过：{entry_count} 条评分。下一步：python3 -m collector report")
    return 0


def cmd_report(args: list[str]) -> int:
    from . import report, tracking, voices as voices_mod

    history = store.load()
    merged_weeks, trends = [], {}
    for scored_path in sorted(store.SCORED_DIR.glob("*.json")):
        week = scored_path.stem
        candidates_path = store.CANDIDATES_DIR / f"{week}.json"
        if not candidates_path.exists():
            continue
        candidates = store.load(candidates_path)
        scored = json.loads(scored_path.read_text(encoding="utf-8"))
        if isinstance(scored, dict) and isinstance(scored.get("trend"), dict):
            trends[week] = scored["trend"]
        # v1 数组是历史遗留，直接合并；v2 对象需通过校验
        if isinstance(scored, dict) and scoring.validate_scored(candidates, scored):
            print(f"警告: {week} 评分未通过校验，跳过合并", file=sys.stderr)
            continue
        history = store.merge(history, scoring.merge_scored(candidates, scored))
        merged_weeks.append(week)

    store.save(history)
    liftoff = tracking.compute_liftoff(history, tracking.load_tracking())
    all_voices = {}
    for voices_path in sorted(voices_mod.WEEKLY_DIR.glob("*.json")):
        week = voices_path.stem
        if not week.count("-W"):
            continue
        try:
            doc = voices_mod.load_weekly(week)
            if doc:
                all_voices[week] = doc
        except ValueError as e:
            print(f"警告: {week} 大佬之声未通过校验，跳过 — {e}", file=sys.stderr)
    html_path = report.generate(history, trends=trends, liftoff=liftoff, voices=all_voices)
    print(f"已合并周: {', '.join(merged_weeks) or '(无新增)'}；累积 {len(history)} 条")
    print(f"站点 → {html_path}（线上 {report.SITE_URL}）")
    return 0


def cmd_feishu(args: list[str]) -> int:
    from . import feishu
    from .awards import compute_awards

    dry_run = "--dry-run" in args
    args = [a for a in args if a != "--dry-run"]
    week = args[0] if args else week_of(datetime.date.today())

    history = store.load()
    week_projects = sorted(
        [p for p in store.by_week(history, week) if isinstance(p.get("scores"), dict)],
        key=lambda p: (-p["scores"]["total"], p["id"]))
    if not week_projects:
        print(f"错误: 累积库中没有 {week} 的已评分项目，请先跑 report", file=sys.stderr)
        return 1
    scored_path = store.SCORED_DIR / f"{week}.json"
    trend_zh = ""
    if scored_path.exists():
        scored = json.loads(scored_path.read_text(encoding="utf-8"))
        if isinstance(scored, dict):
            trend_zh = (scored.get("trend") or {}).get("zh", "")

    card = feishu.build_card(week, trend_zh, week_projects[:10],
                             compute_awards(week_projects))
    if dry_run:
        print(json.dumps(card, ensure_ascii=False, indent=1))
        return 0
    url = feishu.webhook_url()
    if not url:
        print(feishu.SETUP_HINT)
        return 0
    feishu.send(card, url)
    print(f"已推送 {week} Top {min(10, len(week_projects))} 到飞书")
    return 0


def cmd_voices(args: list[str]) -> int:
    from . import voices

    today = datetime.date.fromisoformat(args[0]) if args else datetime.date.today()
    path = voices.collect_daily(today)
    posts = json.loads(path.read_text(encoding="utf-8"))
    authors = sorted({p["author"] for p in posts})
    print(f"已采集 {len(posts)} 条发言（{len(authors)} 人）→ {path}")
    print("  " + ", ".join(authors[:8]) + ("…" if len(authors) > 8 else ""))
    print("（每日快照仅本地保存，不发布；周五由周报任务汇总）")
    return 0


def cmd_voices_prompt(args: list[str]) -> int:
    from . import voices

    week = args[0] if args else week_of(datetime.date.today())
    posts = voices.load_week_posts(week)
    if not posts:
        print(f"本周（{week}）没有每日采集数据；周报的大佬之声区块将自动隐藏。")
        return 0
    print(voices.build_prompt(posts, week))
    return 0


def cmd_track(args: list[str]) -> int:
    from . import tracking

    limit = tracking.DEFAULT_LIMIT
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    history = store.load()
    result = tracking.snapshot(history, datetime.date.today(), limit=limit)
    print(f"快照完成：目标 {result['targets']}，成功 {result['ok']}，失败 {result['failed']}")
    liftoff = tracking.compute_liftoff(history, tracking.load_tracking())
    for row in liftoff[:5]:
        print(f"  ×{row['ratio']}  {row['name']}  {row['stars_then']} → {row['stars_now']} ★")
    print("下一步：python3 -m collector report（把起飞榜渲染进站点）")
    return 0


COMMANDS = {"collect": cmd_collect, "prompt": cmd_prompt, "validate": cmd_validate,
            "report": cmd_report, "feishu": cmd_feishu, "track": cmd_track,
            "voices": cmd_voices, "voices-prompt": cmd_voices_prompt}


def main() -> int:
    argv = sys.argv[1:]
    if not argv or argv[0] not in COMMANDS:
        print("用法: python3 -m collector "
              "{collect [日期]|prompt [周]|validate [周]|report|feishu [周] [--dry-run]|track [--limit N]}",
              file=sys.stderr)
        return 2
    return COMMANDS[argv[0]](argv[1:])


if __name__ == "__main__":
    sys.exit(main())
