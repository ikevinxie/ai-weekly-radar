import datetime
import json

import pytest

from collector import voices


def post(url="https://x.com/a/status/1", **over):
    p = {"author": "Swyx", "handle": "swyx", "text": "AI is eating software",
         "url": url, "date": "2026-07-14", "likes": 10}
    p.update(over)
    return p


def weekly_doc(**over):
    doc = {
        "week": "2026-W29",
        "overview": {"zh": "本周大家都在聊 agent。", "en": "Everyone talked agents."},
        "themes": [{
            "title": {"zh": "智能体基建", "en": "Agent infra"},
            "summary": {"zh": "基建成为共识。", "en": "Infra is consensus."},
            "quotes": [post()],
        }],
    }
    doc.update(over)
    return doc


class TestParseFeed:
    def test_parses_fixture(self, load_json):
        posts = voices.parse_feed(load_json("voices_feed.json"))
        assert len(posts) >= 20
        for p in posts:
            assert p["author"] and p["text"]
            assert p["url"].startswith("https://x.com/")
            assert len(p["date"]) == 10

    def test_empty_and_malformed(self):
        assert voices.parse_feed({}) == []
        assert voices.parse_feed({"x": [{"name": "A", "tweets": [
            {"text": "", "url": "https://x"},          # 空文本
            {"text": "hi"},                             # 缺 url
        ]}]}) == []

    def test_author_falls_back_to_handle(self):
        posts = voices.parse_feed({"x": [{"handle": "swyx", "tweets": [
            {"text": "hello", "url": "https://x.com/1", "createdAt": "2026-07-14T00:00:00Z"}]}]})
        assert posts[0]["author"] == "swyx"


class TestDailyAndWeekAggregation:
    def test_collect_daily_writes_snapshot(self, tmp_path, monkeypatch, load_json):
        monkeypatch.setattr(voices, "fetch_json", lambda url: load_json("voices_feed.json"))
        path = voices.collect_daily(datetime.date(2026, 7, 14), path_dir=tmp_path)
        assert path.name == "2026-07-14.json"
        assert len(json.loads(path.read_text())) >= 20

    def test_week_aggregation_dedupes_and_filters_by_week(self, tmp_path):
        # W29: 7-13(一) ~ 7-19(日)；feed 是 24h 滚动窗口，跨日重叠要按 url 去重
        (tmp_path / "2026-07-13.json").write_text(json.dumps(
            [post("https://x.com/a/1"), post("https://x.com/a/2")]), encoding="utf-8")
        (tmp_path / "2026-07-14.json").write_text(json.dumps(
            [post("https://x.com/a/2"), post("https://x.com/a/3")]), encoding="utf-8")
        (tmp_path / "2026-07-12.json").write_text(json.dumps(
            [post("https://x.com/old/9")]), encoding="utf-8")     # W28，应排除
        (tmp_path / "notes.json").write_text("[]", encoding="utf-8")   # 非日期文件忽略
        posts = voices.load_week_posts("2026-W29", path_dir=tmp_path)
        assert [p["url"] for p in posts] == ["https://x.com/a/1", "https://x.com/a/2", "https://x.com/a/3"]

    def test_missing_dir_returns_empty(self, tmp_path):
        assert voices.load_week_posts("2026-W29", path_dir=tmp_path / "nope") == []


class TestBuildPrompt:
    def test_prompt_contains_posts_and_structure(self):
        posts = [post(), post("https://x.com/b/2", author="Karpathy", handle="karpathy")]
        prompt = voices.build_prompt(posts, "2026-W29")
        assert "2 条发言" in prompt
        assert "@swyx" in prompt and "@karpathy" in prompt
        assert "https://x.com/b/2" in prompt
        assert "overview" in prompt and "themes" in prompt and "渐进式" in prompt
        assert str(voices.weekly_path("2026-W29")) in prompt


class TestValidateWeekly:
    def test_valid(self):
        assert voices.validate_weekly(weekly_doc()) == []

    def test_not_dict(self):
        assert voices.validate_weekly([1]) == ["voices 周汇总必须是对象"]

    def test_missing_overview_lang_and_empty_themes(self):
        doc = weekly_doc(overview={"zh": "只有中文"}, themes=[])
        errors = voices.validate_weekly(doc)
        assert any("overview.en" in e for e in errors)
        assert any("themes" in e for e in errors)

    def test_theme_missing_fields_and_bad_quote(self):
        theme = {"title": {"zh": "x"}, "summary": {"zh": "y", "en": "y"},
                 "quotes": [{"text": "no url"}]}
        errors = voices.validate_weekly(weekly_doc(themes=[theme]))
        assert any("title.en" in e for e in errors)
        assert any("quotes[0]" in e for e in errors)

    def test_load_weekly_missing_returns_none(self, tmp_path, monkeypatch):
        monkeypatch.setattr(voices, "WEEKLY_DIR", tmp_path)
        assert voices.load_weekly("2026-W29") is None

    def test_load_weekly_invalid_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(voices, "WEEKLY_DIR", tmp_path)
        (tmp_path / "2026-W29.json").write_text(json.dumps({"week": "2026-W29"}), encoding="utf-8")
        with pytest.raises(ValueError):
            voices.load_weekly("2026-W29")
