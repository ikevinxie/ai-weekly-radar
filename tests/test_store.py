import datetime
import json

from collector import store
from collector.schema import make_project


def proj(pid, week_date=datetime.date(2026, 7, 13), **extra):
    p = make_project(
        id=f"github:{pid}", name=pid, url="https://example.com", source="github",
        description="d", collected_at=week_date, metrics={},
    )
    p.update(extra)
    return p


class TestLoadSave:
    def test_load_missing_file_returns_empty(self, tmp_path):
        assert store.load(tmp_path / "nope.json") == []

    def test_roundtrip_preserves_unicode(self, tmp_path):
        path = tmp_path / "projects.json"
        projects = [proj("a", reason="脑洞很大")]
        store.save(projects, path)
        assert store.load(path) == projects
        assert "脑洞很大" in path.read_text(encoding="utf-8")   # 不转义中文

    def test_save_creates_parent_dirs(self, tmp_path):
        path = tmp_path / "deep" / "projects.json"
        store.save([], path)
        assert json.loads(path.read_text()) == []


class TestMerge:
    def test_appends_new(self):
        merged = store.merge([proj("a")], [proj("b")])
        assert [p["id"] for p in merged] == ["github:a", "github:b"]

    def test_existing_entry_wins_on_conflict(self):
        old = proj("a", reason="旧的")
        merged = store.merge([old], [proj("a", reason="新的")])
        assert len(merged) == 1
        assert merged[0]["reason"] == "旧的"

    def test_merge_does_not_mutate_inputs(self):
        existing = [proj("a")]
        store.merge(existing, [proj("b")])
        assert len(existing) == 1


class TestQueries:
    def test_by_week_and_weeks(self):
        projects = [
            proj("a", datetime.date(2026, 7, 13)),   # W29
            proj("b", datetime.date(2026, 7, 6)),    # W28
            proj("c", datetime.date(2026, 7, 17)),   # W29
        ]
        assert [p["id"] for p in store.by_week(projects, "2026-W29")] == ["github:a", "github:c"]
        assert store.weeks(projects) == ["2026-W29", "2026-W28"]
