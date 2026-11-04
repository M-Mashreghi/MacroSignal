"""Event clusters, overlap and statistical event study (Task 4.14)."""

from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import numpy as np
import pytest

from macrosignal.calendar.trading import UsTradingCalendar
from macrosignal.domain import AvailabilityPrecision
from macrosignal.event_study.alignment import align_timestamp
from macrosignal.event_study.statistics import (
    EventResponse,
    EventStudySettings,
    SurpriseBuckets,
    contamination_map,
    detect_clusters,
    event_study,
)

NY = ZoneInfo("America/New_York")
CAL = UsTradingCalendar()


def _al(rid: str, fam: str, at: datetime):  # type: ignore[no-untyped-def]
    return align_timestamp(
        release_id=rid,
        release_family=fam,
        release_stage=None,
        event_time=at,
        precision=AvailabilityPrecision.EXACT_TIMESTAMP,
        calendar=CAL,
    )


def test_same_session_releases_are_contaminated() -> None:
    als = [
        _al("CPI-1", "CPI", datetime(2026, 10, 15, 8, 30, tzinfo=NY)),
        _al("RS-1", "RETAIL", datetime(2026, 10, 15, 8, 30, tzinfo=NY)),
        _al("PPI-1", "PPI", datetime(2026, 10, 20, 8, 30, tzinfo=NY)),
        _al("FOMC-1", "FOMC_STATEMENT", datetime(2026, 10, 28, 14, 0, tzinfo=NY)),
    ]
    clusters = detect_clusters(als, CAL)
    assert [c.release_ids for c in clusters] == [("CPI-1", "RS-1"), ("PPI-1",), ("FOMC-1",)]
    cm = contamination_map(clusters)
    assert cm == {"CPI-1": True, "RS-1": True, "PPI-1": False, "FOMC-1": False}
    assert clusters[0].families == ("CPI", "RETAIL")


def test_post_close_event_overlaps_next_morning() -> None:
    als = [
        _al("A", "X", datetime(2026, 10, 14, 16, 30, tzinfo=NY)),
        _al("B", "Y", datetime(2026, 10, 15, 8, 30, tzinfo=NY)),
    ]
    assert detect_clusters(als, CAL)[0].contaminated
    gap = [
        _al("A", "X", datetime(2026, 10, 15, 8, 30, tzinfo=NY)),
        _al("B", "Y", datetime(2026, 10, 16, 8, 30, tzinfo=NY)),
    ]
    assert len(detect_clusters(gap, CAL)) == 2
    assert len(detect_clusters(gap, CAL, max_session_gap=1)) == 1


def _responses() -> list[EventResponse]:
    rng = np.random.default_rng(1)
    out = []
    for i in range(40):
        z = (-1.0 if i % 2 else 1.0) * (1 + i / 40)
        out.append(
            EventResponse(
                release_id=f"CPI-{i}",
                release_family="CPI",
                window_return=float(-0.004 * np.sign(z) + rng.normal(0, 0.002)),
                surprise_z=z,
                regime="growth_inflation" if i < 20 else "slowdown_inflation",
                contaminated=i in (0, 1),
            )
        )
    out.append(
        EventResponse(release_id="CPI-x", release_family="CPI", window_return=0.01, surprise_z=None)
    )
    return out


def test_grouped_statistics_with_bootstrap_ci() -> None:
    res = {
        tuple(g.key.values()): g
        for g in event_study(_responses(), EventStudySettings(min_sample=5))
    }
    pos, neg = res[("CPI", "positive")], res[("CPI", "negative")]
    assert pos.n == 19 and pos.n_contaminated_excluded == 1
    assert pos.mean is not None and pos.mean < 0 and neg.mean is not None and neg.mean > 0
    assert (
        pos.ci_low is not None and pos.ci_high is not None and pos.ci_low < pos.mean < pos.ci_high
    )
    assert pos.ci_high < 0  # significant negative response to positive inflation surprises
    missing = res[("CPI", "missing")]
    assert missing.n == 1 and missing.small_sample and missing.ci_low is None
    again = {
        tuple(g.key.values()): g
        for g in event_study(_responses(), EventStudySettings(min_sample=5))
    }
    assert again[("CPI", "positive")].ci_low == pos.ci_low  # deterministic seed


def test_regime_grouping_and_contamination_toggle() -> None:
    settings = EventStudySettings(
        group_by=("release_family", "regime"), min_sample=5, exclude_contaminated=False
    )
    res = {g.key["regime"]: g for g in event_study(_responses(), settings)}
    assert res["growth_inflation"].n == 20 and res["growth_inflation"].n_contaminated_excluded == 0
    with pytest.raises(ValueError, match="unsupported grouping"):
        event_study(_responses(), EventStudySettings(group_by=("asset",)))


def test_bucket_rules() -> None:
    b = SurpriseBuckets(negative_below=-1, positive_above=1)
    assert [b.bucket(z) for z in (-2, 0, 2, None)] == ["negative", "neutral", "positive", "missing"]
    assert date(2026, 1, 1).year == 2026
