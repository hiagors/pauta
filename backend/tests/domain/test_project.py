"""Projeto: agrupador, sem status, sem prioridade, sem alocação (§6.1)."""

import pytest

from app.domain.entities.project import Project
from app.domain.errors import InvalidName
from app.domain.value_objects.color import DEFAULT_PROJECT_COLOR, Color


def test_criacao_com_o_minimo() -> None:
    project = Project.create(name="CRM")
    assert project.name == "CRM"
    assert project.description == ""
    assert project.color is None
    assert project.is_capacity_reserve is False
    assert project.is_active is True


def test_nome_e_obrigatorio() -> None:
    with pytest.raises(InvalidName):
        Project.create(name="   ")


def test_nome_e_normalizado() -> None:
    assert Project.create(name="  CRM  ").name == "CRM"


def test_projeto_sem_cor_usa_a_cor_neutra_padrao() -> None:
    assert Project.create(name="CRM").effective_color.value == DEFAULT_PROJECT_COLOR


def test_projeto_com_cor_usa_a_dele() -> None:
    project = Project.create(name="CRM", color=Color("#0052CC"))
    assert project.effective_color.value == "#0052CC"


def test_reserva_de_capacidade_e_ligavel_e_desligavel() -> None:
    project = Project.create(name="SUS", is_capacity_reserve=True)
    assert project.is_capacity_reserve
    project.set_capacity_reserve(False)
    assert not project.is_capacity_reserve


def test_projeto_nao_tem_status_nem_prioridade_nem_alocacao() -> None:
    campos = set(Project.__dataclass_fields__)
    assert not campos & {"status", "priority", "allocations", "squad_id", "member_id"}
