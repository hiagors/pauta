"""Erros de domínio.

Três bases, e só três, porque é o que o handler único do §8 precisa para
escolher o código HTTP sem conhecer cada erro concreto:

- `DomainError`   -> 422
- `NotFoundError` -> 404
- `ConflictError` -> 409

Toda exceção carrega um `code` estável (o contrato do JSON de erro), uma
`message` em português e um `details` com os dados que a UI usa para montar o
aviso. Os construtores recebem apenas primitivos (`str`, `int`, `date`, `UUID`)
de propósito: este módulo é a folha da árvore de imports do domínio e não pode
depender de entidade nem de value object.
"""

from datetime import date
from typing import ClassVar
from uuid import UUID


class DomainError(Exception):
    """Violação de regra de negócio. Vira 422 na borda HTTP."""

    code: ClassVar[str] = "DOMAIN_ERROR"

    def __init__(self, message: str, **details: object) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, object] = dict(details)


class NotFoundError(DomainError):
    """Entidade referenciada não existe. Vira 404."""

    code: ClassVar[str] = "NOT_FOUND"


class ConflictError(DomainError):
    """Conflito de unicidade ou de estado. Vira 409."""

    code: ClassVar[str] = "CONFLICT"


# --------------------------------------------------------------------------- #
# Validação (422)
# --------------------------------------------------------------------------- #


class InvalidName(DomainError):
    code: ClassVar[str] = "INVALID_NAME"

    def __init__(self, entity: str) -> None:
        super().__init__(f"O nome {entity} é obrigatório.", entity=entity)


class InvalidColor(DomainError):
    code: ClassVar[str] = "INVALID_COLOR"

    def __init__(self, value: str) -> None:
        super().__init__(
            f"Cor inválida: {value!r}. Use o formato #RRGGBB.", value=value
        )


class InvalidEstimate(DomainError):
    code: ClassVar[str] = "INVALID_ESTIMATE"

    def __init__(self, value: int) -> None:
        super().__init__(
            f"A estimativa em sprints precisa ser maior que zero; recebido {value}.",
            value=value,
        )


class InvalidSprintNumber(DomainError):
    code: ClassVar[str] = "INVALID_SPRINT_NUMBER"

    def __init__(self, number: int) -> None:
        super().__init__(
            f"Número de sprint inválido: {number}. O menor número válido é 1.",
            number=number,
        )


class InvalidSprintDates(DomainError):
    code: ClassVar[str] = "INVALID_SPRINT_DATES"

    def __init__(self, start_date: date, end_date: date) -> None:
        super().__init__(
            f"A data de fim ({end_date.isoformat()}) precisa ser posterior "
            f"à de início ({start_date.isoformat()}).",
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
        )


class InvalidSprintRange(DomainError):
    code: ClassVar[str] = "INVALID_SPRINT_RANGE"

    def __init__(self, from_number: int, to_number: int) -> None:
        super().__init__(
            f"Intervalo de sprints inválido: {from_number} a {to_number}. "
            "A sprint final não pode ser anterior à inicial.",
            from_number=from_number,
            to_number=to_number,
        )


class InvalidStatusTransition(DomainError):
    code: ClassVar[str] = "INVALID_STATUS_TRANSITION"

    def __init__(self, current: str, requested: str) -> None:
        super().__init__(
            f"Transição de status inválida: {current} para {requested}.",
            current=current,
            requested=requested,
        )


class AssigneeRequired(DomainError):
    code: ClassVar[str] = "ASSIGNEE_REQUIRED"

    def __init__(self) -> None:
        super().__init__(
            "A alocação precisa de um responsável: uma squad ou um membro."
        )


class AmbiguousAssignee(DomainError):
    code: ClassVar[str] = "AMBIGUOUS_ASSIGNEE"

    def __init__(self) -> None:
        super().__init__(
            "A alocação aceita uma squad ou um membro, nunca os dois ao mesmo tempo."
        )


