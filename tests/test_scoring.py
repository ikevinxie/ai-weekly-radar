import datetime

from collector.schema import make_project
from collector.scoring import (MAX_TAGS, TAGS, build_prompt, merge_scored, sanitize_scored,
                               top_ids, validate_scored)


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

    def test_tags_only_structural_check_in_validator(self):
        # 词表合规 / 数量 / 去重 全部由 sanitize_scored 软处理；validate 只查
        # 「tags 字段若存在必须是 list」这一条结构性约束，避免下游崩。
        # 这些情况 validate 都不应报错（sanitize 会处理）：
        for soft_bad in (None, [], ["创意"] * (MAX_TAGS + 1), ["区块链"], ["创意", "创意"]):
            bad = entry("a")
            if soft_bad is None:
                del bad["tags"]
            else:
                bad["tags"] = soft_bad
            errors = validate_scored([cand("a")], scored_doc([bad]))
            assert not any("tags" in e for e in errors), (soft_bad, errors)
        # 唯一硬错：tags 字段存在但不是 list
        bad = entry("a")
        bad["tags"] = "创意"
        errors = validate_scored([cand("a")], scored_doc([bad]))
        assert any("tags 必须是数组" in e for e in errors)


class TestSanitizeScored:
    def test_drops_unknown_tags_keeps_valid(self):
        e = entry("a", tags=("创意", "开源", "区块链"))
        doc = scored_doc([e])
        out, warns = sanitize_scored(doc)
        assert out["entries"][0]["tags"] == ["创意", "开源"]
        assert any("区块链" in w for w in warns)

    def test_drops_entry_when_all_tags_unknown(self):
        e = entry("a", tags=("区块链", "元宇宙"))
        doc = scored_doc([e, entry("b")])
        out, warns = sanitize_scored(doc)
        assert [x["id"] for x in out["entries"]] == ["github:b"]
        assert any("整条丢弃" in w for w in warns)

    def test_drops_entry_when_tags_not_list(self):
        e = entry("a")
        e["tags"] = "创意"
        doc = scored_doc([e])
        out, warns = sanitize_scored(doc)
        assert out["entries"] == []
        assert any("不是数组" in w for w in warns)

    def test_drops_entry_when_tags_empty_list(self):
        e = entry("a")
        e["tags"] = []
        doc = scored_doc([e])
        out, warns = sanitize_scored(doc)
        assert out["entries"] == []
        assert any("整条丢弃" in w for w in warns)

    def test_dedups_and_truncates(self):
        e = entry("a", tags=("创意", "创意", "agent", "视频", "数据"))
        doc = scored_doc([e])
        out, warns = sanitize_scored(doc)
        assert out["entries"][0]["tags"] == ["创意", "agent", "视频"]
        assert any("重复" in w for w in warns)

    def test_clean_doc_unchanged_no_warnings(self):
        doc = scored_doc([entry("a", tags=("创意", "开源")), entry("b", tags=("agent",))])
        out, warns = sanitize_scored(doc)
        assert warns == []
        assert [e["tags"] for e in out["entries"]] == [["创意", "开源"], ["agent"]]

    def test_non_dict_scored_passes_through(self):
        out, warns = sanitize_scored([entry("a")])
        assert warns == []
        assert isinstance(out, list)

    def test_kaizen_yuan_in_vocab(self):
        # 回归锁死：开源 必须在词表内，否则 sanitize 会把它当未知 tag 丢掉
        assert "开源" in TAGS

    def test_arbitrary_tag_drift_never_fails_pipeline(self):
        # 根因回归：LLM 是概率模型，tag 漂移是必然事件。无论它写什么词，
        # sanitize + validate 组合都不应让 cmd_score 返回 1。
        # 模拟 LLM 写了一堆词表外的 tag（科研 / 多模态 / RAG / LLM / 区块链 / 元宇宙）
        drift_entries = [
            entry("a", tags=("科研", "多模态")),         # 全未知 → sanitize 丢整条
            entry("b", tags=("RAG", "agent")),           # 部分未知 → sanitize 留 agent
            entry("c", tags=("LLM", "区块链", "元宇宙")), # 全未知 → sanitize 丢整条
            entry("d", tags=("创意",)),                  # 合规 → 原样保留
        ]
        doc = scored_doc(drift_entries)
        sanitized, warns = sanitize_scored(doc)
        assert warns, "漂移场景必须产生 warning 供运维观察"
        # cmd_score 在 sanitize 后会把 candidates 过滤到 surviving ids 再 validate，
        # 这样被 sanitize 丢掉的 entry 不会被当成「缺少评分」硬错。
        all_cands = [cand("a"), cand("b"), cand("c"), cand("d")]
        surviving = {e["id"] for e in sanitized["entries"]}
        scored_cands = [c for c in all_cands if c["id"] in surviving]
        errors = validate_scored(scored_cands, sanitized)
        assert errors == [], f"sanitize 后 validate 不应再报错: {errors}"
        # 留下的 entry 是 b 和 d
        assert [e["id"] for e in sanitized["entries"]] == ["github:b", "github:d"]
        assert sanitized["entries"][0]["tags"] == ["agent"]


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
