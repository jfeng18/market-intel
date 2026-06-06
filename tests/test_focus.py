import json
import subprocess

from market_intel.cli import handle_focus
from market_intel.core.text_report import render_focus_text


def test_focus_mock_shape():
    payload = handle_focus("ai-energy", use_mock=True, top=4)
    data = payload["data"]

    assert payload["ok"] is True
    assert payload["command"] == "focus"
    assert data["headline"]
    assert data["data_status"]["state"] == "warning"
    assert data["market_focus"]["strongest_chain"]["sub_sector"] == "液冷"
    assert data["portfolio_pressure"]["repeated_exposure_count"] >= 1
    assert data["portfolio_pressure"]["repeated_exposures"][0]["symbols"]
    assert data["priority_securities"][0]["symbol"] == "300308"
    assert data["priority_securities"][0]["commands"][0] == "market-intel portfolio explain 300308 --mock --text"
    assert data["first_runnable_command"] == "market-intel portfolio review --mock --text"
    assert "data.priority_securities[].commands" in data["agent_contract"]["stable_fields"]


def test_focus_requires_source_has_text_guidance():
    payload = handle_focus("ai-energy", use_mock=False)
    text = render_focus_text(payload)

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "DAILY_SOURCE_REQUIRED"
    assert payload["data"]["data_status"]["state"] == "blocked"
    assert payload["data"]["data_status"]["command"] == "market-intel import schema --json"
    assert payload["data"]["next_steps"][0]["command"] == "market-intel import schema --json"
    assert "market-intel focus" in text
    assert "数据未就绪" in text
    assert "market-intel import schema --json" in text


def test_focus_text_renderer():
    payload = handle_focus("ai-energy", use_mock=True, top=3)
    text = render_focus_text(payload)

    assert "market-intel focus" in text
    assert "市场焦点" in text
    assert "组合压力" in text
    assert "优先标的" in text
    assert "300308 中际旭创" in text
    assert "先跑: market-intel portfolio review --mock --text" in text
    assert "buy" not in text.lower()
    assert "sell" not in text.lower()


def test_focus_cli_smoke(cli_cmd):
    text_result = subprocess.run(
        cli_cmd("focus", "--mock", "--top", "3", "--text"),
        check=True,
        text=True,
        capture_output=True,
    )
    json_result = subprocess.run(
        cli_cmd("focus", "--mock", "--top", "3", "--json"),
        check=True,
        text=True,
        capture_output=True,
    )

    assert "market-intel focus" in text_result.stdout
    assert "优先标的" in text_result.stdout
    assert json.loads(json_result.stdout)["command"] == "focus"


def test_focus_cli_text_error_is_human_readable(cli_cmd):
    result = subprocess.run(
        cli_cmd("focus", "--text"),
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    assert "market-intel focus" in result.stdout
    assert "数据未就绪" in result.stdout
    assert "DAILY_SOURCE_REQUIRED" in result.stdout
