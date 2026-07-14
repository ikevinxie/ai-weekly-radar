import datetime

import pytest

from collector.filter import filter_projects, is_ai_related, passes_threshold
from collector.schema import make_project


def proj(source="github", pid="x", name="AI tool", desc="an llm agent", **metrics):
    return make_project(
        id=f"{source}:{pid}", name=name, url="https://example.com", source=source,
        description=desc, collected_at=datetime.date(2026, 7, 13), metrics=metrics,
    )


class TestIsAiRelated:
    @pytest.mark.parametrize("text", [
        "An AI assistant", "local LLM runner", "GPT wrapper", "RAG pipeline",
        "machine learning toolkit", "diffusion model playground", "多模态大模型",
        "voice clone studio", "text-to-video generator",
    ])
    def test_hits(self, text):
        assert is_ai_related(proj(name=text, desc=""))

    @pytest.mark.parametrize("text", [
        "A fast email client",      # email 不应命中 ai
        "terminal file manager",
        "paint your house",         # paint 不应命中 ai
        "smland toolkit",           # 不应命中 ml
    ])
    def test_misses(self, text):
        assert not is_ai_related(proj(name=text, desc=""))

    def test_arxiv_and_hf_skip_keyword_check(self):
        assert is_ai_related(proj(source="arxiv", name="Obscure math title", desc=""))
        assert is_ai_related(proj(source="huggingface", name="flux-dev", desc=""))

    def test_description_also_searched(self):
        assert is_ai_related(proj(name="Untitled", desc="a neural renderer"))


class TestPassesThreshold:
    def test_github_stars(self):
        assert passes_threshold(proj(stars=50))
        assert not passes_threshold(proj(stars=49))

    def test_hackernews_points(self):
        assert passes_threshold(proj(source="hackernews", points=50))
        assert not passes_threshold(proj(source="hackernews", points=10))

    def test_huggingface_space_likes_and_paper_upvotes(self):
        assert passes_threshold(proj(source="huggingface", kind="space", likes=20))
        assert not passes_threshold(proj(source="huggingface", kind="space", likes=5))
        assert passes_threshold(proj(source="huggingface", kind="paper", upvotes=10))
        assert not passes_threshold(proj(source="huggingface", kind="paper", upvotes=3))

    def test_no_threshold_sources(self):
        assert passes_threshold(proj(source="producthunt"))
        assert passes_threshold(proj(source="arxiv"))
        assert passes_threshold(proj(source="reddit", week_rank=25))


class TestFilterProjects:
    def test_dedup_against_history(self):
        p = proj(pid="a", stars=100)
        assert filter_projects([p], known_ids={"github:a"}) == []
        assert filter_projects([p], known_ids=set()) == [p]

    def test_dedup_within_batch(self):
        p = proj(pid="a", stars=100)
        assert len(filter_projects([p, dict(p)], known_ids=set())) == 1

    def test_per_source_limit_keeps_hottest(self):
        batch = [proj(pid=str(i), stars=50 + i) for i in range(20)]
        kept = filter_projects(batch, known_ids=set(), per_source_limit=5)
        assert len(kept) == 5
        assert [p["metrics"]["stars"] for p in kept] == [69, 68, 67, 66, 65]

    def test_reddit_ranked_by_week_rank(self):
        batch = [proj(source="reddit", pid=str(i), week_rank=i) for i in (3, 1, 2)]
        kept = filter_projects(batch, known_ids=set(), per_source_limit=2)
        assert [p["metrics"]["week_rank"] for p in kept] == [1, 2]

    def test_drops_non_ai_and_below_threshold(self):
        batch = [
            proj(pid="ok", stars=100),
            proj(pid="cold", stars=3),
            proj(pid="offtopic", name="fast email client", desc="", stars=500),
        ]
        assert [p["id"] for p in filter_projects(batch, known_ids=set())] == ["github:ok"]

    def test_multiple_sources_grouped(self):
        batch = [proj(pid="g", stars=99), proj(source="arxiv", pid="p", name="Anything", desc="")]
        kept = filter_projects(batch, known_ids=set())
        assert {p["source"] for p in kept} == {"github", "arxiv"}
