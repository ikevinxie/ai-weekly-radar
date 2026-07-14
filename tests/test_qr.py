"""QR 生成测试。快照 fixture 由 python-qrcode 交叉比对验证后录制（见 SPEC.md「二维码」）。"""
import json
import pathlib

import pytest

from collector import qr

SNAPSHOTS = json.loads(
    (pathlib.Path(__file__).parent / "fixtures" / "qr_snapshots.json").read_text())


class TestSnapshots:
    @pytest.mark.parametrize("text", list(SNAPSHOTS))
    def test_matches_cross_validated_snapshot(self, text):
        assert qr.rows(text) == SNAPSHOTS[text]


class TestStructure:
    def test_version_adaptive_size(self):
        assert len(qr.matrix("A" * 14)) == 21    # v1
        assert len(qr.matrix("A" * 15)) == 25    # v2
        assert len(qr.matrix("A" * 62)) == 33    # v4
        assert len(qr.matrix("A" * 106)) == 41   # v6

    def test_too_long_raises(self):
        with pytest.raises(ValueError, match="容量"):
            qr.matrix("A" * 107)

    def test_finder_patterns_present(self):
        m = qr.matrix("https://ikevinxie.github.io/ai-weekly-radar/#2026-W29")
        size = len(m)
        for r0, c0 in ((0, 0), (0, size - 7), (size - 7, 0)):
            # 定位符外圈全暗、次圈全亮
            assert all(m[r0][c0 + i] and m[r0 + 6][c0 + i] for i in range(7))
            assert all(m[r0 + i][c0] and m[r0 + i][c0 + 6] for i in range(7))
            assert not any(m[r0 + 1][c0 + 1 + i] for i in range(5))

    def test_timing_pattern_alternates(self):
        m = qr.matrix("HELLO")
        size = len(m)
        for i in range(8, size - 8):
            assert m[6][i] == (i % 2 == 0)
            assert m[i][6] == (i % 2 == 0)

    def test_rows_are_binary_strings(self):
        rows = qr.rows("HELLO")
        assert len(rows) == 21
        assert all(len(r) == 21 and set(r) <= {"0", "1"} for r in rows)

    def test_deterministic(self):
        url = "https://ikevinxie.github.io/ai-weekly-radar/#archive"
        assert qr.rows(url) == qr.rows(url)
