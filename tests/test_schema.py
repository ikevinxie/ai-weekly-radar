import datetime

import pytest

from collector.schema import make_project, validate_project, week_of


def sample(**overrides):
    p = make_project(
        id="github:foo/bar", name="bar", url="https://github.com/foo/bar",
        source="github", description="An AI toy", collected_at=datetime.date(2026, 7, 17),
        metrics={"stars": 100},
    )
    p.update(overrides)
    return p


def scored(**overrides):
    p = sample(scores={"whimsy": 8, "fun": 7, "money": 5, "total": 20}, reason="脑洞很大")
    p.update(overrides)
    return p


class TestWeekOf:
    def test_iso_week(self):
        assert week_of(datetime.date(2026, 7, 17)) == "2026-W29"

    def test_year_boundary(self):
        # 2027-01-01 是周五，属于 2026 年第 53 周
        assert week_of(datetime.date(2027, 1, 1)) == "2026-W53"

    def test_zero_padding(self):
        assert week_of(datetime.date(2026, 1, 7)) == "2026-W02"


class TestMakeProject:
    def test_fills_week_and_date(self):
        p = sample()
        assert p["collected_at"] == "2026-07-17"
        assert p["week"] == "2026-W29"

    def test_strips_description(self):
        p = make_project(
            id="github:a/b", name="b", url="https://x.com", source="github",
            description="  hi \n", collected_at=datetime.date(2026, 7, 17), metrics={},
        )
        assert p["description"] == "hi"


class TestValidateProject:
    def test_valid_candidate(self):
        assert validate_project(sample()) == []

    def test_valid_scored(self):
        assert validate_project(scored(), require_scores=True) == []

    def test_missing_field(self):
        p = sample()
        del p["url"]
        assert any("url" in e for e in validate_project(p))

    def test_unknown_source(self):
        errors = validate_project(sample(source="twitter", id="twitter:x"))
        assert any("未知来源" in e for e in errors)

    def test_id_source_prefix_mismatch(self):
        errors = validate_project(sample(id="hn:123"))
        assert any("开头" in e for e in errors)

    def test_bad_url(self):
        errors = validate_project(sample(url="ftp://x"))
        assert any("http" in e for e in errors)

    def test_not_a_dict(self):
        assert validate_project("nope") == ["project 必须是对象"]


class TestValidateScores:
    def test_candidate_without_scores_fails_when_required(self):
        errors = validate_project(sample(), require_scores=True)
        assert any("scores" in e for e in errors)

    @pytest.mark.parametrize("bad", [-1, 11, 7.5, "8", None, True])
    def test_score_out_of_range_or_wrong_type(self, bad):
        p = scored(scores={"whimsy": bad, "fun": 7, "money": 5, "total": 20})
        errors = validate_project(p, require_scores=True)
        assert any("whimsy" in e for e in errors)

    def test_total_must_match_sum(self):
        p = scored(scores={"whimsy": 8, "fun": 7, "money": 5, "total": 99})
        errors = validate_project(p, require_scores=True)
        assert any("total" in e for e in errors)

    def test_missing_reason(self):
        errors = validate_project(scored(reason="  "), require_scores=True)
        assert any("reason" in e for e in errors)
