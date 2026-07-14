from collector.awards import compute_awards


def proj(pid, whimsy, fun, money):
    return {"id": pid, "scores": {"whimsy": whimsy, "fun": fun, "money": money,
                                  "total": whimsy + fun + money}}


def by_key(awards):
    return {a["key"]: a["project_id"] for a in awards}


class TestComputeAwards:
    def test_three_awards_distinct_winners(self):
        awards = compute_awards([
            proj("a", 9, 9, 9),   # total 27 → best
            proj("b", 10, 2, 0),  # whimsy-money 10 → wildest
            proj("c", 0, 2, 10),  # money-whimsy 10 → quiet_money
        ])
        assert by_key(awards) == {"best": "a", "wildest": "b", "quiet_money": "c"}
        assert all(a["emoji"] and a["title"]["zh"] and a["title"]["en"] for a in awards)

    def test_one_project_sweeps_all(self):
        awards = compute_awards([proj("only", 5, 5, 5)])
        assert set(by_key(awards).values()) == {"only"}
        assert len(awards) == 3

    def test_tie_broken_by_total_then_id(self):
        # wildest 并列（差值都是 5）：b 总分更高胜出
        awards = compute_awards([proj("a", 5, 0, 0), proj("b", 5, 9, 0)])
        assert by_key(awards)["wildest"] == "b"
        # 完全同分时按 id 字典序
        awards = compute_awards([proj("x", 5, 3, 0), proj("w", 5, 3, 0)])
        assert by_key(awards)["wildest"] == "w"

    def test_empty_and_unscored_input(self):
        assert compute_awards([]) == []
        assert compute_awards([{"id": "cand", "name": "no scores"}]) == []
