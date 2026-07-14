"""每周彩蛋奖：纯规则实时计算，不入库。见 SPEC.md「彩蛋奖」。"""
from __future__ import annotations

AWARD_DEFS = (
    {"key": "best", "emoji": "🏆", "title": {"zh": "本周最佳", "en": "Best of the Week"}},
    {"key": "wildest", "emoji": "🤪", "title": {"zh": "最离谱奖", "en": "Wildest Idea"}},
    {"key": "quiet_money", "emoji": "💰", "title": {"zh": "闷声发财奖", "en": "Quiet Money Maker"}},
)

_METRIC = {
    "best": lambda s: s["total"],
    "wildest": lambda s: s["whimsy"] - s["money"],
    "quiet_money": lambda s: s["money"] - s["whimsy"],
}


def compute_awards(projects: list[dict]) -> list[dict]:
    """输入同一周的已评分项目，返回 [{key, emoji, title, project_id}]。

    并列时依次按 total 降序、id 字典序升序断绝；同一项目可兼得多个奖；
    无已评分项目时返回空列表。
    """
    scored = [p for p in projects
              if isinstance(p.get("scores"), dict) and isinstance(p.get("id"), str)]
    if not scored:
        return []
    awards = []
    for definition in AWARD_DEFS:
        metric = _METRIC[definition["key"]]
        winner = min(scored, key=lambda p: (-metric(p["scores"]), -p["scores"]["total"], p["id"]))
        awards.append({**definition, "project_id": winner["id"]})
    return awards
