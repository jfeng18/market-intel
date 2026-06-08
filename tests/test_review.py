import json
from unittest.mock import MagicMock, patch

import pytest

from market_intel.core.review import build_review_report, _window_label, _find_entry_in_window


def _mock_sync_result():
    return {
        "record_count": 100,
        "trade_date": "2026-06-08",
        "summary": {"total": 100, "limit_up": 5, "stage_high": 3},
        "errors": [],
        "warnings": [],
    }


def _mock_daily_payload():
    return {
        "ok": True,
        "command": "daily",
        "data": {
            "summary": "市场震荡偏强，算力链活跃。",
            "risk_flags": ["持仓集中度偏高"],
            "latest_trade_date": "2026-06-08",
            "brief": {"top_hotspots": []},
            "watchlist": {"count": 3, "items": []},
            "portfolio_review": {"items": []},
            "validation": {"ok": True, "summary": {}, "warnings": [], "errors": []},
        },
        "meta": {"generated_at": "2026-06-08T16:00:00+08:00"},
        "errors": [],
        "warnings": [],
    }


def test_review_report_basic_structure(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = build_review_report(
        sync_result=_mock_sync_result(),
        daily_payload=_mock_daily_payload(),
        window="day",
        save_journal=False,
    )

    assert result["window"] == "day"
    assert result["changes"]["available"] is False  # no journal history
    assert result["sync"]["record_count"] == 100
    assert result["daily_summary"] == "市场震荡偏强，算力链活跃。"
    assert result["risk_flags"] == ["持仓集中度偏高"]
    assert result["journal_saved"] is False
    assert result["agent_contract"]["boundary"]
    assert "data.command_queue" in result["agent_contract"]["stable_fields"]
    assert "data.command_queue[].state_effect" in result["agent_contract"]["stable_fields"]
    assert result["command_queue"]
    assert [item["command"] for item in result["command_queue"]] == result["next_commands"]
    assert not result["errors"]


def test_review_report_saves_journal(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = build_review_report(
        sync_result=_mock_sync_result(),
        daily_payload=_mock_daily_payload(),
        window="day",
        save_journal=True,
    )

    assert result["journal_saved"] is True
    assert result["journal_entry"] is not None
    assert result["journal_entry"]["trade_date"] == "2026-06-08"

    journal_dir = tmp_path / "runtime" / "journal"
    assert journal_dir.exists()
    entries = list(journal_dir.glob("*.json"))
    assert len(entries) == 1


def test_review_report_sample_runtime_skips_journal(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = build_review_report(
        sync_result=_mock_sync_result(),
        daily_payload=_mock_daily_payload(),
        window="day",
        save_journal=True,
        runtime_profile={"mode": "sample", "sample_datasets": ["quotes"]},
    )

    assert result["journal_saved"] is False
    assert result["journal_status"]["code"] == "sample_runtime"
    assert result["journal_status"]["sample_datasets"] == ["quotes"]
    assert any(w["code"] == "REVIEW_JOURNAL_SKIPPED_SAMPLE_RUNTIME" for w in result["warnings"])
    assert not (tmp_path / "runtime" / "journal").exists()


def test_review_report_with_journal_history(tmp_path, monkeypatch):
    """When there's a prior journal entry, changes should be available."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    first_payload = _mock_daily_payload()
    first_payload["data"]["risk_flags"] = ["量比异常"]
    build_review_report(
        sync_result=_mock_sync_result(),
        daily_payload=first_payload,
        window="day",
        save_journal=True,
    )

    second_payload = _mock_daily_payload()
    second_payload["data"]["risk_flags"] = ["持仓集中度偏高"]
    second_payload["meta"]["generated_at"] = "2026-06-08T17:00:00+08:00"

    result = build_review_report(
        sync_result=_mock_sync_result(),
        daily_payload=second_payload,
        window="day",
        save_journal=False,
    )

    assert result["changes"]["available"] is True
    assert result["changes"]["window"] == "day"
    risk_changes = result["changes"]["risk_flags"]
    assert "持仓集中度偏高" in risk_changes.get("added", [])
    assert "量比异常" in risk_changes.get("removed", [])


def test_review_window_returns_unavailable_when_no_entries_in_range(tmp_path, monkeypatch):
    """When all journal entries are older than the window, changes should be unavailable."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    old_payload = _mock_daily_payload()
    old_payload["meta"]["generated_at"] = "2025-01-01T16:00:00+08:00"
    build_review_report(
        sync_result=_mock_sync_result(),
        daily_payload=old_payload,
        window="day",
        save_journal=True,
    )

    result = build_review_report(
        sync_result=_mock_sync_result(),
        daily_payload=_mock_daily_payload(),
        window="day",
        save_journal=False,
    )

    assert result["changes"]["available"] is False


def test_review_report_sync_error_propagated(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    sync_result = {
        "record_count": 0,
        "errors": [{"code": "AKSHARE_SPOT_FAILED", "message": "timeout", "detail": {}}],
        "warnings": [],
    }

    result = build_review_report(
        sync_result=sync_result,
        daily_payload=_mock_daily_payload(),
        window="day",
        save_journal=False,
    )

    assert result["sync"]["ok"] is False
    assert len(result["errors"]) >= 1


def test_review_report_sync_error_skips_journal(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    sync_result = {
        "record_count": 0,
        "trade_date": "2026-06-08",
        "errors": [{"code": "AKSHARE_SPOT_FAILED", "message": "timeout", "detail": {}}],
        "warnings": [],
    }

    result = build_review_report(
        sync_result=sync_result,
        daily_payload=_mock_daily_payload(),
        window="day",
        save_journal=True,
    )

    assert result["journal_saved"] is False
    assert any(w["code"] == "REVIEW_JOURNAL_SKIPPED_SYNC_FAILED" for w in result["warnings"])
    assert result["journal_status"]["code"] == "sync_failed"
    assert not (tmp_path / "runtime" / "journal").exists()


def test_review_report_sync_skipped_status(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = build_review_report(
        sync_result={
            "record_count": 0,
            "trade_date": None,
            "summary": {"total": 0, "limit_up": 0, "stage_high": 0},
            "skipped": True,
            "errors": [],
            "warnings": [],
        },
        daily_payload=_mock_daily_payload(),
        window="day",
        save_journal=False,
    )

    assert result["sync"]["ok"] is True
    assert result["sync"]["status"] == "skipped"
    assert result["sync"]["skipped"] is True
    assert result["journal_status"]["code"] == "disabled"


def test_review_report_daily_error_propagated(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    daily_payload = {"ok": False, "command": "daily", "data": {}, "errors": [
        {"code": "MISSING_QUOTES", "message": "no quotes", "detail": {}}
    ]}

    result = build_review_report(
        sync_result=_mock_sync_result(),
        daily_payload=daily_payload,
        window="day",
        save_journal=True,
    )

    assert len(result["errors"]) >= 1
    assert result["journal_saved"] is False


def test_review_report_window_labels():
    assert _window_label("day") == "日级"
    assert _window_label("week") == "周级"
    assert _window_label("month") == "月级"


def test_review_report_no_trading_advice(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = build_review_report(
        sync_result=_mock_sync_result(),
        daily_payload=_mock_daily_payload(),
        window="day",
        save_journal=False,
    )

    result_str = json.dumps(result)
    forbidden = {"target_price", "position_size", "must_buy", "must_sell"}
    for key in forbidden:
        assert '"%s"' % key not in result_str


def test_review_next_commands_with_journal(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = build_review_report(
        sync_result=_mock_sync_result(),
        daily_payload=_mock_daily_payload(),
        window="day",
        save_journal=True,
    )

    assert any("journal show" in cmd for cmd in result["next_commands"])
    assert any("week" in cmd for cmd in result["next_commands"])


def test_review_command_queue_has_agent_execution_contract(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = build_review_report(
        sync_result=_mock_sync_result(),
        daily_payload=_mock_daily_payload(),
        window="day",
        save_journal=True,
    )

    week_item = next(
        item
        for item in result["command_queue"]
        if item["command"] == "market-intel review --window week --no-sync --no-save --text"
    )
    assert week_item["json_command"] == "market-intel review --window week --no-sync --no-save --json"
    assert week_item["state_effect"] == "read_only"
    assert week_item["mutates_state"] is False
    assert "data.command_queue" in week_item["read_fields"]
    assert week_item["done_when"]

    show_item = next(item for item in result["command_queue"] if "journal show" in item["command"])
    assert show_item["json_command"].endswith("--json")
    assert show_item["state_effect"] == "read_only"
    assert show_item["mutates_state"] is False
    assert "data.entry" in show_item["read_fields"]

    focus_item = next(item for item in result["command_queue"] if item["command"] == "market-intel focus --runtime --text")
    assert focus_item["json_command"] == "market-intel focus --runtime --json"
    assert focus_item["state_effect"] == "read_only"
    assert "data.first_runnable_command" in focus_item["read_fields"]


def test_review_next_commands_week_suggests_month(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    result = build_review_report(
        sync_result=_mock_sync_result(),
        daily_payload=_mock_daily_payload(),
        window="week",
        save_journal=False,
    )

    month_command = "market-intel review --window month --no-sync --no-save --text"
    assert month_command in result["next_commands"]
    month_item = next(item for item in result["command_queue"] if item["command"] == month_command)
    assert month_item["json_command"] == "market-intel review --window month --no-sync --no-save --json"
    assert month_item["state_effect"] == "read_only"


def test_handle_review_envelope(tmp_path, monkeypatch):
    """CLI handler wraps review in a proper envelope."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    from market_intel.cli import handle_review

    payload = handle_review(no_sync=True, no_save=True)

    assert payload["command"] == "review"
    assert "data" in payload
    assert payload["data"]["window"] == "day"


def test_render_review_text_error_shows_guidance(tmp_path, monkeypatch):
    """Text renderer shows clear guidance when runtime is missing."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    from market_intel.cli import handle_review
    from market_intel.core.text_report import render_review_text

    payload = handle_review(no_sync=True, no_save=True)
    text = render_review_text(payload)

    assert "market-intel review" in text
    assert "错误" in text
    assert "RUNTIME" in text
    assert "init runtime" in text
    assert "sync quotes" in text


def test_render_review_text_success(tmp_path, monkeypatch):
    """Text renderer produces full output with valid data."""
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    from market_intel.core.text_report import render_review_text

    payload = {
        "ok": True,
        "command": "review",
        "data": build_review_report(
            sync_result=_mock_sync_result(),
            daily_payload=_mock_daily_payload(),
            window="day",
            save_journal=False,
        ),
        "errors": [],
        "warnings": [],
    }
    text = render_review_text(payload)

    assert "market-intel review" in text
    assert "变化追踪" in text
    assert "数据同步" in text
    assert "今日摘要" in text
    assert "下一步" in text
    assert "#1" in text
    assert "读取" in text
    assert "market-intel review --window week --no-sync --no-save --text" in text
    assert "边界" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_render_review_text_sync_skipped(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    from market_intel.core.text_report import render_review_text

    payload = {
        "ok": True,
        "command": "review",
        "data": build_review_report(
            sync_result={
                "record_count": 0,
                "trade_date": None,
                "summary": {"total": 0, "limit_up": 0, "stage_high": 0},
                "skipped": True,
                "errors": [],
                "warnings": [],
            },
            daily_payload=_mock_daily_payload(),
            window="day",
            save_journal=False,
        ),
        "errors": [],
        "warnings": [],
    }

    text = render_review_text(payload)
    assert "已跳过" in text
    assert "数据同步" in text


def test_render_review_text_sample_runtime_journal_status(tmp_path, monkeypatch):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    from market_intel.core.text_report import render_review_text

    payload = {
        "ok": True,
        "command": "review",
        "data": build_review_report(
            sync_result=_mock_sync_result(),
            daily_payload=_mock_daily_payload(),
            window="day",
            save_journal=True,
            runtime_profile={"mode": "sample", "sample_datasets": ["quotes"]},
        ),
        "errors": [],
        "warnings": [],
    }

    text = render_review_text(payload)
    assert "日报留档" in text
    assert "样例数据" in text
    assert "未保存" in text
