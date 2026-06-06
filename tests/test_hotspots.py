from market_intel.cli import handle_hotspots
from market_intel.core.fixtures import load_mock_quotes
from market_intel.core.pool_loader import load_pool
from market_intel.core.scoring import calculate_hotspots


def test_mock_hotspots_return_ranked_breakdown():
    hotspots = calculate_hotspots(load_pool(), load_mock_quotes(), top=5)

    assert hotspots
    assert hotspots[0].score >= hotspots[-1].score
    assert 0 <= hotspots[0].score <= 100
    assert set(hotspots[0].score_breakdown) == {
        "avg_change_score",
        "turnover_expansion_score",
        "strong_member_score",
        "leader_strength_score",
        "persistence_score",
        "intraday_fade_penalty",
    }
    assert hotspots[0].signals
    assert hotspots[0].risks


def test_hotspots_cli_requires_mock():
    payload = handle_hotspots("ai-energy", use_mock=False)

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "QUOTE_SOURCE_REQUIRED"


def test_hotspots_cli_mock_shape():
    payload = handle_hotspots("ai-energy", use_mock=True, top=3)

    assert payload["ok"] is True
    assert payload["command"] == "hotspots"
    assert payload["data"]["mode"] == "mock"
    assert payload["data"]["count"] == 3
    assert payload["data"]["hotspots"][0]["score_breakdown"]
