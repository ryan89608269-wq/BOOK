from datetime import datetime, timezone

import pytest

from public_review import business_date, dry_run_days, scheduled_at


def test_taipei_1907_is_utc_1107():
    assert scheduled_at(datetime(2026, 10, 15).date())["utc"] == "2026-10-15T11:07:00+00:00"


def test_delayed_run_stays_on_prior_business_day_until_1907():
    assert business_date(datetime(2026, 10, 15, 10, 0, tzinfo=timezone.utc)).isoformat() == "2026-10-14"
    assert business_date(datetime(2026, 10, 15, 11, 8, tzinfo=timezone.utc)).isoformat() == "2026-10-15"


def test_manual_backfill_is_deterministic_and_read_only():
    now = datetime(2026, 10, 15, 11, 8, tzinfo=timezone.utc)
    first = dry_run_days(now, target_date="2026-10-15", since_date="2026-10-14")
    assert first == dry_run_days(now, target_date="2026-10-15", since_date="2026-10-14")
    assert [row["date"] for row in first["days"]] == ["2026-10-14", "2026-10-15"]
    assert first["remote_writes"] == 0 and first["scope"] == "synthetic-public-fixture"


def test_future_date_rejected():
    now = datetime(2026, 10, 15, 11, 8, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="future"):
        dry_run_days(now, target_date="2026-10-16")


def test_backfill_over_31_days_rejected():
    now = datetime(2026, 10, 15, 11, 8, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="31 days"):
        dry_run_days(now, target_date="2026-10-15", since_date="2026-09-01")
