import json
import subprocess

from market_intel.cli import (
    handle_import_holdings,
    handle_import_quotes,
    handle_journal_compare,
    handle_journal_latest,
    handle_journal_list,
    handle_journal_note,
    handle_journal_notes,
    handle_journal_save,
    handle_journal_show,
    handle_journal_timeline,
)
from market_intel.core.text_report import (
    render_journal_compare_text,
    render_journal_entry_text,
    render_journal_list_text,
    render_journal_notes_text,
    render_journal_timeline_text,
)


def import_runtime_examples(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)


def write_changed_quotes(tmp_path):
    path = tmp_path / "quotes.changed.csv"
    path.write_text(
        "\n".join(
            [
                "证券代码,证券名称,交易日期,最新价,涨跌幅,成交额,量比,换手率,振幅,涨停,阶段新高,日内回落",
                "002837,英维克,2026-06-07,39.10,9.8%,20.1亿,4.1,7.3%,10.2%,是,是,0.5%",
                "300499,高澜股份,2026-06-07,24.50,10.1%,15.0亿,3.8,8.1%,11.0%,是,是,0.4%",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def test_journal_save_list_latest_and_show(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)

    save_payload = handle_journal_save("ai-energy", use_runtime=True)
    list_payload = handle_journal_list(limit=5)
    latest_payload = handle_journal_latest()
    entry_id = latest_payload["data"]["entry"]["id"]
    show_payload = handle_journal_show(entry_id)

    assert save_payload["ok"] is True
    assert save_payload["data"]["saved"] is True
    assert save_payload["data"]["entry"]["trade_date"] == "2026-06-06"
    assert save_payload["data"]["entry"]["path"]
    assert list_payload["data"]["count"] == 1
    assert latest_payload["ok"] is True
    assert latest_payload["data"]["payload"]["command"] == "daily"
    assert latest_payload["data"]["payload"]["data"]["portfolio_review"]["items"]
    assert show_payload["ok"] is True
    assert show_payload["data"]["entry"]["id"] == entry_id


def test_journal_latest_when_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = handle_journal_latest()

    assert payload["ok"] is False
    assert payload["data"]["found"] is False
    assert payload["data"]["next_commands"]


def test_journal_note_attaches_to_latest_entry(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    saved = handle_journal_save("ai-energy", use_runtime=True)

    payload = handle_journal_note(section="market_structure", note_text="最强链路延续，组合集中在光通信，需要明天继续核对。")
    latest = handle_journal_latest()
    shown = handle_journal_show(saved["data"]["entry"]["id"])
    text = render_journal_entry_text(latest)

    assert payload["ok"] is True
    assert payload["command"] == "journal.note"
    assert payload["data"]["saved"] is True
    assert payload["data"]["entry"]["id"] == saved["data"]["entry"]["id"]
    assert payload["data"]["note"]["section"] == "market_structure"
    assert latest["data"]["notes"][0]["text"].startswith("最强链路")
    assert shown["data"]["notes"][0]["section"] == "market_structure"
    assert "复盘笔记" in text
    assert "光通信" in text


def test_journal_notes_lists_recent_notes(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    first = handle_journal_save("ai-energy", use_runtime=True)
    handle_journal_note(entry_id=first["data"]["entry"]["id"], section="market_structure", note_text="记录 CPO 集中暴露。")
    changed_quotes = write_changed_quotes(tmp_path)
    handle_import_quotes(str(changed_quotes), use_runtime=True)
    second = handle_journal_save("ai-energy", use_runtime=True)
    handle_journal_note(entry_id=second["data"]["entry"]["id"], section="current_change", note_text="记录观察项变化。")

    payload = handle_journal_notes(limit=5)
    section_payload = handle_journal_notes(limit=5, section="market_structure")
    query_payload = handle_journal_notes(limit=5, query="观察项")
    text = render_journal_notes_text(payload)
    section_text = render_journal_notes_text(section_payload)

    assert payload["ok"] is True
    assert payload["command"] == "journal.notes"
    assert payload["data"]["found"] is True
    assert payload["data"]["count"] == 2
    assert payload["data"]["notes"][0]["section"] == "current_change"
    assert payload["data"]["notes"][0]["entry_id"] == second["data"]["entry"]["id"]
    assert payload["data"]["notes"][1]["entry_id"] == first["data"]["entry"]["id"]
    assert payload["data"]["agent_contract"]["stable_fields"]
    assert section_payload["data"]["filters"]["section"] == "market_structure"
    assert section_payload["data"]["count"] == 1
    assert section_payload["data"]["notes"][0]["section"] == "market_structure"
    assert query_payload["data"]["filters"]["query"] == "观察项"
    assert query_payload["data"]["count"] == 1
    assert query_payload["data"]["notes"][0]["section"] == "current_change"
    assert "market-intel journal notes" in text
    assert "观察项变化" in text
    assert "筛选" in section_text


def test_journal_note_requires_text(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    handle_journal_save("ai-energy", use_runtime=True)

    payload = handle_journal_note()

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "JOURNAL_NOTE_TEXT_REQUIRED"


def test_journal_timeline_when_empty(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = handle_journal_timeline()
    text = render_journal_timeline_text(payload)

    assert payload["ok"] is True
    assert payload["command"] == "journal.timeline"
    assert payload["data"]["found"] is False
    assert payload["data"]["count"] == 0
    assert payload["data"]["can_compare"] is False
    assert payload["data"]["next_commands"]
    assert "market-intel journal timeline" in text
    assert "暂无日报留档" in text


def test_journal_save_requires_valid_daily(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = handle_journal_save("ai-energy", use_runtime=True)

    assert payload["ok"] is False
    assert payload["data"]["saved"] is False
    assert payload["errors"]


def test_journal_compare_latest_two_and_explicit_ids(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    first = handle_journal_save("ai-energy", use_runtime=True)
    changed_quotes = write_changed_quotes(tmp_path)
    handle_import_quotes(str(changed_quotes), use_runtime=True)
    second = handle_journal_save("ai-energy", use_runtime=True)

    compare_payload = handle_journal_compare()
    base_id = first["data"]["entry"]["id"]
    current_id = second["data"]["entry"]["id"]
    explicit_payload = handle_journal_compare(base_id=base_id, current_id=current_id)

    assert compare_payload["ok"] is True
    assert compare_payload["command"] == "journal.compare"
    assert compare_payload["data"]["found"] is True
    assert compare_payload["data"]["base_entry"]["id"] == base_id
    assert compare_payload["data"]["current_entry"]["id"] == current_id
    assert compare_payload["data"]["changes"]["trade_date"]["current"] == "2026-06-07"
    assert compare_payload["data"]["changes"]["watchlist"]["removed"]
    assert compare_payload["data"]["changes"]["watchlist"]["changed"]
    assert compare_payload["data"]["changes"]["portfolio_review"]["changed"]
    assert compare_payload["data"]["changes"]["portfolio_review"]["priority_counts"]["current"]
    assert compare_payload["data"]["changes"]["hotspots"]["current_count"] >= 1
    assert compare_payload["data"]["agent_contract"]["stable_fields"]
    assert "data.changes.portfolio_review" in compare_payload["data"]["agent_contract"]["stable_fields"]
    assert explicit_payload["ok"] is True
    assert explicit_payload["data"]["requested"]["base_id"] == base_id
    assert explicit_payload["data"]["requested"]["current_id"] == current_id


def test_journal_timeline_latest_entries(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    first = handle_journal_save("ai-energy", use_runtime=True)
    changed_quotes = write_changed_quotes(tmp_path)
    handle_import_quotes(str(changed_quotes), use_runtime=True)
    second = handle_journal_save("ai-energy", use_runtime=True)
    handle_journal_note(
        entry_id=second["data"]["entry"]["id"],
        section="current_change",
        note_text="观察项变化明显，继续核对液冷链路。",
    )

    payload = handle_journal_timeline(limit=5)
    text = render_journal_timeline_text(payload)
    first_id = first["data"]["entry"]["id"]
    second_id = second["data"]["entry"]["id"]

    assert payload["ok"] is True
    assert payload["data"]["found"] is True
    assert payload["data"]["can_compare"] is True
    assert payload["data"]["order"] == "oldest_to_newest"
    assert payload["data"]["count"] == 2
    assert [point["entry_id"] for point in payload["data"]["points"]] == [first_id, second_id]
    assert payload["data"]["points"][0]["portfolio_review"]["top_items"]
    assert payload["data"]["points"][1]["top_hotspot"]
    assert payload["data"]["points"][1]["note_count"] == 1
    assert payload["data"]["points"][1]["latest_note"]["section"] == "current_change"
    assert "data.points[].latest_note" in payload["data"]["agent_contract"]["stable_fields"]
    assert "笔记" in text
    assert "液冷链路" in text
    assert len(payload["data"]["transitions"]) == 1
    transition = payload["data"]["transitions"][0]
    assert transition["base_entry_id"] == first_id
    assert transition["current_entry_id"] == second_id
    assert transition["portfolio_review"]["changed_count"] >= 1
    assert transition["compare_command"].endswith("--json")
    assert "data.transitions[].portfolio_review" in payload["data"]["agent_contract"]["stable_fields"]


def test_journal_compare_requires_two_entries(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    handle_journal_save("ai-energy", use_runtime=True)

    payload = handle_journal_compare()

    assert payload["ok"] is False
    assert payload["data"]["found"] is False
    assert payload["errors"][0]["code"] == "JOURNAL_COMPARE_REQUIRES_TWO_ENTRIES"
    assert payload["data"]["next_commands"]


def test_journal_compare_requires_both_ids(monkeypatch, tmp_path):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))

    payload = handle_journal_compare(base_id="missing")

    assert payload["ok"] is False
    assert payload["errors"][0]["code"] == "JOURNAL_COMPARE_IDS_REQUIRED"


def test_journal_text_renderers(monkeypatch, tmp_path):
    import_runtime_examples(monkeypatch, tmp_path)
    handle_journal_save("ai-energy", use_runtime=True)
    changed_quotes = write_changed_quotes(tmp_path)
    handle_import_quotes(str(changed_quotes), use_runtime=True)
    handle_journal_save("ai-energy", use_runtime=True)

    list_text = render_journal_list_text(handle_journal_list())
    latest_text = render_journal_entry_text(handle_journal_latest())
    compare_text = render_journal_compare_text(handle_journal_compare())
    timeline_text = render_journal_timeline_text(handle_journal_timeline())

    assert "market-intel journal list" in list_text
    assert "market-intel journal entry" in latest_text
    assert "market-intel journal compare" in compare_text
    assert "market-intel journal timeline" in timeline_text
    assert "风险" in latest_text
    assert "观察项变化" in compare_text
    assert "持仓复核变化" in compare_text
    assert "时间线" in timeline_text
    assert "转折" in timeline_text
    assert "buy" not in latest_text.lower()
    assert "sell" not in latest_text.lower()
    assert "buy" not in compare_text.lower()
    assert "sell" not in compare_text.lower()
    assert "buy" not in timeline_text.lower()
    assert "sell" not in timeline_text.lower()


def test_journal_cli_smoke(monkeypatch, tmp_path, cli_cmd):
    monkeypatch.setenv("MARKET_INTEL_RUNTIME_DIR", str(tmp_path / "runtime"))
    handle_import_quotes("examples/quotes.csv.example", use_runtime=True)
    handle_import_holdings("examples/holdings.csv.example", use_runtime=True)

    save_result = subprocess.run(
        cli_cmd("journal", "save", "--runtime", "--json"),
        check=True,
        text=True,
        capture_output=True,
    )
    save_payload = json.loads(save_result.stdout)
    changed_quotes = write_changed_quotes(tmp_path)
    handle_import_quotes(str(changed_quotes), use_runtime=True)
    subprocess.run(
        cli_cmd("journal", "save", "--runtime", "--json"),
        check=True,
        text=True,
        capture_output=True,
    )
    list_result = subprocess.run(
        cli_cmd("journal", "list", "--text"),
        check=True,
        text=True,
        capture_output=True,
    )
    compare_result = subprocess.run(
        cli_cmd("journal", "compare", "--text"),
        check=True,
        text=True,
        capture_output=True,
    )
    note_result = subprocess.run(
        cli_cmd(
            "journal",
            "note",
            "--section",
            "current_change",
            "--text",
            "记录今日变化集中在观察项和持仓复核。",
        ),
        check=True,
        text=True,
        capture_output=True,
    )
    timeline_result = subprocess.run(
        cli_cmd("journal", "timeline", "--text"),
        check=True,
        text=True,
        capture_output=True,
    )
    notes_result = subprocess.run(
        cli_cmd("journal", "notes", "--section", "current_change", "--text"),
        check=True,
        text=True,
        capture_output=True,
    )

    assert save_payload["ok"] is True
    assert json.loads(note_result.stdout)["command"] == "journal.note"
    assert "market-intel journal list" in list_result.stdout
    assert "market-intel journal compare" in compare_result.stdout
    assert "market-intel journal timeline" in timeline_result.stdout
    assert "market-intel journal notes" in notes_result.stdout
    assert "筛选" in notes_result.stdout
