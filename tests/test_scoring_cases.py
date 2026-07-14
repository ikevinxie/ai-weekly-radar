"""校验 scoring_cases/cases.json 本身的结构合法（用例资产不能悄悄坏掉）。"""
import json
import pathlib

from collector.schema import SCORE_KEYS

CASES_PATH = pathlib.Path(__file__).parent / "scoring_cases" / "cases.json"


def test_cases_file_well_formed():
    data = json.loads(CASES_PATH.read_text(encoding="utf-8"))
    cases = data["cases"]
    assert len(cases) >= 4
    for case in cases:
        assert case["project"]["id"] and case["project"]["description"]
        assert case["why"]
        for key in SCORE_KEYS:
            low, high = case["expected"][key]
            assert 0 <= low <= high <= 10, f"{case['project']['id']}: {key} 区间非法"
