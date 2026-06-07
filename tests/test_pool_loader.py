import pytest

from market_intel.core.normalize import find_pool_item, normalize_row
from market_intel.core.pool_loader import list_pools, load_pool


def test_load_pool_contains_acceptance_samples():
    items = load_pool()
    by_symbol = {item.symbol: item for item in items if item.symbol}

    assert by_symbol["002837"].name == "英维克"
    assert by_symbol["002261"].name == "拓维信息"
    assert by_symbol["002281"].name == "光迅科技"
    assert by_symbol["300604"].name == "长川科技"
    assert by_symbol["603881"].name == "数据港"


def test_all_a_pool_is_supported_as_seed_universe():
    items = load_pool("all-a")
    pools = {item["id"]: item for item in list_pools()}
    by_symbol = {item.symbol: item for item in items if item.symbol}

    assert "all-a" in pools
    assert pools["all-a"]["scope"] == "all_a_seed"
    assert by_symbol["002837"].name == "英维克"
    assert by_symbol["002837"].raw["pool"] == "all-a"
    assert by_symbol["002837"].raw["pool_scope"] == "all_a_seed"


def test_load_pool_can_overlay_extra_pool_paths(monkeypatch, tmp_path):
    extra_pool = tmp_path / "pool_expansion.csv"
    extra_pool.write_text(
        "status,priority,section,level,company,code,desc,notes\n"
        "candidate,P2,银行 / 银行,待确认,平安银行,000001,持仓补充样例,source=test\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_POOL_EXTRA_PATHS", str(extra_pool))

    items = load_pool("all-a")
    pingan = find_pool_item(items, "000001")
    existing = find_pool_item(items, "002837")

    assert existing is not None
    assert pingan is not None
    assert pingan.name == "平安银行"
    assert pingan.raw["pool_source"] == "extra:pool_expansion.csv"
    assert pingan.raw["pool_source_file"] == "pool_expansion.csv"
    assert str(extra_pool) not in str(pingan.to_dict())
    assert pingan.raw["pool"] == "all-a"
    assert pingan.raw["pool_scope"] == "all_a_seed"


def test_explicit_pool_path_ignores_extra_pool_paths(monkeypatch, tmp_path):
    base_pool = tmp_path / "base.csv"
    extra_pool = tmp_path / "extra.csv"
    base_pool.write_text(
        "status,priority,section,level,company,code,desc,notes\n"
        "pending,P2,测试 / 基础,待确认,基础公司,000002,基础池样例,\n",
        encoding="utf-8",
    )
    extra_pool.write_text(
        "status,priority,section,level,company,code,desc,notes\n"
        "candidate,P2,测试 / 额外,待确认,额外公司,000003,额外池样例,\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_POOL_EXTRA_PATHS", str(extra_pool))

    items = load_pool("all-a", path=base_pool)

    assert find_pool_item(items, "000002") is not None
    assert find_pool_item(items, "000003") is None


def test_load_pool_can_overlay_a_share_universe(monkeypatch, tmp_path):
    universe_file = tmp_path / "a_share_universe.csv"
    universe_file.write_text(
        "证券代码,证券名称,行业,概念,指数成分,上市状态\n"
        "000001,平安银行,银行,股份行;金融科技,沪深300;深证100,listed\n"
        "600519,贵州茅台,食品饮料,白酒;消费,上证50;沪深300,listed\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    items = load_pool("all-a")
    pingan = find_pool_item(items, "000001")
    maotai = find_pool_item(items, "600519")

    assert pingan is not None
    assert pingan.name == "平安银行"
    assert pingan.primary_layer == "行业"
    assert pingan.primary_sub_sector == "银行"
    assert pingan.raw["pool_source"] == "universe:a_share_universe.csv"
    assert pingan.raw["pool_source_file"] == "a_share_universe.csv"
    assert pingan.raw["universe_schema"] == "a_share_universe_v1"
    assert pingan.raw["universe_industry"] == "银行"
    assert pingan.raw["universe_concepts"] == "股份行;金融科技"
    assert str(universe_file) not in str(pingan.to_dict())
    assert maotai is not None
    assert maotai.primary_sub_sector == "食品饮料"


def test_a_share_universe_metadata_survives_existing_seed_merge(monkeypatch, tmp_path):
    universe_file = tmp_path / "a_share_universe.csv"
    universe_file.write_text(
        "symbol,name,industry,concepts,index_membership,listing_status\n"
        "002837,英维克,机械设备,液冷;数据中心,中证1000,listed\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_A_SHARE_UNIVERSE_PATHS", str(universe_file))

    items = load_pool("all-a")
    item = find_pool_item(items, "002837")

    assert item is not None
    assert item.primary_layer == "电力"
    assert item.raw["universe_schema"] == "a_share_universe_v1"
    assert item.raw["universe_industry"] == "机械设备"
    assert "universe:a_share_universe.csv" in item.raw["merged_pool_sources"]


def test_research_notes_accept_common_a_share_symbol_formats(monkeypatch, tmp_path):
    research_file = tmp_path / "research_notes.csv"
    research_file.write_text(
        "symbol,name,status,thesis,evidence,invalidation,updated_at,source\n"
        "300308.SZ,中际旭创,reviewed,光模块龙头,订单和业绩验证,海外资本开支下修,2026-06-07,test\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MARKET_INTEL_RESEARCH_NOTES_PATHS", str(research_file))

    items = load_pool("all-a")
    item = find_pool_item(items, "300308")

    assert item is not None
    assert item.raw["research_schema"] == "research_notes_v1"
    assert item.raw["research_status"] == "reviewed"
    assert item.raw["research_note"]["symbol"] == "300308"
    assert item.raw["research_thesis"] == "光模块龙头"


def test_unknown_pool_lists_supported_pools():
    with pytest.raises(ValueError) as exc:
        load_pool("unknown")

    assert "Unsupported pool: unknown" in str(exc.value)
    assert "all-a" in str(exc.value)
    assert "ai-energy" in str(exc.value)


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


def test_pending_marker_rows_do_not_recover_symbol_from_desc():
    item = normalize_row(
        {
            "status": "pending",
            "priority": "P2",
            "section": "1.1 AI 算力芯片（GPU / AI 加速器）",
            "level": "🇨🇳 中国梯队",
            "company": "摩尔线程",
            "code": "科创板",
            "desc": "国产 GPGPU 第二梯队 | 展示 256GPU 超节点",
            "notes": "",
        },
        raw_row=8,
    )

    assert item.symbol is None
    assert item.instrument_type == "pending_listing"
    assert item.tradable is False
    assert "pending_listing" in item.data_quality_flags
    assert "column_shift_suspected" not in item.data_quality_flags
