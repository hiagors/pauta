"""Montagem do modelo de leitura do plano.

Não é use case: é a tradução de repositórios para `PlanningSnapshot` (§13) que
`get_grid`, `list_alerts`, `allocate_range` e `deallocate` fazem exatamente
igual. Fica em funções livres, e não numa classe que carrega o feixe de portas,
para que cada use case continue declarando as portas que usa — a regra do §5 é
"só portas e DTOs", não "um objeto que sabe tudo".

O domínio nunca recebe repositório: recebe a fotografia pronta.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.initiative import Initiative
from app.domain.entities.muted_alert import MutedAlert
from app.domain.entities.sprint import Sprint
from app.domain.errors import ProjectNotFound
from app.domain.ports.clock import Clock
from app.domain.ports.repositories import (
    AllocationRepository,
    InitiativeRepository,
    MemberRepository,
    MutedAlertRepository,
    ProjectRepository,
    SprintRepository,
    SquadMembershipRepository,
    SquadRepository,
)
from app.domain.services.planning_rules import (
    AllocationFact,
    InitiativeRef,
    MembershipFact,
    PlanningSnapshot,
    current_sprint,
    sprints_in_quarter,
)


@dataclass(frozen=True)
class SprintWindow:
    """Uma janela de sprints, com a sprint atual do conjunto **inteiro**.

    `current` é calculada sobre todas as sprints cadastradas, não sobre a
    janela: RN12 define a atual como a de maior `start_date` já passado, e
    recortar a janela não muda esse fato — a Sprint 18 continua sendo a atual
    quando a grade mostra só da 20 à 22.
    """

    all: tuple[Sprint, ...]
    selected: tuple[Sprint, ...]
    current: Sprint | None

    @property
    def numbers(self) -> tuple[int, ...]:
        return tuple(sprint.number for sprint in self.selected)

    @property
    def ids(self) -> tuple[UUID, ...]:
        return tuple(sprint.id for sprint in self.selected)

    @property
    def current_number(self) -> int | None:
        return self.current.number if self.current is not None else None

    @property
    def by_number(self) -> dict[int, Sprint]:
        return {sprint.number: sprint for sprint in self.selected}

    def number_of(self, sprint_id: UUID) -> int:
        """Número da sprint de um id qualquer, dentro ou fora da janela."""
        for sprint in self.all:
            if sprint.id == sprint_id:
                return sprint.number
        raise KeyError(sprint_id)

    def is_current(self, sprint: Sprint) -> bool:
        return self.current is not None and self.current.id == sprint.id

    def narrowed(
        self, *, number_from: int | None = None, number_to: int | None = None
    ) -> SprintWindow:
        """Recorta a janela sem voltar ao repositório.

        Serve a quem precisa da sprint atual para **decidir** o recorte — o
        painel de alertas, cuja janela default começa na atual (§8).
        """
        return SprintWindow(
            all=self.all,
            selected=tuple(
                sprint
                for sprint in self.selected
                if (number_from is None or sprint.number >= number_from)
                and (number_to is None or sprint.number <= number_to)
            ),
            current=self.current,
        )


def load_window(
    *,
    sprints: SprintRepository,
    clock: Clock,
    number_from: int | None = None,
    number_to: int | None = None,
) -> SprintWindow:
    """Janela explícita. Sem limites, é o conjunto inteiro."""
    everything = tuple(sprints.list_all())
    selected = tuple(
        sprint
        for sprint in everything
        if (number_from is None or sprint.number >= number_from)
        and (number_to is None or sprint.number <= number_to)
    )
    return SprintWindow(
        all=everything,
        selected=selected,
        current=current_sprint(everything, clock.today()),
    )


def load_quarter_window(*, sprints: SprintRepository, clock: Clock) -> SprintWindow:
    """RN13: as sprints que intersectam o trimestre corrente.

    Trimestre civil, por RN13 — trocar por um fiscal deslocado é
    mexer só em `civil_quarter_bounds`.
    """
    everything = tuple(sprints.list_all())
    today = clock.today()
    return SprintWindow(
        all=everything,
        selected=tuple(sprints_in_quarter(everything, today)),
        current=current_sprint(everything, today),
    )


def load_initiative_refs(
    *, projects: ProjectRepository, initiatives: Sequence[Initiative]
) -> dict[UUID, InitiativeRef]:
    """Resolve o projeto de cada iniciativa (§6.2).

    `is_capacity_reserve` é **herdado do projeto**: a iniciativa não tem esse
    campo, e é aqui — no use case, com o repositório na mão — que o booleano
    é resolvido antes de o domínio ver.
    """
    wanted = {initiative.project_id for initiative in initiatives}
    found = {project.id: project for project in projects.list_by_ids(wanted)}
    missing = wanted - found.keys()
    if missing:
        raise ProjectNotFound(next(iter(sorted(missing, key=str))))
    return {
        initiative.id: InitiativeRef(
            id=initiative.id,
            name=initiative.name,
            project_id=initiative.project_id,
            project_name=found[initiative.project_id].name,
            is_capacity_reserve=found[initiative.project_id].is_capacity_reserve,
        )
        for initiative in initiatives
    }


def load_snapshot(
    *,
    window: SprintWindow,
    allocations: AllocationRepository,
    initiatives: InitiativeRepository,
    projects: ProjectRepository,
    members: MemberRepository,
    squads: SquadRepository,
    memberships: SquadMembershipRepository,
) -> PlanningSnapshot:
    """A fotografia do plano na janela, pronta para `evaluate_alerts`.

    `members` leva **apenas** os ativos: é a RN-S3 (quem é
    inativado só desaparece) implementada num lugar só, e é o que os dois
    alertas de membro do §7.3 pedem ao dizer "membro ativo". Alocação ou
    membership que aponte para alguém fora do mapa é ignorada pelo domínio.

    `squads` leva **todas**, com as inativas marcadas à parte. O §7.3 qualifica
    "squad ativa" só em `EMPTY_SQUAD`, e é o domínio que aplica a distinção —
    aqui ela seria aplicada aos quatro alertas de uma vez.

    O nome que viaja é o `short_name` do membro: é ele que aparece nas
    mensagens de alerta ("Ana está nas squads...", §7.3) e nos chips da UI.
    """
    cells = allocations.list_all(sprint_ids=window.ids)
    known_squads = squads.list_all()
    refs = load_initiative_refs(
        projects=projects,
        initiatives=initiatives.list_by_ids({cell.initiative_id for cell in cells}),
    )
    return PlanningSnapshot(
        sprint_numbers=window.numbers,
        allocations=tuple(
            AllocationFact(
                sprint_number=window.number_of(cell.sprint_id),
                initiative=refs[cell.initiative_id],
                assignee=cell.assignee,
            )
            for cell in cells
        ),
        memberships=tuple(
            MembershipFact(
                sprint_number=window.number_of(link.sprint_id),
                squad_id=link.squad_id,
                member_id=link.member_id,
            )
            for link in memberships.list_all(sprint_ids=window.ids)
        ),
        squads={squad.id: squad.name for squad in known_squads},
        inactive_squad_ids=frozenset(
            squad.id for squad in known_squads if not squad.is_active
        ),
        members={
            member.id: member.short_name for member in members.list_all(active=True)
        },
        current_sprint_number=window.current_number,
    )


def load_mutes(muted_alerts: MutedAlertRepository) -> Mapping[str, MutedAlert]:
    """Silenciamentos indexados por `fingerprint`, como o domínio espera."""
    return {mute.fingerprint: mute for mute in muted_alerts.list_all()}


def initiative_ids_of_projects(
    *, initiatives: InitiativeRepository, project_id: UUID
) -> Collection[UUID]:
    """Ids das iniciativas de um projeto — o filtro `project_id` do §8."""
    return [initiative.id for initiative in initiatives.list_all(project_id=project_id)]
