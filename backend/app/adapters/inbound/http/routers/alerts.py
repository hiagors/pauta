"""`/alerts` e o silenciamento (§7.3, §8)."""

from uuid import UUID

from fastapi import APIRouter, status

from app.adapters.inbound.http.deps import PortsDep
from app.adapters.inbound.http.schemas.alerts import (
    AlertsOut,
    MuteAlertIn,
    MutedAlertOut,
)
from app.application.dto.alerts import AlertsQuery
from app.application.use_cases.alerts.list_alerts import ListAlerts
from app.application.use_cases.alerts.mute_alert import MuteAlert
from app.application.use_cases.alerts.unmute_alert import UnmuteAlert

router = APIRouter(prefix="/alerts", tags=["alertas"])


@router.get("", summary="Lista alertas")
def list_alerts(
    ports: PortsDep,
    sprint_from: int | None = None,
    sprint_to: int | None = None,
    include_muted: bool = False,
) -> AlertsOut:
    """Sem intervalo, a janela é da sprint atual (RN12) até a última
    cadastrada. Os silenciados saem da lista mas continuam contados em
    `muted_count`, que é o contador expansível do painel."""
    query = AlertsQuery(
        sprint_from=sprint_from, sprint_to=sprint_to, include_muted=include_muted
    )
    return AlertsOut.model_validate(ports.use_case(ListAlerts).execute(query))


@router.post("/mute", status_code=status.HTTP_201_CREATED, summary="Silencia alerta")
def mute_alert(ports: PortsDep, body: MuteAlertIn) -> MutedAlertOut:
    """O `fingerprint` vem calculado pelo domínio e ancorado no sujeito mais a
    sprint. É por isso que entrar uma terceira iniciativa na mesma sprint não
    desfaz o silenciamento (cenário G do §13.1)."""
    return MutedAlertOut.model_validate(
        ports.use_case(MuteAlert).execute(body.to_input())
    )


@router.delete(
    "/mute/{mute_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Reativa alerta silenciado",
)
def unmute_alert(ports: PortsDep, mute_id: UUID) -> None:
    ports.use_case(UnmuteAlert).execute(mute_id)
