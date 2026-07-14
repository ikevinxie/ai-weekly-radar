import datetime
import json
import re
import xml.etree.ElementTree as ET

import pytest

from collector.report import build_feed, generate
from collector.schema import make_project

TREND = {"zh": "本周智能体基建扎堆出现。信号明显。", "en": "Agent infra clustered this week.",
         "deep": {"zh": "深度：三条主线展开讲。", "en": "Deep: three storylines."}}


def scored_proj(pid, name="AI Pet Rock", week_date=datetime.date(2026, 7, 17),
                total_parts=(9, 8, 2), deep=False, **extra):
    p = make_project(
        id=f"github:{pid}", name=name, url=f"https://github.com/{pid}", source="github",
        description="a rock that judges you", collected_at=week_date, metrics={"stars": 99},
    )
    w, f, m = total_parts
    p["scores"] = {"whimsy": w, "fun": f, "money": m, "total": w + f + m}
    p["reason"] = "毫无用处但让人想要"
    p["analysis"] = {"zh": "中文简读两句。", "en": "English brief."}
    p["tags"] = ["创意"]
    if deep:
        p["deep_dive"] = {"zh": {"what": "是石头。", "why": "很怪。", "biz": "没钱途。"},
                          "en": {"what": "A rock.", "why": "Weird.", "biz": "No market."}}
    p.update(extra)
    return p


@pytest.fixture
def site(tmp_path):
    history = [
        scored_proj("a", deep=True),
        scored_proj("b", total_parts=(1, 1, 1)),
        scored_proj("old", week_date=datetime.date(2026, 7, 10)),   # W28
    ]
    liftoff = [{"id": "github:a", "name": "a", "url": "https://github.com/a",
                "week": "2026-W29", "stars_then": 99, "stars_now": 500, "ratio": 5.1,
                "reason": "毫无用处但让人想要", "analysis": {"zh": "简读", "en": "brief"}}]
    generate(history, trends={"2026-W29": TREND}, liftoff=liftoff, out_dir=tmp_path)
    return tmp_path


class TestGenerate:
    def test_writes_all_site_files(self, site):
        for name in ("index.html", "feed.xml", "data/weeks.json",
                     "data/2026-W29.json", "data/2026-W28.json"):
            assert (site / name).exists(), name

    def test_weeks_index_has_trend_awards_liftoff(self, site):
        meta = json.loads((site / "data" / "weeks.json").read_text(encoding="utf-8"))
        weeks = {w["week"]: w for w in meta["weeks"]}
        assert list(weeks) == ["2026-W29", "2026-W28"]   # 倒序
        assert weeks["2026-W29"]["trend"] == TREND
        assert weeks["2026-W28"]["trend"] is None        # 无风向的历史周
        award_keys = {a["key"] for a in weeks["2026-W29"]["awards"]}
        assert {"best", "wildest", "quiet_money", "funnest"} <= award_keys
        assert meta["liftoff"][0]["ratio"] == 5.1
        assert meta["liftoff"][0]["reason"]              # 起飞榜带介绍

    def test_weeks_index_has_date_top3_and_awards_names(self, site):
        meta = json.loads((site / "data" / "weeks.json").read_text(encoding="utf-8"))
        w29 = next(w for w in meta["weeks"] if w["week"] == "2026-W29")
        assert w29["date"] == "2026-07-17"               # 该 ISO 周的周五
        assert [p["id"] for p in w29["top3"]] == ["github:a", "github:b"]
        assert w29["top3"][0]["name"] == "AI Pet Rock"
        assert all(a["project_name"] for a in w29["awards"])

    def test_qr_matrices_embedded(self, site):
        meta = json.loads((site / "data" / "weeks.json").read_text(encoding="utf-8"))
        for rows in [meta["qr_site"]] + [w["qr"] for w in meta["weeks"]]:
            assert len(rows) >= 21                        # 至少 v1 尺寸
            assert all(len(r) == len(rows) and set(r) <= {"0", "1"} for r in rows)

    def test_week_data_sorted_ranked_and_contains_analysis(self, site):
        data = json.loads((site / "data" / "2026-W29.json").read_text(encoding="utf-8"))
        assert [p["id"] for p in data] == ["github:a", "github:b"]
        assert [p["rank"] for p in data] == [1, 2]
        assert data[0]["deep_dive"]["en"]["what"] == "A rock."
        assert data[1]["analysis"]["zh"]
        assert data[0]["tags"] == ["创意"]

    def test_index_self_contained_and_fetch_based(self, site):
        html = (site / "index.html").read_text(encoding="utf-8")
        assert "fetch(" in html
        assert not re.search(r"<script[^>]+src=", html)
        assert not re.search(r'<link(?![^>]*feed\.xml)[^>]*href=', html)   # 仅允许 RSS link
        assert "@import" not in html

    def test_score_bar_fill_is_block_level(self, site):
        # 回归：.fill 必须 display:block 否则 width 百分比不渲染（浏览器实测发现）
        html = (site / "index.html").read_text(encoding="utf-8")
        fill_rule = re.search(r"\.fill\s*\{([^}]*)\}", html).group(1)
        assert "display: block" in fill_rule

    def test_unscored_projects_excluded(self, tmp_path):
        candidate = scored_proj("cand")
        del candidate["scores"]
        generate([scored_proj("done"), candidate], out_dir=tmp_path)
        data = json.loads((tmp_path / "data" / "2026-W29.json").read_text(encoding="utf-8"))
        assert [p["id"] for p in data] == ["github:done"]

    def test_empty_history_still_generates(self, tmp_path):
        generate([], out_dir=tmp_path)
        meta = json.loads((tmp_path / "data" / "weeks.json").read_text(encoding="utf-8"))
        assert meta["weeks"] == [] and meta["liftoff"] == []
        assert len(meta["qr_site"]) >= 21           # 站点二维码始终生成
        assert (tmp_path / "index.html").exists()


class TestFeed:
    def test_valid_rss_with_item_per_week(self, site):
        root = ET.fromstring((site / "feed.xml").read_text(encoding="utf-8"))
        assert root.tag == "rss"
        items = root.findall("./channel/item")
        assert len(items) == 2
        first = items[0]
        assert "2026-W29" in first.findtext("title")
        assert "本周智能体基建扎堆出现。" in first.findtext("title")   # 风向首句进标题
        desc = first.findtext("description")
        assert "AI Pet Rock" in desc and "毫无用处但让人想要" in desc
        assert first.findtext("link").endswith("#2026-W29")

    def test_feed_escapes_xml_specials(self):
        p = scored_proj("x", name="Tom & <Jerry>")
        xml_text = build_feed(
            [{"week": "2026-W29", "trend": None, "awards": [], "count": 1}],
            {"2026-W29": [p]})
        ET.fromstring(xml_text)   # 不抛错即通过
        assert "Tom &amp; &lt;Jerry&gt;" in xml_text
