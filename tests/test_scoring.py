import datetime

from collector.schema import make_project
from collector.scoring import (MAX_TAGS, TAGS, build_prompt, merge_scored, top_ids,
                               validate_scored)


def cand(pid, name="Robot painter"):
    return make_project(
        id=f"github:{pid}", name=name, url=f"https://github.com/{pid}", source="github",
        description="paints with a robot arm using diffusion",
        collected_at=datetime.date(2026, 7, 17), metrics={"stars": 120},
    )


def entry(pid, whimsy=8, fun=7, money=5, reason="脑洞大且能落地", tags=("创意",)):
    return {
        "id": f"github:{pid}", "reason": reason,
        "scores": {"whimsy": whimsy, "fun": fun, "money": money,
                   "total": whimsy + fun + money},
        "analysis": {"zh": "它用机械臂画画，思路大胆。", "en": "It paints with a robot arm; bold idea."},
        "deep_dive": {
            "zh": {"what": "机械臂绘画系统。", "why": "跨界结合罕见。", "biz": "艺术市场小众但溢价高。"},
            "en": {"what": "A robot-arm painting system.", "why": "Rare crossover.", "biz": "Niche art market."},
        },
        "tags": list(tags),
    }


def scored_doc(entries, week="2026-W29"):
    return {"week": week,
            "trend": {"zh": "本周智能体基建扎堆。", "en": "Agent infra everywhere this week.",
                      "deep": {"zh": "深度：基建、反噬经济、视频白嫖三条线。",
                               "en": "Deep: infra, backlash economy, free video."}},
            "entries": entries}


class TestBuildPrompt:
    def test_contains_all_candidates_and_paths(self):
        prompt = build_prompt([cand("a"), cand("b")], "2026-W29", "data/scored/2026-W29.json")
        assert "github:a" in prompt and "github:b" in prompt
        assert "2 个候选" in prompt
        assert "data/scored/2026-W29.json" in prompt
        assert "validate 2026-W29" in prompt

    def test_mentions_v3_requirements(self):
        prompt = build_prompt([cand("a")], "2026-W29", "out.json")
        for token in ("trend", "analysis", "deep_dive", "tags", "deep.zh", "zh", "en"):
            assert token in prompt, token
        for tag in TAGS:
            assert tag in prompt

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
    def test_valid_v3(self):
        assert validate_scored([cand("a"), cand("b")], scored_doc([entry("a"), entry("b")])) == []

    def test_legacy_list_rejected_by_validate(self):
        errors = validate_scored([cand("a")], [entry("a")])
        assert len(errors) == 1 and "必须是对象" in errors[0]

    def test_missing_week_and_trend_lang(self):
        doc = scored_doc([entry("a")])
        del doc["week"]
        doc["trend"] = {"zh": "只有中文", "deep": {"zh": "深", "en": "deep"}}
        errors = validate_scored([cand("a")], doc)
        assert any("week" in e for e in errors)
        assert any("trend.en" in e for e in errors)

    def test_trend_deep_required(self):
        doc = scored_doc([entry("a")])
        del doc["trend"]["deep"]
        assert any("trend.deep" in e for e in validate_scored([cand("a")], doc))
        doc["trend"]["deep"] = {"zh": "只有中文"}
        assert any("trend.deep.en" in e for e in validate_scored([cand("a")], doc))

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

    def test_every_entry_requires_deep_dive(self):
        bad = entry("a")
        del bad["deep_dive"]
        errors = validate_scored([cand("a")], scored_doc([bad]))
        assert any("deep_dive" in e for e in errors)

    def test_deep_dive_missing_section(self):
        bad = entry("a")
        del bad["deep_dive"]["en"]["biz"]
        bad["deep_dive"]["zh"]["what"] = "  "
        errors = validate_scored([cand("a")], scored_doc([bad]))
        assert any("deep_dive.en.biz" in e for e in errors)
        assert any("deep_dive.zh.what" in e for e in errors)

    def test_tags_required_and_bounded(self):
        for bad_tags in (None, [], ["创意"] * (MAX_TAGS + 1), "创意"):
            bad = entry("a")
            bad["tags"] = bad_tags
            if bad_tags is None:
                del bad["tags"]
            errors = validate_scored([cand("a")], scored_doc([bad]))
            assert any("tags" in e for e in errors), bad_tags

    def test_tags_must_be_in_vocabulary(self):
        bad = entry("a", tags=("创意", "区块链"))
        errors = validate_scored([cand("a")], scored_doc([bad]))
        assert any("区块链" in e and "词表" in e for e in errors)

    def test_duplicate_tags_rejected(self):
        bad = entry("a", tags=("创意", "创意"))
        assert any("重复" in e for e in validate_scored([cand("a")], scored_doc([bad])))


class TestMergeScored:
    def test_merges_v3_fields(self):
        candidates = [cand("low"), cand("high")]
        doc = scored_doc([entry("low", 1, 1, 1), entry("high", 9, 9, 9, tags=("agent", "安全"))])
        merged = merge_scored(candidates, doc)
        assert [p["id"] for p in merged] == ["github:high", "github:low"]
        assert merged[0]["deep_dive"]["en"]["what"]
        assert merged[0]["tags"] == ["agent", "安全"]
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
