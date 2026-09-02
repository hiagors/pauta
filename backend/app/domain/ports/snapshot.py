"""Portas de snapshot (§9).

O banco é a fonte da verdade; JSON e Markdown são **saída** (D5). A
reimportação é restauração, não integração — não existe importação de planilha
nem de CSV (RNF5).

O writer devolve os caminhos que gerou. Que formato ele escreve, em que ordem de
chaves e com qual debounce é detalhe de adapter: o domínio não sabe.

`SnapshotStore` é a terceira porta, e existe porque export e import são
operações sobre o banco **inteiro**, não sobre um agregado:

- o export precisa ler tudo, e ler oito repositórios para montar um objeto que
  já tem nome (`SnapshotBundle`) seria o mesmo trabalho espalhado;
- o import é `replace` (RNF4): apaga e recria dentro de uma transação. As
  portas de `repositories.py` não têm — e não podem ter — o `delete` que isso
  exigiria: membro e squad saem por `is_active = false` (§6.4, §6.5) e sprint
  nunca é excluída (D13). Abrir um `delete` em cada uma delas para servir a
  restauração desfaria justamente a regra que a ausência do método protege.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from app.domain.entities.allocation import Allocation
from app.domain.entities.initiative import Initiative
from app.domain.entities.member import Member
from app.domain.entities.muted_alert import MutedAlert
from app.domain.entities.project import Project
from app.domain.entities.sprint import Sprint
from app.domain.entities.squad import Squad
from app.domain.entities.squad_membership import SquadMembership


@dataclass(frozen=True)
class SnapshotBundle:
    """O banco inteiro, em entidades de domínio.

    A importação preserva verbatim os UUIDs e o `created_at` de `MutedAlert`
    (RNF4) — é o que faz o roundtrip export -> import -> export produzir
    arquivos byte a byte idênticos.
    """

    projects: tuple[Project, ...] = ()
    initiatives: tuple[Initiative, ...] = ()
    members: tuple[Member, ...] = ()
    squads: tuple[Squad, ...] = ()
    squad_memberships: tuple[SquadMembership, ...] = ()
    sprints: tuple[Sprint, ...] = ()
    allocations: tuple[Allocation, ...] = ()
    muted_alerts: tuple[MutedAlert, ...] = ()


@runtime_checkable
class SnapshotWriter(Protocol):
    def write(self, bundle: SnapshotBundle) -> tuple[Path, ...]:
        """Escreve o snapshot e devolve os caminhos gerados."""
        ...


@runtime_checkable
class SnapshotReader(Protocol):
    def read(self, path: Path) -> SnapshotBundle:
        """Lê um snapshot de um diretório."""
        ...


@runtime_checkable
class SnapshotStore(Protocol):
    """O banco inteiro, de uma vez: é o que export e import precisam."""

    def dump(self) -> SnapshotBundle:
        """Tudo o que está gravado, com as listas ordenadas por `id`."""
        ...

    def replace(self, bundle: SnapshotBundle) -> None:
        """Apaga o que existe e grava o `bundle` no lugar (RNF4).

        Não faz `commit`: quem abre e fecha a transação é o adapter de entrada
        (a requisição HTTP ou o comando da CLI). É isso que faz "apaga e
        recria" ser tudo ou nada.
        """
        ...
