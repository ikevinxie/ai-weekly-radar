"""飞书推送周级幂等标记：data/feishu_sent/<week>.txt 存在即视为本周已推。

为什么需要：workflow 的 feishu step 没有去重，手动 Run workflow 连点 / cron 与
手动同时触发都会让飞书群收到重复卡片。标记文件随仓库 commit & push，云端各 run
共享同一份事实。

本地手动重发：用 `python3 -m collector feishu <week> --force` 跳过检查。
"""
from __future__ import annotations

import datetime
import pathlib

from .store import ROOT

SENT_DIR = ROOT / "data" / "feishu_sent"


def _path(week: str) -> pathlib.Path:
    return SENT_DIR / f"{week}.txt"


def was_sent(week: str) -> bool:
    return _path(week).exists()


def mark_sent(week: str) -> pathlib.Path:
    SENT_DIR.mkdir(parents=True, exist_ok=True)
    p = _path(week)
    p.write_text(datetime.datetime.now(datetime.timezone.utc)
                 .isoformat(timespec="seconds").replace("+00:00", "Z") + "\n",
                 encoding="utf-8")
    return p
