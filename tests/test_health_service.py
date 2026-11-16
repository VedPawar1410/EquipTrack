"""The health formula as a pure function: no database needed."""
from datetime import datetime, timedelta, timezone

import pytest

from app.schemas.analytics import HealthBand
from app.services.health_service import band_for, compute_health

NOW = datetime(2026, 11, 16, tzinfo=timezone.utc)
RECENT = NOW - timedelta(days=10)
FUTURE = NOW + timedelta(days=30)


@pytest.mark.parametrize("severities, last, next_, expected", [
    ([], RECENT, FUTURE, 100),                                   # healthy
    (["Low", "Low"], RECENT, FUTURE, 100),                       # low-severity issues cost nothing
    (["Medium"], RECENT, FUTURE, 90),
    (["High", "High"], RECENT, FUTURE, 60),
    (["Critical"], RECENT, FUTURE, 65),
    ([], NOW - timedelta(days=200), FUTURE, 85),                 # stale: > 6 months
    ([], None, None, 85),                                        # never maintained counts as stale
    ([], RECENT, NOW - timedelta(days=3), 80),                   # overdue
    (["Critical", "Critical", "Critical"], None, NOW - timedelta(days=1), 0),   # floored at 0, not negative
])
def test_score(severities, last, next_, expected):
    assert compute_health(severities, last, next_, NOW).score == expected


def test_deductions_explain_the_score():
    health = compute_health(["High", "High", "Medium"], NOW - timedelta(days=400), NOW - timedelta(days=2), NOW)
    reasons = {d.reason: d.points for d in health.deductions}
    assert reasons == {"2 open High issue(s)": 40, "1 open Medium issue(s)": 10,
                       "Last maintenance 400 days ago": 15, "Scheduled maintenance overdue by 2 day(s)": 20}
    assert health.score == 100 - sum(reasons.values()) == 15


@pytest.mark.parametrize("score, band", [(100, HealthBand.GOOD), (80, HealthBand.GOOD), (79, HealthBand.FAIR),
                                         (50, HealthBand.FAIR), (49, HealthBand.POOR), (0, HealthBand.POOR)])
def test_bands(score, band):
    assert band_for(score) == band
