"""每周彩蛋奖：纯规则实时计算，不入库。见 SPEC.md「彩蛋奖」。"""
from __future__ import annotations

AWARD_DEFS = (
    {"key": "best", "emoji": "🏆", "title": {"zh": "本周最佳", "en": "Best of the Week"}},
    {"key": "wildest", "emoji": "🤪", "title": {"zh": "最离谱奖", "en": "Wildest Idea"}},
    {"key": "quiet_money", "emoji": "💰", "title": {"zh": "闷声发财奖", "en": "Quiet Money Maker"}},
    {"key": "dark_horse", "emoji": "🐴", "title": {"zh": "黑马奖", "en": "Dark Horse"}},
    {"key": "hardcore", "emoji": "🔬", "title": {"zh": "硬核奖", "en": "Hardcore Research"}},
    {"key": "funnest", "emoji": "🎪", "title": {"zh": "最好玩奖", "en": "Most Fun"}},
    {"key": "polarized", "emoji": "⚖️", "title": {"zh": "两极分化奖", "en": "Most Polarizing"}},
)

_HEAT_KEYS = ("stars", "points", "upvotes", "likes")


def _heat(p: dict):
    metrics = p.get("metrics") or {}
    for key in _HEAT_KEYS:
        if isinstance(metrics.get(key), int):
            return metrics[key]
    return None


def _is_paper(p: dict) -> bool:
    if p.get("source") == "arxiv":
        return True
    return p.get("source") == "huggingface" and (p.get("metrics") or {}).get("kind") == "paper"


def _pool_and_metric(key: str, scored: list[dict]):
    """返回 (候选池, 指标函数)；奖项空缺时候选池为空。"""
    if key == "best":
        return scored, lambda p: p["scores"]["total"]
    if key == "wildest":
        return scored, lambda p: p["scores"]["whimsy"] - p["scores"]["money"]
    if key == "quiet_money":
        return scored, lambda p: p["scores"]["money"] - p["scores"]["whimsy"]
    if key == "funnest":
        return scored, lambda p: p["scores"]["fun"]
    if key == "polarized":
        return scored, lambda p: (max(p["scores"][k] for k in ("whimsy", "fun", "money"))
                                  - min(p["scores"][k] for k in ("whimsy", "fun", "money")))
    if key == "hardcore":
        return [p for p in scored if _is_paper(p)], lambda p: p["scores"]["total"]
    if key == "dark_horse":
        # 有数值热度且 total 进入当周前 1/3 的项目中，热度最低者
        by_total = sorted(scored, key=lambda p: (-p["scores"]["total"], p["id"]))
        top_third = by_total[:max(1, len(by_total) // 3)]
        pool = [p for p in top_third if _heat(p) is not None]
        return pool, lambda p: -_heat(p)
    raise KeyError(key)


def compute_awards(projects: list[dict]) -> list[dict]:
    """输入同一周的已评分项目，返回 [{key, emoji, title, project_id}]。

    并列时依次按（指标降序 → total 降序 → id 字典序升序）断绝；同一项目可兼得多奖；
    候选池为空的奖项空缺（不出现在结果里）。
    """
    scored = [p for p in projects
              if isinstance(p.get("scores"), dict) and isinstance(p.get("id"), str)]
    awards = []
    for definition in AWARD_DEFS:
        pool, metric = _pool_and_metric(definition["key"], scored)
        if not pool:
            continue
        winner = min(pool, key=lambda p: (-metric(p), -p["scores"]["total"], p["id"]))
        awards.append({**definition, "project_id": winner["id"]})
    return awards
