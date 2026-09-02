"""`plan-sprint-N.md` e `plan-grid.md` (§9).

Os dois arquivos que uma pessoa abre no Drive: um por sprint, dizendo quem está
em quê, e a grade inteira em tabela. São **derivados** — nada aqui é fonte da
verdade, e a restauração da RNF4 lê o JSON, nunca isto.

Duas escolhas de apresentação, porque estes arquivos são para ler:

- data em `dd/mm/aaaa`, como o resto da UI em português;
- `status` e `priority` saem com o valor do código. São identificadores, como
  no JSON, e traduzi-los aqui duplicaria em um adapter o mapa de rótulos que é
  da UI (§10).

O writer também **apaga** os `plan-sprint-N.md` de sprints que não estão mais
no snapshot. A pasta é sincronizada: um arquivo órfão de uma restauração
anterior seria lido como plano vigente.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from uuid import UUID

from app.domain.entities.initiative import Initiative
from app.domain.entities.project import Project
from app.domain.entities.sprint import Sprint
from app.domain.ports.snapshot import SnapshotBundle

#: `plan-sprint-18.md`. O glob do mesmo padrão é o que acha os órfãos.
SPRINT_PLAN_PREFIX = "plan-sprint-"
SPRINT_PLAN_SUFFIX = ".md"
GRID_FILENAME = "plan-grid.md"


@dataclass(frozen=True)
class MarkdownSnapshotWriter:
    """Implementa `SnapshotWriter` com a parte Markdown do §9."""

    directory: Path

    def write(self, bundle: SnapshotBundle) -> tuple[Path, ...]:
        self.directory.mkdir(parents=True, exist_ok=True)
        plan = _Plan(bundle)
        written = [self._write_sprint(plan, sprint) for sprint in plan.sprints]
        self._remove_orphans(keep={path.name for path in written})
        written.append(_write(self.directory / GRID_FILENAME, _grid(plan)))
        return tuple(written)

    def _write_sprint(self, plan: _Plan, sprint: Sprint) -> Path:
        name = f"{SPRINT_PLAN_PREFIX}{sprint.number}{SPRINT_PLAN_SUFFIX}"
        return _write(self.directory / name, _sprint_plan(plan, sprint))

    def _remove_orphans(self, *, keep: set[str]) -> None:
        pattern = f"{SPRINT_PLAN_PREFIX}*{SPRINT_PLAN_SUFFIX}"
        for path in self.directory.glob(pattern):
            if path.name not in keep:
                path.unlink()


class _Plan:
    """Índices do bundle, montados uma vez para os dois arquivos.

    Não é regra de negócio: é a mesma travessia que a grade do §8 faz, aqui só
    para virar texto.
    """

    def __init__(self, bundle: SnapshotBundle) -> None:
        self.sprints = sorted(bundle.sprints, key=lambda sprint: sprint.number)
        self._projects = {project.id: project for project in bundle.projects}
        self._initiatives = {
            initiative.id: initiative for initiative in bundle.initiatives
        }
        self._names: dict[UUID, str] = {squad.id: squad.name for squad in bundle.squads}
        self._names.update({member.id: member.short_name for member in bundle.members})
        self._sprint_numbers = {sprint.id: sprint.number for sprint in self.sprints}
        #: (iniciativa, número da sprint) -> responsável.
        self.assignees: dict[tuple[UUID, int], UUID] = {}
        for cell in bundle.allocations:
            number = self._sprint_numbers.get(cell.sprint_id)
            if number is None or cell.initiative_id not in self._initiatives:
                continue
            self.assignees[(cell.initiative_id, number)] = cell.assignee.id
        #: número da sprint -> squad -> membros.
        self.composition: dict[int, dict[UUID, list[UUID]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for link in bundle.squad_memberships:
            number = self._sprint_numbers.get(link.sprint_id)
            if number is not None:
                self.composition[number][link.squad_id].append(link.member_id)

    @property
    def allocated_initiatives(self) -> list[Initiative]:
        """As linhas do Gantt: iniciativa com pelo menos uma alocação.

        Ordem: projeto, prioridade e nome — a mesma de `GET /planning/grid`.
        """
        involved = {key[0] for key in self.assignees}
        return sorted(
            (self._initiatives[key] for key in involved),
            key=lambda initiative: (
                self.project_of(initiative).name.casefold(),
                initiative.priority.rank,
                initiative.name.casefold(),
            ),
        )

    def project_of(self, initiative: Initiative) -> Project:
        return self._projects[initiative.project_id]

    def name_of(self, entity_id: UUID) -> str:
        """Squad inativada continua sendo a responsável do passado, e a linha
        dela precisa de nome. Um id sem nome é snapshot incoerente, e aqui
        aparece como tal em vez de derrubar o export."""
        return self._names.get(entity_id, f"(desconhecido {entity_id})")


def _sprint_plan(plan: _Plan, sprint: Sprint) -> str:
    lines = [
        f"# Sprint {sprint.number} — {_day(sprint.start_date)} a "
        f"{_day(sprint.end_date)}",
        "",
        "## Quem está em quê",
        "",
    ]
    rows = [
        (
            plan.project_of(initiative).name,
            initiative.name,
            initiative.status.value,
            plan.name_of(plan.assignees[(initiative.id, sprint.number)]),
        )
        for initiative in plan.allocated_initiatives
        if (initiative.id, sprint.number) in plan.assignees
    ]
    if rows:
        lines.extend(_table(("Projeto", "Iniciativa", "Status", "Responsável"), rows))
    else:
        lines.append("Nenhuma alocação nesta sprint.")
    lines.extend(("", "## Composição das squads", ""))
    composition = [
        (
            plan.name_of(squad_id),
            ", ".join(sorted(plan.name_of(member_id) for member_id in member_ids)),
        )
        for squad_id, member_ids in sorted(
            plan.composition.get(sprint.number, {}).items(),
            key=lambda item: plan.name_of(item[0]).casefold(),
        )
    ]
    if composition:
        lines.extend(_table(("Squad", "Membros"), composition))
    else:
        lines.append("Nenhuma squad com composição nesta sprint.")
    return "\n".join(lines) + "\n"


def _grid(plan: _Plan) -> str:
    lines = ["# Grade de planejamento", "", "## Sprints", ""]
    if not plan.sprints:
        lines.append("Nenhuma sprint cadastrada.")
        return "\n".join(lines) + "\n"
    lines.extend(
        _table(
            ("Sprint", "Início", "Fim"),
            [
                (str(sprint.number), _day(sprint.start_date), _day(sprint.end_date))
                for sprint in plan.sprints
            ],
        )
    )
    lines.extend(("", "## Alocação por iniciativa", ""))
    initiatives = plan.allocated_initiatives
    if not initiatives:
        lines.append("Nenhuma alocação registrada.")
        return "\n".join(lines) + "\n"
    header = (
        "Projeto",
        "Iniciativa",
        *(f"S{sprint.number}" for sprint in plan.sprints),
    )
    lines.extend(
        _table(
            header,
            [
                (
                    plan.project_of(initiative).name,
                    initiative.name,
                    *(
                        _cell(plan, initiative.id, sprint.number)
                        for sprint in plan.sprints
                    ),
                )
                for initiative in initiatives
            ],
        )
    )
    return "\n".join(lines) + "\n"


def _cell(plan: _Plan, initiative_id: UUID, sprint_number: int) -> str:
    assignee = plan.assignees.get((initiative_id, sprint_number))
    return "" if assignee is None else plan.name_of(assignee)


def _table(header: tuple[str, ...], rows: list[tuple[str, ...]]) -> list[str]:
    return [
        _row(header),
        _row(tuple("---" for _ in header)),
        *(_row(row) for row in rows),
    ]


def _row(cells: tuple[str, ...]) -> str:
    return "| " + " | ".join(_escape(cell) for cell in cells) + " |"


def _escape(cell: str) -> str:
    """Nome com `|` quebraria a tabela. Nada aqui é HTML, então só o pipe."""
    return cell.replace("|", "\\|")


def _day(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path
