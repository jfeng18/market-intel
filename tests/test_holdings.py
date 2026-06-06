from market_intel.cli import handle_holdings_impact
from market_intel.core.fixtures import load_mock_holdings
from market_intel.core.holdings import calculate_holding_impacts
from market_intel.core.pool_loader import load_pool


def test_mock_holdings_identify_repeated_exposure():
    data = calculate_holding_impacts(load_pool(), load_mock_holdings())

    assert data["holding_count"] == 5
    assert "theme_concentration" in data["risk_flags"]
    assert data["repeated_exposures"] or data["repeated_overlap_groups"]
    symbols = {impact["holding_symbol"] for impact in data["impacts"]}
    assert {"002261", "002281", "300308", "300604", "603881"} == symbols


def test_holdings_impact_cli_requires_mock():
    payload = handle_holdings_impact("ai-energy", use_mock=False)

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "HOLDINGS_SOURCE_REQUIRED"


def test_holdings_impact_cli_mock_shape():
    payload = handle_holdings_impact("ai-energy", use_mock=True)

    assert payload["ok"] is True
    assert payload["command"] == "holdings.impact"
    assert payload["data"]["mode"] == "mock"
    assert payload["data"]["holding_count"] == 5
    assert payload["data"]["impacts"][0]["impact"]["risk_flags"] is not None
