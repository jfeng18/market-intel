from market_intel.cli import handle_holdings_impact
from market_intel.core.fixtures import load_mock_holdings
from market_intel.core.holdings import calculate_holding_impacts
from market_intel.core.models import Exposure, Holding, PoolItem
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


def test_repeated_exposures_count_distinct_holdings():
    item = PoolItem(
        symbol="688008",
        name="测试持仓",
        market="CN_A",
        instrument_type="security",
        priority="P2",
        tradable=True,
        primary_layer="存力",
        primary_sub_sector="存储接口芯片 / CXL",
        primary_role="核心",
        logic="测试",
        exposures=[
            Exposure(
                layer="存力",
                sub_sector="存储接口芯片 / CXL",
                section="3.4 存储接口芯片 / CXL",
                role="核心",
                priority="P2",
                logic="测试 A",
                raw_row=1,
            ),
            Exposure(
                layer="存力",
                sub_sector="存储接口芯片 / CXL",
                section="3.4 存储接口芯片 / CXL",
                role="核心",
                priority="P2",
                logic="测试 B",
                raw_row=2,
            ),
        ],
    )

    data = calculate_holding_impacts([item], [Holding(symbol="688008", name="测试持仓")])

    assert data["holding_count"] == 1
    assert data["repeated_exposures"] == []
    assert "theme_concentration" not in data["risk_flags"]


def test_unmatched_holding_copy_is_pool_neutral():
    data = calculate_holding_impacts([], [Holding(symbol="000001", name="测试")])
    impact = data["impacts"][0]

    assert impact["matched_pool_item"] is False
    assert "当前复盘池" in impact["explain"]
    assert "AI 能量池" not in impact["explain"]
