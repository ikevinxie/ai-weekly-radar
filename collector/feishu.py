"""飞书群自定义机器人推送：每周 Top 10 交互式卡片。见 SPEC.md「飞书推送」。

webhook 读取顺序：环境变量 FEISHU_WEBHOOK_URL → ~/.config/ai-weekly-radar/feishu_webhook。
秘密绝不进入仓库。
"""
from __future__ import annotations

import json
import os
import pathlib

from .net import post_json
from .report import SITE_URL

WEBHOOK_FILE = pathlib.Path.home() / ".config" / "ai-weekly-radar" / "feishu_webhook"
MAX_CARD_BYTES = 30 * 1024

SETUP_HINT = f"""飞书 webhook 未配置，跳过推送。配置方法（约 5 分钟）：
1. 在飞书里建一个群（比如「AI 周报」）
2. 群设置 → 群机器人 → 添加机器人 → 自定义机器人，复制 webhook 地址
3. 把地址存入文件：mkdir -p ~/.config/ai-weekly-radar && echo '<webhook地址>' > {WEBHOOK_FILE}
   （或设置环境变量 FEISHU_WEBHOOK_URL）"""

_DIM_LABELS = (("whimsy", "天马行空"), ("fun", "有趣"), ("money", "有钱途"))


def webhook_url() -> str | None:
    url = os.environ.get("FEISHU_WEBHOOK_URL", "").strip()
    if url:
        return url
    if WEBHOOK_FILE.exists():
        url = WEBHOOK_FILE.read_text(encoding="utf-8").strip()
        if url:
            return url
    return None


def _item_md(rank: int, p: dict, medals: dict[str, str]) -> str:
    s = p["scores"]
    dims = " · ".join(f"{label} {s[key]}" for key, label in _DIM_LABELS)
    medal = f" {medals[p['id']]}" if p.get("id") in medals else ""
    lines = [f"**{rank}. [{p['name']}]({p['url']})**{medal}",
             f"{dims} · **总分 {s['total']}**",
             f"💡 {p.get('reason', '')}"]
    analysis_zh = (p.get("analysis") or {}).get("zh")
    if analysis_zh:
        lines.append(analysis_zh)
    return "\n".join(lines)


def build_card(week: str, trend_zh: str, top10: list[dict], awards: list[dict],
               site_url: str = SITE_URL) -> dict:
    medals = {}
    for a in awards:
        medals.setdefault(a["project_id"], "")
        medals[a["project_id"]] += a["emoji"]
    elements: list[dict] = []
    if trend_zh:
        elements.append({"tag": "div",
                         "text": {"tag": "lark_md", "content": f"🧭 **本周风向**\n{trend_zh}"}})
        elements.append({"tag": "hr"})
    for rank, p in enumerate(top10, 1):
        elements.append({"tag": "div",
                         "text": {"tag": "lark_md", "content": _item_md(rank, p, medals)}})
    if awards:
        awards_md = " ".join(f"{a['emoji']} {a['title']['zh']}" for a in awards)
        elements.append({"tag": "hr"})
        elements.append({"tag": "div",
                         "text": {"tag": "lark_md", "content": f"本周彩蛋奖：{awards_md}（见周报）"}})
    elements.append({"tag": "action", "actions": [{
        "tag": "button", "type": "primary",
        "text": {"tag": "plain_text", "content": "查看完整周报与双语深度解读"},
        "url": f"{site_url}/#{week}",
    }]})
    card = {
        "msg_type": "interactive",
        "card": {
            "config": {"wide_screen_mode": True},
            "header": {"template": "blue",
                       "title": {"tag": "plain_text",
                                 "content": f"AI 周报 {week} · 最值得看的 {len(top10)} 个项目"}},
            "elements": elements,
        },
    }
    size = len(json.dumps(card, ensure_ascii=False).encode("utf-8"))
    if size > MAX_CARD_BYTES:
        raise ValueError(f"飞书卡片 {size} 字节，超过 {MAX_CARD_BYTES} 上限，请缩短解读")
    return card


def send(card: dict, url: str) -> None:
    resp = post_json(url, card)
    # 自定义机器人成功返回 {"code": 0, ...}（旧版为 {"StatusCode": 0, ...}）
    if resp.get("code", resp.get("StatusCode")) != 0:
        raise RuntimeError(f"飞书推送失败: {resp}")
