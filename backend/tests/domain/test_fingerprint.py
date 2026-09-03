"""Estabilidade do fingerprint (§7.3) — o que faz o silenciamento durar."""

import hashlib

from app.domain.services.fingerprint import FINGERPRINT_LENGTH, alert_fingerprint
from app.domain.value_objects.alert import AlertType
from tests.domain.conftest import uid

ALFA = uid(1)
ANA = uid(10)


def test_the_formula_is_the_one_in_the_spec() -> None:
    expected = hashlib.sha256(f"MEMBER_CONFLICT|{ANA}|19".encode()).hexdigest()[:32]
    assert alert_fingerprint(AlertType.MEMBER_CONFLICT, ANA, 19) == expected


def test_it_is_thirty_two_hex_characters() -> None:
    fingerprint = alert_fingerprint(AlertType.MEMBER_IDLE, ANA, 20)
    assert len(fingerprint) == FINGERPRINT_LENGTH
    assert all(char in "0123456789abcdef" for char in fingerprint)


def test_it_is_deterministic() -> None:
    first = alert_fingerprint(AlertType.SQUAD_OVERLOADED, ALFA, 19)
    second = alert_fingerprint(AlertType.SQUAD_OVERLOADED, ALFA, 19)
    assert first == second


def test_it_changes_with_the_alert_type() -> None:
    assert alert_fingerprint(AlertType.MEMBER_CONFLICT, ANA, 19) != alert_fingerprint(
        AlertType.MEMBER_IDLE, ANA, 19
    )


def test_it_changes_with_the_sprint() -> None:
    assert alert_fingerprint(AlertType.MEMBER_CONFLICT, ANA, 19) != alert_fingerprint(
        AlertType.MEMBER_CONFLICT, ANA, 20
    )


def test_it_changes_with_the_subject() -> None:
    assert alert_fingerprint(AlertType.MEMBER_CONFLICT, ANA, 19) != alert_fingerprint(
        AlertType.MEMBER_CONFLICT, uid(11), 19
    )


def test_the_subject_of_a_squad_alert_is_the_squad() -> None:
    """Nenhuma iniciativa entra no hash: o sujeito é o único eixo além da sprint."""
    assert alert_fingerprint(AlertType.EMPTY_SQUAD, ALFA, 21) == alert_fingerprint(
        AlertType.EMPTY_SQUAD, ALFA, 21
    )
