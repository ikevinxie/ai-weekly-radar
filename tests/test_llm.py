"""collector/llm.py 离线测试。所有网络调用 mock，不打真实 API。"""
import json
from unittest import mock

import pytest

from collector.llm import (BATCH_SIZE, extract_json, score_backfill,
                           score_candidates, summarize_voices, chat)


# ---------------------------------------------------------------------------
# extract_json
# ---------------------------------------------------------------------------

class TestExtractJson:
    def test_plain_json(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_json_array(self):
        assert extract_json('[{"id": "x"}]') == [{"id": "x"}]

    def test_markdown_fence(self):
        text = '这是评分结果：\n```json\n{"week": "2026-W31"}\n```\n完成。'
        assert extract_json(text) == {"week": "2026-W31"}

    def test_markdown_fence_no_lang(self):
        text = '```\n[{"id": "a"}]\n```'
        assert extract_json(text) == [{"id": "a"}]

    def test_prefix_suffix_text(self):
        text = '好的，以下是评分：\n{"entries": []}\n希望对你有帮助！'
        assert extract_json(text) == {"entries": []}

    def test_array_in_text(self):
        text = '结果如下\n[{"id": "x"}, {"id": "y"}]\n以上。'
        assert extract_json(text) == [{"id": "x"}, {"id": "y"}]

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="无法从 LLM 回复中提取 JSON"):
            extract_json("完全没有 JSON 内容")

    def test_whitespace(self):
        assert extract_json('  \n {"ok": true} \n ') == {"ok": True}


# ---------------------------------------------------------------------------
# chat（mock urllib）
# ---------------------------------------------------------------------------

def _mock_urlopen(reply_text):
    """构造 mock urlopen 上下文管理器，返回百炼 API 格式响应。"""
    body = json.dumps({
        "choices": [{"message": {"content": reply_text}}]
    }).encode()

    class FakeResp:
        def read(self):
            return body
        def __enter__(self):
            return self
        def __exit__(self, *a):
            pass

    return mock.patch("collector.llm.urllib.request.urlopen", return_value=FakeResp())


class TestChat:
    def test_returns_content(self):
        with _mock_urlopen("hello"), \
             mock.patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}):
            assert chat("test prompt") == "hello"

    def test_missing_api_key(self):
        with mock.patch.dict("os.environ", {}, clear=True):
            import os
            os.environ.pop("DASHSCOPE_API_KEY", None)
            with pytest.raises(RuntimeError, match="DASHSCOPE_API_KEY"):
                chat("test")

    def test_retry_on_failure(self):
        import urllib.error
        calls = []
        def fake_urlopen(*a, **kw):
            calls.append(1)
            if len(calls) < 3:
                raise urllib.error.URLError("timeout")
            body = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()
            class R:
                def read(self): return body
                def __enter__(self): return self
                def __exit__(self, *a): pass
            return R()

        with mock.patch("collector.llm.urllib.request.urlopen", side_effect=fake_urlopen), \
             mock.patch.dict("os.environ", {"DASHSCOPE_API_KEY": "sk-test"}), \
             mock.patch("collector.llm.time.sleep"):
            assert chat("test") == "ok"
            assert len(calls) == 3


# ---------------------------------------------------------------------------
# score_candidates（mock chat）
# ---------------------------------------------------------------------------

def _make_candidates(n):
    return [{"id": f"github:test/{i}", "name": f"proj-{i}", "source": "github",
             "url": f"https://github.com/test/{i}", "description": f"desc {i}",
             "metrics": {"stars": 100 + i}} for i in range(n)]


def _fake_entry(pid, total=20):
    return {"id": pid, "scores": {"whimsy": 7, "fun": 7, "money": 6, "total": total},
            "reason": "测试理由", "analysis": {"zh": "中文", "en": "English"},
            "deep_dive": {"zh": {"what": "w", "why": "y", "biz": "b"},
                          "en": {"what": "w", "why": "y", "biz": "b"}},
            "tags": ["agent"]}


