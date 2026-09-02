"""Fingerprint estável de alerta (§7.3).

Ancorado no **sujeito** do alerta (a squad ou o membro) e na sprint. As
iniciativas envolvidas **não** entram no hash: se entrassem, um terceiro
projeto caindo na mesma sprint mudaria o hash e desfaria o silenciamento —
exatamente o que o silenciamento existe para evitar (cenário G do §13.1).
"""

import hashlib
from uuid import UUID

from app.domain.value_objects.alert import AlertType

#: Tamanho do prefixo do sha256 guardado. 32 hex = 128 bits, colisão irrelevante
#: para a escala do sistema e legível no JSON do snapshot.
FINGERPRINT_LENGTH = 32


def alert_fingerprint(
    alert_type: AlertType, subject_id: UUID, sprint_number: int
) -> str:
    """`sha256("TIPO|uuid-do-sujeito|numero-da-sprint")`, truncado em 32 hex.

    As três partes são estáveis por construção: `alert_type.value` é a string
    do enum, `str(UUID)` é a forma canônica minúscula com hífens e
    `sprint_number` é inteiro.
    """
    raw = f"{alert_type.value}|{subject_id}|{sprint_number}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:FINGERPRINT_LENGTH]
