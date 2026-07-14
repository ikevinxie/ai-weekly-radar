import datetime

from collector.schema import make_project
from collector.scoring import build_prompt, merge_scored, top_ids, validate_scored


def cand(pid, name="Robot painter"):
    return make_project(
        id=f"github:{pid}", name=name, url=f"https://github.com/{pid}", source="github",
        description="paints with a robot arm using diffusion",
        collected_at=datetime.date(2026, 7, 17), metrics={"stars": 120},
    )


def entry(pid, whimsy=8, fun=7, money=5, reason="脑洞大且能落地", deep=True):
    e = {
        "id": f"github:{pid}", "reason": reason,
        "scores": {"whimsy": whimsy, "fun": fun, "money": money,
                   "total": whimsy + fun + money},
        "analysis": {"zh": "它用机械臂画画，思路大胆。", "en": "It paints with a robot arm; bold idea."},
    }
    if deep:
        e["deep_dive"] = {
            "zh": {"what": "机械臂绘画系统。", "why": "跨界结合罕见。", "biz": "艺术市场小众但溢价高。"},
            "en": {"what": "A robot-arm painting system.", "why": "Rare crossover.", "biz": "Niche art market."},
        }
    return e


def scored_doc(entries, week="2026-W29"):
    return {"week": week,
            "trend": {"zh": "本周智能体基建扎堆。", "en": "Agent infra everywhere this week."},
            "entries": entries}


class TestBuildPrompt:
    def test_contains_all_candidates_and_paths(self):
        prompt = build_prompt([cand("a"), cand("b")], "2026-W29", "data/scored/2026-W29.json")
        assert "github:a" in prompt and "github:b" in prompt
        assert "2 个候选" in prompt
        assert "data/scored/2026-W29.json" in prompt
        assert "validate 2026-W29" in prompt

    def test_mentions_v2_requirements(self):
        prompt = build_prompt([cand("a")], "2026-W29", "out.json")
        for token in ("trend", "analysis", "deep_dive", "Top 10", "zh", "en"):
            assert token in prompt, token

    def test_internal_links_excluded_from_metrics(self):
        c = cand("a")
        c["metrics"]["hn_link"] = "https://news.ycombinator.com/item?id=1"
        assert "news.ycombinator" not in build_prompt([c], "2026-W29", "out.json")


class TestTopIds:
    def test_orders_by_total_then_id(self):
        entries = [entry("a", 1, 1, 1), entry("b", 9, 9, 9), entry("c", 1, 1, 1)]
        assert top_ids(entries, count=2) == {"github:b", "github:a"}   # 并列时 a < c

    def test_fewer_entries_than_count(self):
        assert top_ids([entry("a")], count=10) == {"github:a"}


class TestValidateScored:
    def test_valid_v2(self):
        assert validate_scored([cand("a"), cand("b")], scored_doc([entry("a"), entry("b")])) == []

    def test_legacy_list_rejected_by_validate(self):
        errors = validate_scored([cand("a")], [entry("a")])
        assert errors == ["评分文件必须是对象 {week, trend, entries}（v2 格式，见 SPEC.md）"]

    def test_missing_week_and_trend_lang(self):
        doc = scored_doc([entry("a")])
        del doc["week"]
        doc["trend"] = {"zh": "只有中文"}
        errors = validate_scored([cand("a")], doc)
        assert any("week" in e for e in errors)
        assert any("trend.en" in e for e in errors)

    def test_missing_candidate_and_unknown_and_duplicate(self):
        doc = scored_doc([entry("a"), entry("a"), entry("ghost")])
        errors = validate_scored([cand("a"), cand("b")], doc)
        assert any("重复评分" in e for e in errors)
        assert any("不在候选列表" in e for e in errors)
        assert any("github:b: 缺少评分" in e for e in errors)

    def test_bad_score_and_missing_reason_still_checked(self):
        bad = entry("a")
        bad["scores"]["fun"] = 99
        bad["scores"]["total"] = 112
        bad["reason"] = ""
        errors = validate_scored([cand("a")], scored_doc([bad]))
        assert any("fun" in e for e in errors)
        assert any("reason" in e for e in errors)

    def test_analysis_missing_language(self):
        bad = entry("a")
        bad["analysis"] = {"zh": "只有中文"}
        errors = validate_scored([cand("a")], scored_doc([bad]))
        assert any("analysis.en" in e for e in errors)

    def test_top10_missing_deep_dive(self):
        errors = validate_scored([cand("a")], scored_doc([entry("a", deep=False)]))
        assert any("缺少 deep_dive" in e for e in errors)

    def test_non_top10_must_not_have_deep_dive(self):
        candidates = [cand(f"p{i:02d}") for i in range(11)]
        entries = [entry(f"p{i:02d}", whimsy=9) for i in range(10)]        # total 21 → Top 10
        entries.append(entry("p10", whimsy=0, fun=0, money=0, deep=True))  # 第 11 名却带 deep_dive
        errors = validate_scored(candidates, scored_doc(entries))
        assert any("不应有 deep_dive" in e for e in errors)

    def test_deep_dive_missing_section(self):
        bad = entry("a")
        del bad["deep_dive"]["en"]["biz"]
        bad["deep_dive"]["zh"]["what"] = "  "
        errors = validate_scored([cand("a")], scored_doc([bad]))
        assert any("deep_dive.en.biz" in e for e in errors)
        assert any("deep_dive.zh.what" in e for e in errors)


class TestMergeScored:
    def test_merges_v2_with_analysis_and_deep_dive(self):
        candidates = [cand("low"), cand("high")]
        doc = scored_doc([entry("low", 1, 1, 1, deep=False), entry("high", 9, 9, 9)])
        merged = merge_scored(candidates, doc)
        assert [p["id"] for p in merged] == ["github:high", "github:low"]
        assert merged[0]["deep_dive"]["en"]["what"]
        assert "deep_dive" not in merged[1]
        assert merged[1]["analysis"]["zh"]
        assert merged[0]["metrics"]["stars"] == 120   # 候选字段保留

    def test_merges_legacy_v1_list(self):
        legacy = [{"id": "github:a", "reason": "旧格式",
                   "scores": {"whimsy": 5, "fun": 5, "money": 5, "total": 15}}]
        merged = merge_scored([cand("a")], legacy)
        assert merged[0]["reason"] == "旧格式"
        assert "analysis" not in merged[0]

    def test_does_not_mutate_candidates(self):
        c = cand("a")
        merge_scored([c], scored_doc([entry("a")]))
        assert "scores" not in c