class TestScoreCandidates:
    def test_single_batch(self):
        cands = _make_candidates(3)
        entries = [_fake_entry(c["id"]) for c in cands]
        trend = {"zh": "风向", "en": "trend", "deep": {"zh": "深度", "en": "deep"}}
        replies = [json.dumps(entries), json.dumps(trend)]
        with mock.patch("collector.llm.chat", side_effect=replies):
            result = score_candidates(cands, "2026-W31")
        assert result["week"] == "2026-W31"
        assert len(result["entries"]) == 3
        assert result["trend"]["zh"] == "风向"

    def test_multi_batch(self):
        cands = _make_candidates(BATCH_SIZE + 5)
        batch1 = [_fake_entry(c["id"]) for c in cands[:BATCH_SIZE]]
        batch2 = [_fake_entry(c["id"]) for c in cands[BATCH_SIZE:]]
        trend = {"zh": "z", "en": "e", "deep": {"zh": "dz", "en": "de"}}
        replies = [json.dumps(batch1), json.dumps(batch2), json.dumps(trend)]
        with mock.patch("collector.llm.chat", side_effect=replies):
            result = score_candidates(cands, "2026-W31")
        assert len(result["entries"]) == BATCH_SIZE + 5

    def test_entries_wrapped_in_object(self):
        cands = _make_candidates(2)
        entries = [_fake_entry(c["id"]) for c in cands]
        trend = {"zh": "z", "en": "e", "deep": {"zh": "dz", "en": "de"}}
        replies = [json.dumps({"entries": entries}), json.dumps(trend)]
        with mock.patch("collector.llm.chat", side_effect=replies):
            result = score_candidates(cands, "2026-W31")
        assert len(result["entries"]) == 2

    def test_retries_on_malformed_json_then_succeeds(self):
        # 第一次返回畸形 JSON（模拟 LLM 写错括号），第二次返回合法 JSON
        cands = _make_candidates(2)
        entries = [_fake_entry(c["id"]) for c in cands]
        trend = {"zh": "z", "en": "e", "deep": {"zh": "dz", "en": "de"}}
        malformed = '[{"id": "github:test/0", "analysis": )'   # 语法错
        replies = [malformed, json.dumps(entries), json.dumps(trend)]
        with mock.patch("collector.llm.chat", side_effect=replies) as m:
            result = score_candidates(cands, "2026-W31")
        assert len(result["entries"]) == 2
        # 1 次原始 + 1 次修正 + 1 次 trend = 3
        assert m.call_count == 3

    def test_raises_after_parse_retries_exhausted(self):
        from collector.llm import PARSE_RETRIES
        cands = _make_candidates(1)
        # 全部返回无法解析的文本：原始 1 次 + PARSE_RETRIES 次修正
        replies = ["not json at all"] * (PARSE_RETRIES + 1)
        with mock.patch("collector.llm.chat", side_effect=replies) as m, \
             pytest.raises(ValueError, match="无法从 LLM 回复中提取 JSON"):
            score_candidates(cands, "2026-W31")
        assert m.call_count == PARSE_RETRIES + 1

    def test_prompt_tag_list_in_sync_with_TAGS(self):
        # 回归锁死：_BATCH_TEMPLATE 的词表必须从 scoring.TAGS 动态生成，
        # 否则加新词表时只改 scoring.TAGS 不改 prompt，LLM 仍会乱写。
        from collector.llm import _BATCH_TEMPLATE, _TAGS
        from collector.scoring import TAGS
        assert _TAGS is TAGS or set(_TAGS) == set(TAGS)
        rendered = _BATCH_TEMPLATE.format(count=1, tags=" ".join(_TAGS),
                                          candidates="- id: x\n  名称: X\n  来源: github\n  链接: u\n  描述: d")
        for tag in TAGS:
            assert tag in rendered, f"prompt 缺词表项 {tag!r}"
        # 反向断言：prompt 里不应再硬编码旧词表（如果硬编码，加新词后会缺）
        assert "开源" in rendered


class TestScoreBackfill:
    def test_returns_entries_without_trend_call(self):
        # 补评只评漏写的候选，不生成 trend（trend 由 score_candidates 统一生成）
        cands = _make_candidates(2)
        entries = [_fake_entry(c["id"]) for c in cands]
        with mock.patch("collector.llm.chat",
                        return_value=json.dumps(entries)) as m:
            result = score_backfill(cands)
        assert result == entries
        assert m.call_count == 1

    def test_unwraps_entries_object(self):
        cands = _make_candidates(1)
        entries = [_fake_entry(c["id"]) for c in cands]
        with mock.patch("collector.llm.chat",
                        return_value=json.dumps({"entries": entries})):
            assert score_backfill(cands) == entries


# ---------------------------------------------------------------------------
# summarize_voices（mock chat）
# ---------------------------------------------------------------------------

class TestSummarizeVoices:
    def test_basic(self):
        posts = [{"author": "Swyx", "handle": "swyx", "text": "AI is eating software",
                  "url": "https://x.com/swyx/status/1", "date": "2026-07-25", "likes": 100}]
        doc = {"week": "2026-W31",
               "overview": {"zh": "总览", "en": "overview"},
               "themes": [{"title": {"zh": "主题", "en": "Theme"},
                           "summary": {"zh": "归纳", "en": "summary"},
                           "quotes": [{"author": "Swyx", "handle": "swyx",
                                       "text": "AI is eating software",
                                       "url": "https://x.com/swyx/status/1",
                                       "date": "2026-07-25"}]}]}
        with mock.patch("collector.llm.chat", return_value=json.dumps(doc)):
            result = summarize_voices(posts, "2026-W31")
        assert result["week"] == "2026-W31"
        assert len(result["themes"]) == 1

    def test_week_corrected(self):
        posts = [{"author": "A", "handle": "a", "text": "t",
                  "url": "https://x.com/a/1", "date": "2026-07-25", "likes": 0}]
        doc = {"week": "WRONG", "overview": {"zh": "z", "en": "e"},
               "themes": [{"title": {"zh": "t", "en": "t"},
                           "summary": {"zh": "s", "en": "s"},
                           "quotes": [{"author": "A", "handle": "a", "text": "t",
                                       "url": "https://x.com/a/1", "date": "2026-07-25"}]}]}
        with mock.patch("collector.llm.chat", return_value=json.dumps(doc)):
            result = summarize_voices(posts, "2026-W31")
        assert result["week"] == "2026-W31"
