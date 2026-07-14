from collector.awards import AWARD_DEFS, compute_awards


def proj(pid, whimsy, fun, money, source="producthunt", **metrics):
    return {"id": pid, "source": source, "metrics": metrics,
            "scores": {"whimsy": whimsy, "fun": fun, "money": money,
                       "total": whimsy + fun + money}}


def by_key(awards):
    return {a["key"]: a["project_id"] for a in awards}


class TestClassicAwards:
    def test_three_awards_distinct_winners(self):
        awards = compute_awards([
            proj("a", 9, 9, 9),   # total 27 → best
            proj("b", 10, 2, 0),  # whimsy-money 10 → wildest
            proj("c", 0, 2, 10),  # money-whimsy 10 → quiet_money
        ])
        got = by_key(awards)
        assert got["best"] == "a" and got["wildest"] == "b" and got["quiet_money"] == "c"
        assert all(a["emoji"] and a["title"]["zh"] and a["title"]["en"] for a in awards)

    def test_one_project_sweeps_all_grantable(self):
        awards = compute_awards([proj("only", 5, 5, 5)])
        assert set(by_key(awards).values()) == {"only"}
        # 非论文、无热度指标 → hardcore 和 dark_horse 空缺
        assert set(by_key(awards)) == {"best", "wildest", "quiet_money", "funnest", "polarized"}

    def test_tie_broken_by_total_then_id(self):
        awards = compute_awards([proj("a", 5, 0, 0), proj("b", 5, 9, 0)])
        assert by_key(awards)["wildest"] == "b"   # 差值并列，总分高者胜
        awards = compute_awards([proj("x", 5, 3, 0), proj("w", 5, 3, 0)])
        assert by_key(awards)["wildest"] == "w"   # 完全同分按 id

    def test_empty_and_unscored_input(self):
        assert compute_awards([]) == []
        assert compute_awards([{"id": "cand", "name": "no scores"}]) == []


class TestNewAwards:
    def test_funnest_and_polarized(self):
        awards = compute_awards([
            proj("flat", 5, 5, 5),
            proj("funny", 2, 10, 2),    # fun 最高 → funnest；极差 8 → polarized
            proj("split", 9, 5, 0),     # 极差 9 → polarized 胜出
        ])
        got = by_key(awards)
        assert got["funnest"] == "funny"
        assert got["polarized"] == "split"

    def test_hardcore_only_papers_eligible(self):
        awards = compute_awards([
            proj("gh", 9, 9, 9, source="github", stars=500),
            proj("paper-low", 5, 2, 2, source="arxiv"),
            proj("hf-paper", 6, 2, 2, source="huggingface", kind="paper", upvotes=30),
        ])
        assert by_key(awards)["hardcore"] == "hf-paper"   # 论文中 total 最高（10 vs 9）

    def test_hardcore_absent_without_papers(self):
        awards = compute_awards([proj("gh", 9, 9, 9, source="github", stars=100)])
        assert "hardcore" not in by_key(awards)

    def test_hf_space_not_counted_as_paper(self):
        awards = compute_awards([proj("space", 9, 9, 9, source="huggingface",
                                      kind="space", likes=100)])
        assert "hardcore" not in by_key(awards)

    def test_dark_horse_lowest_heat_in_top_third(self):
        batch = [proj(f"hot{i}", 8, 8, 8, source="github", stars=1000 + i) for i in range(5)]
        batch.append(proj("quiet", 8, 8, 9, source="github", stars=52))   # 高分低热度
        batch.extend(proj(f"low{i}", 1, 1, 1, source="github", stars=51) for i in range(12))
        # 前 1/3（18 个里取 6 个）全是高分组，quiet 热度最低
        assert by_key(compute_awards(batch))["dark_horse"] == "quiet"

    def test_dark_horse_absent_when_top_third_has_no_heat(self):
        # 前 1/3 只有无热度指标的 ph（总分最高），奖项空缺——不从后排递补
        awards = compute_awards([
            proj("ph", 9, 9, 9),
            proj("gh", 8, 8, 8, source="github", stars=200),
        ])
        assert "dark_horse" not in by_key(awards)

    def test_dark_horse_skips_heatless_within_top_third(self):
        # 前 1/3 内既有无热度也有有热度的项目：只在有热度者中选
        batch = [proj("ph", 9, 9, 9),
                 proj("gh", 8, 8, 9, source="github", stars=70),
                 proj("hn", 8, 8, 8, source="hackernews", points=300)]
        batch.extend(proj(f"low{i}", 1, 1, 1, source="github", stars=60) for i in range(6))
        # 9 个项目前 1/3 = 3 个（ph/gh/hn），有热度的是 gh(70) 和 hn(300)
        assert by_key(compute_awards(batch))["dark_horse"] == "gh"

    def test_dark_horse_absent_when_no_heat_anywhere(self):
        awards = compute_awards([proj("ph", 9, 9, 9), proj("ph2", 1, 1, 1)])
        assert "dark_horse" not in by_key(awards)

    def test_award_defs_have_seven(self):
        assert len(AWARD_DEFS) == 7
        assert len({d["key"] for d in AWARD_DEFS}) == 7
