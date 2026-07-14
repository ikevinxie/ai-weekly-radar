import datetime
import json

import pytest

from collector import tracking


def gh(pid, total=20, stars=100):
    return {"id": f"github:{pid}", "name": pid, "url": f"https://github.com/{pid}",
            "source": "github", "week": "2026-W29", "metrics": {"stars": stars},
            "scores": {"whimsy": 8, "fun": 7, "money": total - 15, "total": total}}


class TestParseRepo:
    def test_parses_fixture(self, load_json):
        assert tracking.parse_repo(load_json("github_repo.json")) == 498

    def test_missing_field_raises(self):
        with pytest.raises(ValueError, match="stargazers_count"):
            tracking.parse_repo({"full_name": "a/b"})


class TestGithubTargets:
    def test_filters_sorts_limits(self):
        history = [
            gh("low", total=10), gh("high", total=25), gh("mid", total=20),
            {"id": "hackernews:1", "source": "hackernews",
             "scores": {"whimsy": 9, "fun": 9, "money": 9, "total": 27}},   # 非 GitHub
            {"id": "github:cand", "source": "github", "metrics": {}},        # 未评分
        ]
        targets = tracking.github_targets(history, limit=2)
        assert [t["id"] for t in targets] == ["github:high", "github:mid"]


class TestSnapshot:
    def test_appends_and_same_day_overwrites(self, tmp_path, monkeypatch):
        path = tmp_path / "tracking.json"
        monkeypatch.setattr(tracking, "fetch_stars", lambda repo: 500)
        history = [gh("a")]
        result = tracking.snapshot(history, datetime.date(2026, 8, 1), path=path, delay=0)
        assert result == {"targets": 1, "ok": 1, "failed": 0}

        monkeypatch.setattr(tracking, "fetch_stars", lambda repo: 750)
        tracking.snapshot(history, datetime.date(2026, 8, 1), path=path, delay=0)   # 同日重跑
        tracking.snapshot(history, datetime.date(2026, 9, 1), path=path, delay=0)   # 次月
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["github:a"] == [{"date": "2026-08-01", "stars": 750},
                                    {"date": "2026-09-01", "stars": 750}]

    def test_single_repo_failure_tolerated(self, tmp_path, monkeypatch):
        def flaky(repo):
            if repo == "bad":
                raise RuntimeError("HTTP Error 500")
            return 300
        monkeypatch.setattr(tracking, "fetch_stars", flaky)
        result = tracking.snapshot([gh("bad", total=25), gh("ok", total=20)],
                                   datetime.date(2026, 8, 1),
                                   path=tmp_path / "t.json", delay=0)
        assert result["ok"] == 1 and result["failed"] == 1

    def test_rate_limit_stops_early(self, tmp_path, monkeypatch):
        calls = []
        def limited(repo):
            calls.append(repo)
            raise RuntimeError("HTTP Error 403: rate limit exceeded")
        monkeypatch.setattr(tracking, "fetch_stars", limited)
        tracking.snapshot([gh("a", total=25), gh("b", total=20)],
                          datetime.date(2026, 8, 1), path=tmp_path / "t.json", delay=0)
        assert calls == ["a"]   # 403 后不再继续打


class TestComputeLiftoff:
    def test_ratio_ranking(self):
        history = [gh("slow", stars=100), gh("fast", stars=100), gh("untracked")]
        track = {"github:slow": [{"date": "2026-08-01", "stars": 150}],
                 "github:fast": [{"date": "2026-08-01", "stars": 900}]}
        rows = tracking.compute_liftoff(history, track)
        assert [r["id"] for r in rows] == ["github:fast", "github:slow"]
        assert rows[0]["ratio"] == 9.0 and rows[0]["stars_then"] == 100

    def test_zero_baseline_and_missing_project_skipped(self):
        history = [gh("z", stars=0)]
        track = {"github:z": [{"date": "d", "stars": 10}],
                 "github:ghost": [{"date": "d", "stars": 10}]}
        assert tracking.compute_liftoff(history, track) == []

    def test_load_missing_file(self, tmp_path):
        assert tracking.load_tracking(tmp_path / "nope.json") == {}
