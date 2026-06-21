from datetime import date, timedelta
from typing import Dict, Optional


CN_A_SHARE_CLOSED_DATES = {
    "2026-01-01": "new_year",
    "2026-01-02": "new_year",
    "2026-01-03": "new_year",
    "2026-02-15": "spring_festival",
    "2026-02-16": "spring_festival",
    "2026-02-17": "spring_festival",
    "2026-02-18": "spring_festival",
    "2026-02-19": "spring_festival",
    "2026-02-20": "spring_festival",
    "2026-02-21": "spring_festival",
    "2026-02-22": "spring_festival",
    "2026-02-23": "spring_festival",
    "2026-04-04": "qingming_festival",
    "2026-04-05": "qingming_festival",
    "2026-04-06": "qingming_festival",
    "2026-05-01": "labor_day",
    "2026-05-02": "labor_day",
    "2026-05-03": "labor_day",
    "2026-05-04": "labor_day",
    "2026-05-05": "labor_day",
    "2026-06-19": "dragon_boat_festival",
    "2026-06-20": "dragon_boat_festival",
    "2026-06-21": "dragon_boat_festival",
    "2026-09-25": "mid_autumn_festival",
    "2026-09-26": "mid_autumn_festival",
    "2026-09-27": "mid_autumn_festival",
    "2026-10-01": "national_day",
    "2026-10-02": "national_day",
    "2026-10-03": "national_day",
    "2026-10-04": "national_day",
    "2026-10-05": "national_day",
    "2026-10-06": "national_day",
    "2026-10-07": "national_day",
}


def calendar_status(day: date) -> Dict[str, object]:
    is_weekend = day.weekday() >= 5
    holiday_code = CN_A_SHARE_CLOSED_DATES.get(day.isoformat())
    is_closed = is_weekend or bool(holiday_code)
    return {
        "date": day.isoformat(),
        "market": "cn_a_share",
        "is_trading_day": not is_closed,
        "reason_code": holiday_code or ("weekend" if is_weekend else "weekday"),
        "reason": "交易所假日休市" if holiday_code else ("周末休市" if is_weekend else "工作日，按交易日处理"),
        "previous_expected_trade_date": previous_expected_trade_date(day).isoformat(),
    }


def previous_expected_trade_date(day: date) -> date:
    cursor = day - timedelta(days=1)
    while cursor.weekday() >= 5 or cursor.isoformat() in CN_A_SHARE_CLOSED_DATES:
        cursor -= timedelta(days=1)
    return cursor


def freshness_state(
    latest_trade_date: Optional[date],
    today: date,
    max_quote_age_days: int,
    provider_failed_using_cache: bool = False,
) -> Dict[str, object]:
    cal = calendar_status(today)
    if latest_trade_date is None:
        return {
            "state": "missing",
            "reason_code": "missing_trade_date",
            "calendar_status": cal,
            "quote_age_days": None,
            "degrades_review_confidence": True,
            "summary": "行情缺少 trade_date；先修复或刷新 quotes。",
        }

    age_days = (today - latest_trade_date).days
    expected_previous = previous_expected_trade_date(today)
    if age_days < 0:
        return {
            "state": "future_date",
            "reason_code": "quote_date_in_future",
            "calendar_status": cal,
            "quote_age_days": age_days,
            "degrades_review_confidence": True,
            "summary": "行情日期晚于当前日期；请核对 trade_date。",
        }
    if provider_failed_using_cache:
        return {
            "state": "provider_failed_using_cache",
            "reason_code": "provider_failed_using_cache",
            "calendar_status": cal,
            "quote_age_days": age_days,
            "degrades_review_confidence": True,
            "summary": "行情 provider 曾失败，当前使用缓存行情；可复盘，但全市场结论需降级。",
        }
    if not cal["is_trading_day"] and latest_trade_date >= expected_previous:
        return {
            "state": "market_closed_expected_stale",
            "reason_code": "non_trading_day_expected_stale",
            "calendar_status": cal,
            "quote_age_days": age_days,
            "degrades_review_confidence": False,
            "summary": "今天是非交易日；使用最新交易日 %s。适合复盘，不适合盘中判断。" % latest_trade_date.isoformat(),
        }
    if age_days <= max_quote_age_days:
        return {
            "state": "fresh",
            "reason_code": "within_threshold",
            "calendar_status": cal,
            "quote_age_days": age_days,
            "degrades_review_confidence": False,
            "summary": "行情日期在阈值内，可用于复盘。",
        }
    return {
        "state": "stale_on_trading_day" if cal["is_trading_day"] else "stale_after_market_close",
        "reason_code": "trading_day_stale" if cal["is_trading_day"] else "non_trading_day_stale",
        "calendar_status": cal,
        "quote_age_days": age_days,
        "degrades_review_confidence": True,
        "summary": "行情日期过旧；先刷新 quotes 后再解读全市场结论。",
    }
