"""飞书推送日级幂等标记：data/feishu_sent/<YYYY-MM-DD>.txt 存在即视为当日已推。

为什么是日级而不是周级：发布节奏是每周五，但 ISO 周从周一开始算，
周一和周五在同一个 ISO 周里。如果标记是周级，周一的手动 run 会把
周五的自动 cron run 挡掉，飞书卡片发不出去。日级标记让"同一天
重复 run 不重发"（防手抖连点 / cron 与手动同时触发），但"不同天
即使同周也能各自发"，匹配真实的发布节奏。

本地手动重发：用 `python3 -m collector feishu <week> --force` 跳过检查。
"""
from __future__ import annotations

import datetime
import pathlib

from .store import ROOT

SENT_DIR = ROOT / "data" / "feishu_sent"


def _path(date_key: str) -> pathlib.Path:
    return SENT_DIR / f"{date_key}.txt"


def was_sent(date_key: str) -> bool:
    return _path(date_key).exists()


def mark_sent(date_key: str) -> pathlib.Path:
    SENT_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(date_key)
    p.write_text(datetime.datetime.now(datetime.timezone.utc)
                 .isoformat(timespec="seconds").replace("+00:00", "Z") + "\n",
                 encoding="utf-8")
    return p
