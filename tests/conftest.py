import datetime
import json
import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    return FIXTURES


@pytest.fixture
def load_json():
    def _load(name):
        return json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    return _load


@pytest.fixture
def load_text():
    def _load(name):
        return (FIXTURES / name).read_text(encoding="utf-8")
    return _load


@pytest.fixture
def today():
    # fixture 录制日（2026-07-13，周一，2026-W29），时间窗口测试相对它计算
    return datetime.date(2026, 7, 13)
