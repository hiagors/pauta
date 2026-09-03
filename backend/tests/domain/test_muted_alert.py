"""Silenciamento (§6.9)."""

from datetime import UTC, date, datetime, timedelta, timezone

import pytest

from app.domain.entities.muted_alert import MutedAlert
from app.domain.errors import InvalidTimestamp, MuteReasonRequired
from app.domain.value_objects.alert import AlertType
from tests.domain.conftest import FrozenClock, uid


def make(reason: str = "Conflito conhecido e intencional.") -> MutedAlert:
    return MutedAlert.create(
        alert_type=AlertType.MEMBER_CONFLICT,
        fingerprint="a" * 32,
        reason=reason,
        clock=FrozenClock(date(2026, 9, 2)),
        id=uid(1),
    )


def test_created_at_comes_from_the_clock_in_utc() -> None:
    mute = make()
    assert mute.created_at == datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def test_the_reason_is_required() -> None:
    with pytest.raises(MuteReasonRequired):
        make(reason="   ")


def test_the_reason_is_normalized() -> None:
    assert make(reason="  porque sim  ").reason == "porque sim"


def test_a_naive_datetime_is_refused() -> None:
    with pytest.raises(InvalidTimestamp):
        MutedAlert(
            id=uid(1),
            alert_type=AlertType.MEMBER_CONFLICT,
            fingerprint="a" * 32,
            reason="motivo",
            created_at=datetime(2026, 9, 2, 12, 0),  # noqa: DTZ001
        )


def test_a_datetime_in_another_timezone_is_converted_to_utc() -> None:
    mute = MutedAlert(
        id=uid(1),
        alert_type=AlertType.MEMBER_CONFLICT,
        fingerprint="a" * 32,
        reason="motivo",
        created_at=datetime(2026, 9, 2, 9, 0, tzinfo=timezone(timedelta(hours=-3))),
    )
    assert mute.created_at == datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
