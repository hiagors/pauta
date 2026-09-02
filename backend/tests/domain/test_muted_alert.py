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


def test_created_at_vem_do_clock_em_utc() -> None:
    mute = make()
    assert mute.created_at == datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def test_motivo_e_obrigatorio() -> None:
    with pytest.raises(MuteReasonRequired):
        make(reason="   ")


def test_motivo_e_normalizado() -> None:
    assert make(reason="  porque sim  ").reason == "porque sim"


def test_datetime_sem_timezone_e_recusado() -> None:
    with pytest.raises(InvalidTimestamp):
        MutedAlert(
            id=uid(1),
            alert_type=AlertType.MEMBER_CONFLICT,
            fingerprint="a" * 32,
            reason="motivo",
            created_at=datetime(2026, 9, 2, 12, 0),  # noqa: DTZ001
        )


def test_datetime_em_outro_fuso_e_convertido_para_utc() -> None:
    mute = MutedAlert(
        id=uid(1),
        alert_type=AlertType.MEMBER_CONFLICT,
        fingerprint="a" * 32,
        reason="motivo",
        created_at=datetime(2026, 9, 2, 9, 0, tzinfo=timezone(timedelta(hours=-3))),
    )
    assert mute.created_at == datetime(2026, 9, 2, 12, 0, tzinfo=UTC)
