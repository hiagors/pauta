"""Estabilidade do fingerprint (§7.3) — o que faz o silenciamento durar."""

import hashlib

from app.domain.services.fingerprint import FINGERPRINT_LENGTH, alert_fingerprint
from app.domain.value_objects.alert import AlertType
from tests.domain.conftest import uid

ALFA = uid(1)
ANA = uid(10)


def test_a_formula_e_a_do_spec() -> None:
    esperado = hashlib.sha256(f"MEMBER_CONFLICT|{ANA}|19".encode()).hexdigest()[:32]
    assert alert_fingerprint(AlertType.MEMBER_CONFLICT, ANA, 19) == esperado


def test_tem_trinta_e_dois_hex() -> None:
    fingerprint = alert_fingerprint(AlertType.MEMBER_IDLE, ANA, 20)
    assert len(fingerprint) == FINGERPRINT_LENGTH
    assert all(char in "0123456789abcdef" for char in fingerprint)


def test_e_deterministico() -> None:
    primeiro = alert_fingerprint(AlertType.SQUAD_OVERLOADED, ALFA, 19)
    segundo = alert_fingerprint(AlertType.SQUAD_OVERLOADED, ALFA, 19)
    assert primeiro == segundo


def test_muda_com_o_tipo() -> None:
    assert alert_fingerprint(AlertType.MEMBER_CONFLICT, ANA, 19) != alert_fingerprint(
        AlertType.MEMBER_IDLE, ANA, 19
    )


def test_muda_com_a_sprint() -> None:
    assert alert_fingerprint(AlertType.MEMBER_CONFLICT, ANA, 19) != alert_fingerprint(
        AlertType.MEMBER_CONFLICT, ANA, 20
    )


def test_muda_com_o_sujeito() -> None:
    assert alert_fingerprint(AlertType.MEMBER_CONFLICT, ANA, 19) != alert_fingerprint(
        AlertType.MEMBER_CONFLICT, uid(11), 19
    )


def test_o_sujeito_e_a_squad_nos_alertas_de_squad() -> None:
    """Nenhuma iniciativa entra no hash: o sujeito é o único eixo além da sprint."""
    assert alert_fingerprint(AlertType.EMPTY_SQUAD, ALFA, 21) == alert_fingerprint(
        AlertType.EMPTY_SQUAD, ALFA, 21
    )
