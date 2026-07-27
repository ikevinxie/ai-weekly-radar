import json

import pytest

from collector import feishu
from collector import feishu_sent


def proj(pid, name, total_parts=(8, 7, 5)):
    w, f, m = total_parts
    return {"id": f"github:{pid}", "name": name, "url": f"https://github.com/{pid}",
            "reason": "值得一看", "analysis": {"zh": "中文简读。", "en": "Brief."},
            "scores": {"whimsy": w, "fun": f, "money": m, "total": w + f + m}}


AWARDS = [{"key": "best", "emoji": "🏆", "title": {"zh": "本周最佳", "en": "Best"},
           "project_id": "github:p0"}]


def card_text(card):
    return json.dumps(card, ensure_ascii=False)


class TestBuildCard:
    def test_title_contains_keyword_ai_xiangmu(self):
        # 回归锁死：机器人配置了关键词「AI项目」，标题必须含该字面量，否则消息被拒收
        card = feishu.build_card("2026-W29", "", [proj("p0", "X")], [])
        assert "AI项目" in card["card"]["header"]["title"]["content"]

    def test_contains_top10_trend_awards_and_link(self):
        top10 = [proj(f"p{i}", f"Project-{i}") for i in range(10)]
        card = feishu.build_card("2026-W29", "本周风向如此。", top10, AWARDS)
        text = card_text(card)
        assert card["msg_type"] == "interactive"
        assert "AI项目周报 2026-W29" in text
        for i in range(10):
            assert f"Project-{i}" in text
        assert "本周风向如此。" in text
        assert "🏆" in text and "本周最佳" in text
        assert "#2026-W29" in text          # 深度解读按钮链到站点对应周
        assert "总分 20" in text and "中文简读。" in text

    def test_award_medal_attached_to_winner_item(self):
        card = feishu.build_card("2026-W29", "", [proj("p0", "Winner")], AWARDS)
        item = next(e for e in card["card"]["elements"]
                    if e.get("tag") == "div" and "Winner" in e["text"]["content"])
        assert "🏆" in item["text"]["content"]

    def test_no_trend_no_awards_still_valid(self):
        card = feishu.build_card("2026-W29", "", [proj("p0", "Solo")], [])
        text = card_text(card)
        assert "本周风向" not in text and "彩蛋奖" not in text
        assert "Solo" in text

    def test_size_guard(self):
        big = [proj(f"p{i}", "X" * 4000) for i in range(10)]
        with pytest.raises(ValueError, match="超过"):
            feishu.build_card("2026-W29", "", big, [])

    def test_realistic_card_under_limit(self):
        top10 = [proj(f"p{i}", f"project-{i}/repo-name-{i}") for i in range(10)]
        for p in top10:
            p["analysis"]["zh"] = "这是一段比较长的中文简读，" * 5
        card = feishu.build_card("2026-W29", "风向" * 100, top10, AWARDS)
        assert len(card_text(card).encode("utf-8")) < feishu.MAX_CARD_BYTES


class TestWebhookConfig:
    def test_env_var_wins(self, monkeypatch):
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://open.feishu.cn/hook/abc")
        assert feishu.webhook_url() == "https://open.feishu.cn/hook/abc"

    def test_fallback_file(self, monkeypatch, tmp_path):
        monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
        hook_file = tmp_path / "feishu_webhook"
        hook_file.write_text("https://open.feishu.cn/hook/from-file\n")
        monkeypatch.setattr(feishu, "WEBHOOK_FILE", hook_file)
        assert feishu.webhook_url() == "https://open.feishu.cn/hook/from-file"

    def test_missing_returns_none_and_hint_mentions_setup(self, monkeypatch, tmp_path):
        monkeypatch.delenv("FEISHU_WEBHOOK_URL", raising=False)
        monkeypatch.setattr(feishu, "WEBHOOK_FILE", tmp_path / "nope")
        assert feishu.webhook_url() is None
        assert "自定义机器人" in feishu.SETUP_HINT


class TestSend:
    def test_raises_on_error_code(self, monkeypatch):
        monkeypatch.setattr(feishu, "post_json",
                            lambda url, payload: {"code": 19001, "msg": "param invalid"})
        with pytest.raises(RuntimeError, match="19001"):
            feishu.send({"msg_type": "interactive"}, "https://hook")

    def test_ok_on_code_zero_and_legacy(self, monkeypatch):
        monkeypatch.setattr(feishu, "post_json", lambda url, payload: {"code": 0})
        feishu.send({}, "https://hook")
        monkeypatch.setattr(feishu, "post_json", lambda url, payload: {"StatusCode": 0})
        feishu.send({}, "https://hook")


