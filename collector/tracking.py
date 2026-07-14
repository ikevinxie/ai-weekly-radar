"""起飞追踪：每月回访历史高分 GitHub 项目的 star 增长。见 SPEC.md「起飞追踪」。"""
from __future__ import annotations

import datetime
import json
import pathlib
import sys
import time

from .net import fetch_json
from .store import ROOT

TRACKING_PATH = ROOT / "data" / "tracking.json"
DEFAULT_LIMIT = 50


def load_tracking(path: pathlib.Path = TRACKING_PATH) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def save_tracking(tracking: dict, path: pathlib.Path = TRACKING_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tracking, ensure_ascii=False, indent=1), encoding="utf-8")


def github_targets(history: list[dict], limit: int = DEFAULT_LIMIT) -> list[dict]:
    """累积库中已评分的 GitHub 项目，按 total 降序取前 limit。"""
    projects = [p for p in history
                if p.get("source") == "github" and isinstance(p.get("scores"), dict)]
    projects.sort(key=lambda p: (-p["scores"]["total"], p["id"]))
    return projects[:limit]


def parse_repo(payload: dict) -> int:
    stars = payload.get("stargazers_count")
    if not isinstance(stars, int):
        raise ValueError(f"GitHub 响应缺少 stargazers_count: {str(payload)[:120]}")
    return stars


def fetch_stars(repo_full_name: str) -> int:
    return parse_repo(fetch_json(f"https://api.github.com/repos/{repo_full_name}"))


def snapshot(history: list[dict], today: datetime.date,
             limit: int = DEFAULT_LIMIT, path: pathlib.Path = TRACKING_PATH,
             delay: float = 0.5) -> dict:
    """给目标项目追加一条 {date, stars} 快照。同日重复运行会覆盖当日值，不叠加。"""
    tracking = load_tracking(path)
    targets = github_targets(history, limit)
    ok = failed = 0
    for i, p in enumerate(targets):
        if i:
            time.sleep(delay)
        repo = p["id"].removeprefix("github:")
        try:
            stars = fetch_stars(repo)
        except Exception as e:
            failed += 1
            print(f"警告: {repo} star 查询失败 — {e}", file=sys.stderr)
            if "403" in str(e):
                print("疑似触发 GitHub 限流，提前结束本轮（可设 GITHUB_TOKEN 提额）", file=sys.stderr)
                break
            continue
        ok += 1
        entries = tracking.setdefault(p["id"], [])
        record = {"date": today.isoformat(), "stars": stars}
        if entries and entries[-1]["date"] == record["date"]:
            entries[-1] = record
        else:
            entries.append(record)
    save_tracking(tracking, path)
    return {"targets": len(targets), "ok": ok, "failed": failed}


def compute_liftoff(history: list[dict], tracking: dict) -> list[dict]:
    """对比入库时 star 与最新快照，返回增幅榜（ratio 降序）。"""
    by_id = {p["id"]: p for p in history if p.get("id")}
    rows = []
    for pid, snapshots in tracking.items():
        p = by_id.get(pid)
        if not p or not snapshots:
            continue
        stars_then = (p.get("metrics") or {}).get("stars", 0)
        stars_now = snapshots[-1]["stars"]
        if stars_then <= 0:
            continue
        rows.append({
            "id": pid,
            "name": p["name"],
            "url": p["url"],
            "week": p.get("week", ""),
            "stars_then": stars_then,
            "stars_now": stars_now,
            "ratio": round(stars_now / stars_then, 1),
            "reason": p.get("reason", ""),
            "analysis": p.get("analysis") or {},
        })
    rows.sort(key=lambda r: (-r["ratio"], -r["stars_now"], r["id"]))
    return rows
