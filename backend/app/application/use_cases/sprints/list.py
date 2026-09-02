"""Listar sprints (`GET /sprints ?from=&to=`)."""

from dataclasses import dataclass

from app.application.dto.sprints import SprintView
from app.application.planning_view import load_window
from app.domain.ports.clock import Clock
from app.domain.ports.repositories import SprintRepository


@dataclass(frozen=True)
class ListSprints:
    sprints: SprintRepository
    clock: Clock

    def execute(
        self, *, number_from: int | None = None, number_to: int | None = None
    ) -> list[SprintView]:
        """`is_current` sai do conjunto **inteiro**, não da janela pedida.

        RN12: a atual é a de maior `start_date` já passado. Pedir da 20 à 22
        não promove a 20 a atual.
        """
        window = load_window(
            sprints=self.sprints,
            clock=self.clock,
            number_from=number_from,
            number_to=number_to,
        )
        return [
            SprintView.of(sprint, is_current=window.is_current(sprint))
            for sprint in window.selected
        ]