class InitiativeNotAllocatable(DomainError):
    code: ClassVar[str] = "INITIATIVE_NOT_ALLOCATABLE"

    def __init__(self, initiative_id: UUID, status: str) -> None:
        super().__init__(
            f"A iniciativa está em {status} e não aceita nova alocação. "
            "As alocações existentes permanecem como histórico.",
            initiative_id=str(initiative_id),
            status=status,
        )


class InvalidRepresentative(DomainError):
    code: ClassVar[str] = "INVALID_REPRESENTATIVE"

    def __init__(self, member_id: UUID) -> None:
        super().__init__(
            "O representante da squad precisa ser um membro ativo.",
            member_id=str(member_id),
        )


class MuteReasonRequired(DomainError):
    code: ClassVar[str] = "MUTE_REASON_REQUIRED"

    def __init__(self) -> None:
        super().__init__("Silenciar um alerta exige um motivo.")


class InvalidSnapshot(DomainError):
    """Snapshot ilegível ou incoerente (RNF4).

    Vale para as duas formas de estar errado: arquivo que não é o JSON
    esperado e conjunto que não fecha — uma alocação apontando para uma
    iniciativa que não está no snapshot, por exemplo. Nos dois casos a
    restauração para antes de apagar qualquer coisa.
    """

    code: ClassVar[str] = "INVALID_SNAPSHOT"

    def __init__(self, reason: str, **details: object) -> None:
        super().__init__(f"Snapshot inválido: {reason}", reason=reason, **details)


class SnapshotImportNotConfirmed(DomainError):
    """§8: a importação é destrutiva e exige `?confirm=true`."""

    code: ClassVar[str] = "SNAPSHOT_IMPORT_NOT_CONFIRMED"

    def __init__(self) -> None:
        super().__init__(
            "A importação apaga todos os dados e recria a partir do snapshot. "
            "Confirme a operação para continuar."
        )


class InvalidTimestamp(DomainError):
    code: ClassVar[str] = "INVALID_TIMESTAMP"

    def __init__(self, field: str) -> None:
        super().__init__(
            f"O campo {field} precisa ser um datetime em UTC com timezone.",
            field=field,
        )


# --------------------------------------------------------------------------- #
# Não encontrado (404)
# --------------------------------------------------------------------------- #


class ProjectNotFound(NotFoundError):
    code: ClassVar[str] = "PROJECT_NOT_FOUND"

    def __init__(self, project_id: UUID) -> None:
        super().__init__(
            f"Projeto {project_id} não existe.", project_id=str(project_id)
        )


class InitiativeNotFound(NotFoundError):
    code: ClassVar[str] = "INITIATIVE_NOT_FOUND"

    def __init__(self, initiative_id: UUID) -> None:
        super().__init__(
            f"Iniciativa {initiative_id} não existe.",
            initiative_id=str(initiative_id),
        )


class MemberNotFound(NotFoundError):
    code: ClassVar[str] = "MEMBER_NOT_FOUND"

    def __init__(self, member_id: UUID) -> None:
        super().__init__(f"Membro {member_id} não existe.", member_id=str(member_id))


class SquadNotFound(NotFoundError):
    code: ClassVar[str] = "SQUAD_NOT_FOUND"

    def __init__(self, squad_id: UUID) -> None:
        super().__init__(f"Squad {squad_id} não existe.", squad_id=str(squad_id))


class SprintNotFound(NotFoundError):
    code: ClassVar[str] = "SPRINT_NOT_FOUND"

    def __init__(
        self, *, sprint_id: UUID | None = None, number: int | None = None
    ) -> None:
        if number is not None:
            super().__init__(f"Sprint {number} não existe.", number=number)
        elif sprint_id is not None:
            super().__init__(
                f"Sprint {sprint_id} não existe.", sprint_id=str(sprint_id)
            )
        else:
            super().__init__(
                "Nenhuma sprint cadastrada. Crie a primeira informando as datas."
            )


