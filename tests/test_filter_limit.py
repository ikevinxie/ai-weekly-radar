"""回归：每源默认上限 10，保证 6 源总候选 ≤ 60（SPEC「粗筛规则」）。"""
import datetime

from collector.filter import PER_SOURCE_LIMIT, filter_projects
from collector.schema import SOURCES, make_project


def test_default_limit_is_ten():
    assert PER_SOURCE_LIMIT == 10


def test_six_sources_cap_at_sixty():
    batch = []
    for source in SOURCES:
        for i in range(20):
            batch.append(make_project(
                id=f"{source}:{i}", name=f"llm tool {i}", url="https://example.com",
                source=source, description="an ai agent", collected_at=datetime.date(2026, 7, 13),
                metrics={"stars": 100, "points": 100, "likes": 100, "upvotes": 100},
            ))
    assert len(filter_projects(batch, known_ids=set())) == 60