class TestFeishuSent:
    def test_was_sent_false_initially(self, monkeypatch, tmp_path):
        monkeypatch.setattr(feishu_sent, "SENT_DIR", tmp_path)
        assert feishu_sent.was_sent("2026-W31") is False

    def test_mark_then_was_sent(self, monkeypatch, tmp_path):
        monkeypatch.setattr(feishu_sent, "SENT_DIR", tmp_path)
        p = feishu_sent.mark_sent("2026-W31")
        assert p.exists()
        assert feishu_sent.was_sent("2026-W31") is True
        # 标记内容是 UTC ISO 时间戳，便于排查
        assert "Z" in p.read_text(encoding="utf-8")

    def test_different_weeks_independent(self, monkeypatch, tmp_path):
        monkeypatch.setattr(feishu_sent, "SENT_DIR", tmp_path)
        feishu_sent.mark_sent("2026-W30")
        assert feishu_sent.was_sent("2026-W30") is True
        assert feishu_sent.was_sent("2026-W31") is False


class TestCmdFeishuIdempotent:
    """cmd_feishu 的周级幂等：标记存在则跳过，--force 才重发。"""

    def _setup(self, monkeypatch, tmp_path):
        monkeypatch.setattr(feishu_sent, "SENT_DIR", tmp_path)
        monkeypatch.setenv("FEISHU_WEBHOOK_URL", "https://open.feishu.cn/hook/test")
        from collector import store
        week = "2026-W31"
        project = {
            "id": "github:p0", "name": "P0", "url": "https://github.com/p0",
            "source": "github", "week": week,
            "scores": {"whimsy": 8, "fun": 7, "money": 5, "total": 20},
            "reason": "test", "tags": ["agent"],
            "analysis": {"zh": "zh", "en": "en"},
        }
        # store.load 的默认参数在 def 时绑定，monkeypatch PROJECTS_PATH 不生效；
        # 直接 patch load 本身最稳。cmd_feishu 只调无参 load()。
        monkeypatch.setattr(store, "load", lambda path=None: [project])
        # scored 文件路径走 store.SCORED_DIR，这个 monkeypatch 有效（属性查找在调用时）
        scored_dir = tmp_path / "scored"
        scored_dir.mkdir()
        (scored_dir / f"{week}.json").write_text(
            json.dumps({"week": week, "trend": {"zh": "", "en": "",
                                                "deep": {"zh": "", "en": ""}},
                        "entries": [{"id": "github:p0",
                                     "scores": project["scores"],
                                     "reason": "test",
                                     "analysis": project["analysis"],
                                     "deep_dive": {"zh": {"what": "w", "why": "y", "biz": "b"},
                                                   "en": {"what": "w", "why": "y", "biz": "b"}},
                                     "tags": ["agent"]}]},
                       ensure_ascii=False),
            encoding="utf-8")
        monkeypatch.setattr(store, "SCORED_DIR", scored_dir)
        return week

    def test_first_send_marks_and_calls_webhook(self, monkeypatch, tmp_path):
        week = self._setup(monkeypatch, tmp_path)
        calls = []
        monkeypatch.setattr(feishu, "send", lambda card, url: calls.append(url))
        from collector.__main__ import cmd_feishu
        assert cmd_feishu([week]) == 0
        assert calls == ["https://open.feishu.cn/hook/test"]
        assert feishu_sent.was_sent(week) is True

    def test_second_send_skipped_without_force(self, monkeypatch, tmp_path, capsys):
        week = self._setup(monkeypatch, tmp_path)
        feishu_sent.mark_sent(week)
        calls = []
        monkeypatch.setattr(feishu, "send", lambda card, url: calls.append(url))
        from collector.__main__ import cmd_feishu
        assert cmd_feishu([week]) == 0
        assert calls == []
        assert "已推送过飞书" in capsys.readouterr().out

    def test_force_resends_even_when_marked(self, monkeypatch, tmp_path):
        week = self._setup(monkeypatch, tmp_path)
        feishu_sent.mark_sent(week)
        calls = []
        monkeypatch.setattr(feishu, "send", lambda card, url: calls.append(url))
        from collector.__main__ import cmd_feishu
        assert cmd_feishu([week, "--force"]) == 0
        assert calls == ["https://open.feishu.cn/hook/test"]

    def test_dry_run_does_not_mark(self, monkeypatch, tmp_path):
        week = self._setup(monkeypatch, tmp_path)
        from collector.__main__ import cmd_feishu
        assert cmd_feishu([week, "--dry-run"]) == 0
        assert feishu_sent.was_sent(week) is False