class AllocationNotFound(NotFoundError):
    code: ClassVar[str] = "ALLOCATION_NOT_FOUND"

    def __init__(self, allocation_id: UUID) -> None:
        super().__init__(
            f"Alocação {allocation_id} não existe.",
            allocation_id=str(allocation_id),
        )


class SnapshotNotFound(NotFoundError):
    code: ClassVar[str] = "SNAPSHOT_NOT_FOUND"

    def __init__(self, path: str) -> None:
        super().__init__(
            f"Não há snapshot em {path}. Informe a pasta que tem os arquivos "
            "JSON exportados.",
            path=path,
        )


class MutedAlertNotFound(NotFoundError):
    code: ClassVar[str] = "MUTED_ALERT_NOT_FOUND"

    def __init__(self, mute_id: UUID) -> None:
        super().__init__(f"Silenciamento {mute_id} não existe.", mute_id=str(mute_id))


# --------------------------------------------------------------------------- #
# Conflito (409)
# --------------------------------------------------------------------------- #


class DuplicateName(ConflictError):
    code: ClassVar[str] = "DUPLICATE_NAME"

    def __init__(self, entity: str, name: str) -> None:
        super().__init__(
            f"Já existe {entity} com o nome {name!r}.", entity=entity, name=name
        )


class AllocationConflict(ConflictError):
    code: ClassVar[str] = "ALLOCATION_CONFLICT"

    def __init__(
        self,
        *,
        initiative_id: UUID,
        sprint_number: int,
        occupant_kind: str,
        occupant_id: UUID,
    ) -> None:
        quem = "uma squad" if occupant_kind == "squad" else "um membro"
        super().__init__(
            f"A iniciativa já tem {quem} como responsável na Sprint "
            f"{sprint_number}. Uma iniciativa tem um responsável por sprint.",
            initiative_id=str(initiative_id),
            sprint_number=sprint_number,
            occupant_kind=occupant_kind,
            occupant_id=str(occupant_id),
        )


class SprintOverlap(ConflictError):
    code: ClassVar[str] = "SPRINT_OVERLAP"

    def __init__(self, number: int, other_number: int) -> None:
        super().__init__(
            f"A Sprint {number} se sobrepõe à Sprint {other_number}.",
            number=number,
            other_number=other_number,
        )


class SprintNumberTaken(ConflictError):
    code: ClassVar[str] = "SPRINT_NUMBER_TAKEN"

    def __init__(self, number: int) -> None:
        super().__init__(f"A Sprint {number} já existe.", number=number)


class SprintNumberGap(ConflictError):
    code: ClassVar[str] = "SPRINT_NUMBER_GAP"

    def __init__(self, expected: int, received: int) -> None:
        super().__init__(
            f"A numeração das sprints não pode ter buraco: depois da anterior "
            f"vem a {expected}, não a {received}.",
            expected=expected,
            received=received,
        )


class LastInitiativeOfProject(ConflictError):
    code: ClassVar[str] = "LAST_INITIATIVE_OF_PROJECT"

    def __init__(self, project_id: UUID) -> None:
        super().__init__(
            "Um projeto não pode ficar sem iniciativa. Cadastre outra antes de "
            "excluir esta, ou marque a iniciativa como CANCELLED.",
            project_id=str(project_id),
        )


class AlertAlreadyMuted(ConflictError):
    code: ClassVar[str] = "ALERT_ALREADY_MUTED"

    def __init__(self, fingerprint: str) -> None:
        super().__init__("Este alerta já está silenciado.", fingerprint=fingerprint)


class HasAllocations(ConflictError):
    code: ClassVar[str] = "HAS_ALLOCATIONS"

    def __init__(self, entity: str) -> None:
        super().__init__(
            f"Não é possível excluir {entity}: existem alocações apontando para ele. "
            "Marque como CANCELLED para preservar o histórico.",
            entity=entity,
        )
