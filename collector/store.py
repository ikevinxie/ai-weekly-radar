"""data/projects.json 累积库：读写、去重合并、按周查询。"""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
PROJECTS_PATH = ROOT / "data" / "projects.json"
CANDIDATES_DIR = ROOT / "data" / "candidates"
SCORED_DIR = ROOT / "data" / "scored"


def load(path: pathlib.Path = PROJECTS_PATH) -> list[dict]:
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save(projects: list[dict], path: pathlib.Path = PROJECTS_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(projects, ensure_ascii=False, indent=1), encoding="utf-8")


def known_ids(projects: list[dict]) -> set[str]:
    return {p["id"] for p in projects if p.get("id")}


def merge(existing: list[dict], incoming: list[dict]) -> list[dict]:
    """按 id 去重合并；已存在的条目保留原值，不覆盖。"""
    ids = known_ids(existing)
    merged = list(existing)
    for p in incoming:
        if p.get("id") and p["id"] not in ids:
            ids.add(p["id"])
            merged.append(p)
    return merged


def by_week(projects: list[dict], week: str) -> list[dict]:
    return [p for p in projects if p.get("week") == week]


def weeks(projects: list[dict]) -> list[str]:
    return sorted({p["week"] for p in projects if p.get("week")}, reverse=True)
