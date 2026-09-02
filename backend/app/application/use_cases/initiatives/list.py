"""Listar iniciativas (§8, `?project_id=&status=&priority=&layer=&q=`)."""

from dataclasses import dataclass

from app.application.dto.initiatives import InitiativeFilter, InitiativeView
from app.domain.ports.repositories import InitiativeRepository


@dataclass(frozen=True)
class ListInitiatives:
    initiatives: InitiativeRepository

    def execute(self, filters: InitiativeFilter | None = None) -> list[InitiativeView]:
        """Ordem de fila: prioridade primeiro, nome como desempate."""
        criteria = filters or InitiativeFilter()
        found = self.initiatives.list_all(
            project_id=criteria.project_id,
            statuses=criteria.statuses or None,
            priorities=criteria.priorities or None,
            layer=criteria.layer,
            query=criteria.query,
        )
        return [
            InitiativeView.of(initiative)
            for initiative in sorted(
                found, key=lambda item: (item.priority.rank, item.name.casefold())
            )
        ]
