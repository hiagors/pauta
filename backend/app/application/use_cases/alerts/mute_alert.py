"""Silenciar um alerta (`POST /alerts/mute`, §7.3).

Silenciar exige motivo em texto e é reversível. O `fingerprint` vem calculado
pelo domínio, ancorado no sujeito do alerta e na sprint — nunca nas iniciativas
envolvidas —, e é por isso que entrar um terceiro projeto na mesma sprint não
desfaz o silenciamento (cenário G do §13.1).

O use case **não** recalcula o fingerprint: ele grava o que o alerta trouxe.
Silenciar algo que não existe mais é inofensivo, e exigir que o alerta ainda
esteja de pé abriria uma corrida entre a tela e o clique.
"""

from dataclasses import dataclass

from app.application.dto.alerts import MuteAlertInput, MutedAlertView
from app.domain.entities.muted_alert import MutedAlert
from app.domain.errors import AlertAlreadyMuted
from app.domain.ports.clock import Clock
from app.domain.ports.repositories import MutedAlertRepository


@dataclass(frozen=True)
class MuteAlert:
    muted_alerts: MutedAlertRepository
    clock: Clock

    def execute(self, data: MuteAlertInput) -> MutedAlertView:
        if self.muted_alerts.get_by_fingerprint(data.fingerprint) is not None:
            raise AlertAlreadyMuted(data.fingerprint)
        mute = MutedAlert.create(
            alert_type=data.alert_type,
            fingerprint=data.fingerprint,
            reason=data.reason,
            clock=self.clock,
        )
        self.muted_alerts.add(mute)
        return MutedAlertView.of(mute)
