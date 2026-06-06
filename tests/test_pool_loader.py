from market_intel.core.normalize import find_pool_item
from market_intel.core.pool_loader import load_pool


def test_load_pool_contains_acceptance_samples():
    items = load_pool()
    by_symbol = {item.symbol: item for item in items if item.symbol}

    assert by_symbol["002837"].name == "英维克"
    assert by_symbol["002261"].name == "拓维信息"
    assert by_symbol["002281"].name == "光迅科技"
    assert by_symbol["300604"].name == "长川科技"
    assert by_symbol["603881"].name == "数据港"


def test_pool_item_exposures_are_merged():
    items = load_pool()

    guangxun = find_pool_item(items, "002281")
    assert guangxun is not None
    assert guangxun.primary_layer == "运力"
    assert {exposure.sub_sector for exposure in guangxun.exposures} == {"光模块", "CPO / 硅光"}
    assert "duplicate_symbol_exposure" in guangxun.data_quality_flags

    changchuan = find_pool_item(items, "300604")
    assert changchuan is not None
    assert {exposure.sub_sector for exposure in changchuan.exposures} == {
        "半导体设备",
        "存储测试与老化设备",
    }
    assert "duplicate_symbol_exposure" in changchuan.data_quality_flags


def test_column_shift_rows_are_recovered_when_possible():
    items = load_pool()
    hu_gui = find_pool_item(items, "688126")

    assert hu_gui is not None
    assert hu_gui.name == "沪硅产业"
    assert "column_shift_suspected" in hu_gui.data_quality_flags
    assert "invalid_symbol" in hu_gui.data_quality_flags


def test_non_security_rows_are_flagged_and_not_tradable():
    items = load_pool()
    non_security = [
        item
        for item in items
        if "non_security_row" in item.data_quality_flags and item.symbol is None
    ]

    assert non_security
    assert all(not item.tradable for item in non_security)

