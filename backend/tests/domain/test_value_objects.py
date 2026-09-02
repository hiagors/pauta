"""Value objects: prioridade, cor, intervalo de sprints e responsável."""

import pytest

from app.domain.errors import (
    AmbiguousAssignee,
    AssigneeRequired,
    InvalidColor,
    InvalidSprintNumber,
    InvalidSprintRange,
)
from app.domain.value_objects.assignee import Assignee, AssigneeKind
from app.domain.value_objects.color import DEFAULT_PROJECT_COLOR, Color
from app.domain.value_objects.priority import Priority
from app.domain.value_objects.sprint_range import SprintRange
from tests.domain.conftest import uid


class TestPriority:
    def test_ordena_do_mais_para_o_menos_prioritario(self) -> None:
        ordered = sorted(Priority, key=lambda priority: priority.rank)
        assert ordered == [Priority.HIGH, Priority.MEDIUM, Priority.LOW]

    def test_viaja_como_string_em_ingles(self) -> None:
        assert Priority.HIGH == "HIGH"


class TestColor:
    def test_normaliza_para_maiusculo(self) -> None:
        assert Color("#0052cc").value == "#0052CC"

    @pytest.mark.parametrize("raw", ["0052CC", "#0052C", "#GGGGGG", "", "azul"])
    def test_recusa_formato_invalido(self, raw: str) -> None:
        with pytest.raises(InvalidColor):
            Color(raw)

    def test_parse_de_vazio_e_de_none_devolve_none(self) -> None:
        assert Color.parse(None) is None
        assert Color.parse("   ") is None

    def test_cor_padrao_de_projeto(self) -> None:
        assert Color.default_project().value == DEFAULT_PROJECT_COLOR


class TestSprintRange:
    def test_intervalo_e_inclusivo_nas_duas_pontas(self) -> None:
        interval = SprintRange(18, 22)
        assert interval.numbers == (18, 19, 20, 21, 22)
        assert len(interval) == 5
        assert 18 in interval
        assert 23 not in interval

    def test_uma_sprint_so(self) -> None:
        assert SprintRange(19, 19).numbers == (19,)

    def test_recusa_fim_antes_do_inicio(self) -> None:
        with pytest.raises(InvalidSprintRange):
            SprintRange(22, 18)

    def test_recusa_numero_abaixo_de_um(self) -> None:
        with pytest.raises(InvalidSprintNumber):
            SprintRange(0, 3)


class TestAssignee:
    def test_squad(self) -> None:
        assignee = Assignee.for_squad(uid(1))
        assert assignee.kind is AssigneeKind.SQUAD
        assert assignee.squad_id == uid(1)
        assert assignee.member_id is None

    def test_membro(self) -> None:
        assignee = Assignee.for_member(uid(2))
        assert assignee.kind is AssigneeKind.MEMBER
        assert assignee.member_id == uid(2)
        assert assignee.squad_id is None

    def test_kind_viaja_em_minusculo_no_json(self) -> None:
        assert AssigneeKind.SQUAD == "squad"
        assert AssigneeKind.MEMBER == "member"

    def test_sem_nenhum_dos_dois_e_erro(self) -> None:
        with pytest.raises(AssigneeRequired):
            Assignee.from_ids()

    def test_com_os_dois_e_erro(self) -> None:
        with pytest.raises(AmbiguousAssignee):
            Assignee.from_ids(squad_id=uid(1), member_id=uid(2))

    def test_igualdade_e_por_valor(self) -> None:
        assert Assignee.for_squad(uid(1)) == Assignee.for_squad(uid(1))
        assert Assignee.for_squad(uid(1)) != Assignee.for_member(uid(1))
