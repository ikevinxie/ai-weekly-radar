"""Feed 类数据源（Product Hunt / arXiv / Reddit）的解析测试。"""
import datetime

import pytest

from collector.schema import validate_project
from collector.sources import arxiv, producthunt, reddit

EMPTY_ATOM = '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom"></feed>'


class TestProductHunt:
    def test_parses_fixture(self, load_text, today):
        projects = producthunt.parse(load_text("producthunt_feed.xml"), today)
        assert len(projects) >= 5
        for p in projects:
            assert validate_project(p) == [], validate_project(p)
            assert p["id"].startswith("producthunt:")

    def test_time_window_excludes_old_entries(self, load_text, today):
        far_future = today + datetime.timedelta(days=365)
        assert producthunt.parse(load_text("producthunt_feed.xml"), far_future) == []

    def test_empty_feed(self, today):
        assert producthunt.parse(EMPTY_ATOM, today) == []

    def test_description_discussion_link_residue_removed(self, load_text, today):
        # feed 内容尾部的「Discussion              |              Link」导航残留必须清掉
        for p in producthunt.parse(load_text("producthunt_feed.xml"), today):
            assert "Discussion" not in p["description"], p["description"]

    def test_malformed_xml_raises(self, today):
        with pytest.raises(Exception):
            producthunt.parse("not xml at all", today)


class TestArxiv:
    def test_parses_fixture(self, load_text, today):
        projects = arxiv.parse(load_text("arxiv_feed.xml"), today)
        assert len(projects) >= 10
        for p in projects:
            assert validate_project(p) == [], validate_project(p)
            assert p["url"].startswith("https://arxiv.org/abs/")
            assert len(p["description"]) <= 500

    def test_title_whitespace_normalized(self, load_text, today):
        for p in arxiv.parse(load_text("arxiv_feed.xml"), today):
            assert "\n" not in p["name"] and "  " not in p["name"]

    def test_time_window_excludes_old_entries(self, load_text, today):
        far_future = today + datetime.timedelta(days=365)
        assert arxiv.parse(load_text("arxiv_feed.xml"), far_future) == []

    def test_empty_feed(self, today):
        assert arxiv.parse(EMPTY_ATOM, today) == []


class TestReddit:
    def test_parses_fixture(self, load_text, today):
        projects = reddit.parse(load_text("reddit_top.rss"), today)
        assert len(projects) >= 10
        for p in projects:
            assert validate_project(p) == [], validate_project(p)
            assert not p["id"].startswith("reddit:t3_")   # t3_ 前缀应剥掉
            assert p["metrics"]["subreddit"]

    def test_week_rank_is_sequential(self, load_text, today):
        projects = reddit.parse(load_text("reddit_top.rss"), today)
        assert [p["metrics"]["week_rank"] for p in projects] == list(range(1, len(projects) + 1))

    def test_description_html_stripped(self, load_text, today):
        for p in reddit.parse(load_text("reddit_top.rss"), today):
            assert "<" not in p["description"] or ">" not in p["description"]
            assert "submitted by" not in p["description"]

    def test_empty_feed(self, today):
        assert reddit.parse(EMPTY_ATOM, today) == []

    def test_one_feed_per_subreddit(self, today):
        assert len(reddit.urls(today)) == len(reddit.SUBREDDITS)
