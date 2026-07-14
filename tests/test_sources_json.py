"""JSON 类数据源（GitHub / Hacker News / Hugging Face）的解析测试。"""
from collector.schema import validate_project
from collector.sources import github, hackernews, huggingface


class TestGithub:
    def test_parses_fixture(self, load_json, today):
        projects = github.parse(load_json("github_search.json"), today)
        assert len(projects) >= 5
        for p in projects:
            assert validate_project(p) == [], validate_project(p)
            assert p["id"].startswith("github:")
            assert isinstance(p["metrics"]["stars"], int)

    def test_empty_response(self, today):
        assert github.parse({"items": []}, today) == []
        assert github.parse({}, today) == []

    def test_skips_malformed_items(self, today):
        payload = {"items": [
            {"full_name": None, "html_url": "https://x"},
            {"description": "no name at all"},
            {"full_name": "a/b", "html_url": "https://github.com/a/b", "stargazers_count": 7},
        ]}
        projects = github.parse(payload, today)
        assert [p["id"] for p in projects] == ["github:a/b"]

    def test_two_query_urls_with_time_window(self, today):
        urls = github.urls(today)
        assert len(urls) == 2
        assert all("2026-07-06" in u for u in urls)


class TestHackerNews:
    def test_parses_fixture(self, load_json, today):
        projects = hackernews.parse(load_json("hackernews_search.json"), today)
        assert len(projects) >= 10
        for p in projects:
            assert validate_project(p) == [], validate_project(p)
            assert p["metrics"]["hn_link"].startswith("https://news.ycombinator.com/")

    def test_show_hn_prefix_stripped_from_name(self, today):
        payload = {"hits": [{"objectID": "1", "title": "Show HN: My robot", "points": 80, "url": None}]}
        p = hackernews.parse(payload, today)[0]
        assert p["name"] == "My robot"
        assert p["description"] == "Show HN: My robot"

    def test_missing_url_falls_back_to_hn_link(self, today):
        payload = {"hits": [{"objectID": "42", "title": "T", "points": 60}]}
        assert hackernews.parse(payload, today)[0]["url"] == "https://news.ycombinator.com/item?id=42"

    def test_empty_and_malformed(self, today):
        assert hackernews.parse({}, today) == []
        assert hackernews.parse({"hits": [{"title": "no id"}, {"objectID": "9"}]}, today) == []


class TestHuggingFace:
    def test_parses_spaces_fixture(self, load_json, today):
        projects = huggingface.parse_spaces(load_json("huggingface_spaces.json"), today)
        assert len(projects) == 25
        for p in projects:
            assert validate_project(p) == [], validate_project(p)
            assert p["id"].startswith("huggingface:space/")
            assert p["metrics"]["kind"] == "space"

    def test_parses_papers_fixture(self, load_json, today):
        projects = huggingface.parse_papers(load_json("huggingface_papers.json"), today)
        assert len(projects) == 25
        for p in projects:
            assert validate_project(p) == [], validate_project(p)
            assert p["url"].startswith("https://huggingface.co/papers/")

    def test_empty_and_malformed(self, today):
        assert huggingface.parse_spaces([], today) == []
        assert huggingface.parse_spaces([{"likes": 3}], today) == []
        assert huggingface.parse_papers([{}, {"paper": {"title": "no id"}}], today) == []
