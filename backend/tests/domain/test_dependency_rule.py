"""A regra de dependência do §5, como teste que falha.

`app/domain` importa **apenas** stdlib e ele mesmo. `app/application` importa
`app/domain`, nunca `app/adapters`. Sem isso a regra é um parágrafo de
documento; com isso é um build vermelho.
"""

import ast
import sys
from collections.abc import Iterator
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
DOMAIN = BACKEND / "app" / "domain"
APPLICATION = BACKEND / "app" / "application"

#: stdlib que o domínio não pode importar **mesmo sendo stdlib**.
#:
#: A regra do §5 é "só stdlib", e ela é literal demais para pegar isto: por
#: anos `domain/ports/snapshot.py` declarou `SnapshotWriter.write(...) ->
#: tuple[Path, ...]` e a varredura passava, porque `pathlib` é stdlib. O que
#: tinha entrado no domínio não era uma biblioteca — era o **conceito**
#: "sistema de arquivos", e ele vazava dali para o DTO da aplicação e daí para
#: o schema HTTP. As duas portas foram para `application/ports/`, e esta lista
#: existe para elas não voltarem.
FILESYSTEM_IN_DOMAIN = frozenset(
    {"pathlib", "os", "shutil", "tempfile", "io", "socket", "subprocess"}
)

#: As quatro que o CLAUDE.md nomeia, mais as que viriam pelo mesmo caminho.
FORBIDDEN_IN_DOMAIN = frozenset(
    {
        "sqlalchemy",
        "pydantic",
        "pydantic_settings",
        "fastapi",
        "alembic",
        "uvicorn",
        "typer",
        "starlette",
        "httpx",
    }
)


def _python_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


def _imported_modules(path: Path) -> Iterator[tuple[int, str]]:
    """Todo módulo importado pelo arquivo, com imports relativos resolvidos."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    parts = list(path.relative_to(BACKEND).with_suffix("").parts)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = parts[: len(parts) - node.level]
                suffix = node.module.split(".") if node.module else []
                yield node.lineno, ".".join([*base, *suffix])
            else:
                yield node.lineno, node.module or ""


def _top_level(module: str) -> str:
    return module.split(".", 1)[0]


def test_domain_imports_only_stdlib_and_itself() -> None:
    violations: list[str] = []
    for path in _python_files(DOMAIN):
        for lineno, module in _imported_modules(path):
            if module.startswith("app.domain"):
                continue
            if _top_level(module) in sys.stdlib_module_names:
                continue
            violations.append(
                f"{path.relative_to(BACKEND)}:{lineno} importa {module!r}"
            )
    assert not violations, (
        "app/domain só pode importar stdlib e app.domain:\n  " + "\n  ".join(violations)
    )


def test_domain_never_imports_the_forbidden_libraries() -> None:
    """Redundante de propósito: falha nomeando a biblioteca proibida.

    A varredura é no AST, não no texto: os comentários do domínio citam
    `sqlalchemy` e `pydantic` justamente para explicar a regra, e um `grep`
    daria falso positivo neles.
    """
    violations: list[str] = []
    for path in _python_files(DOMAIN):
        for lineno, module in _imported_modules(path):
            if _top_level(module) in FORBIDDEN_IN_DOMAIN:
                violations.append(
                    f"{path.relative_to(BACKEND)}:{lineno} importa {module!r}"
                )
    assert not violations, (
        "dependência de adapter dentro do domínio:\n  " + "\n  ".join(violations)
    )


def test_the_domain_does_not_know_what_a_file_is() -> None:
    """ "Só stdlib" não basta: `pathlib` é stdlib e é sistema de arquivos.

    Exportar o plano para uma pasta é caso de uso (§9), e as portas que falam
    de `Path` moram em `application/ports/snapshot.py`.
    """
    violations: list[str] = []
    for path in _python_files(DOMAIN):
        for lineno, module in _imported_modules(path):
            if _top_level(module) in FILESYSTEM_IN_DOMAIN:
                violations.append(
                    f"{path.relative_to(BACKEND)}:{lineno} importa {module!r}"
                )
    assert not violations, "o domínio não tem sistema de arquivos:\n  " + "\n  ".join(
        violations
    )


def test_application_never_imports_adapters() -> None:
    violations: list[str] = []
    for path in _python_files(APPLICATION):
        for lineno, module in _imported_modules(path):
            if module.startswith("app.adapters"):
                violations.append(
                    f"{path.relative_to(BACKEND)}:{lineno} importa {module!r}"
                )
    assert not violations, (
        "application/ não pode importar adapters/:\n  " + "\n  ".join(violations)
    )


def test_the_scan_actually_sees_imports() -> None:
    """Guarda contra o pior modo de falha: um teste que passa vazio."""
    service = DOMAIN / "services" / "alert_service.py"
    fingerprint = DOMAIN / "services" / "fingerprint.py"
    assert "app.domain.services.planning_rules" in {
        module for _, module in _imported_modules(service)
    }
    assert "hashlib" in {module for _, module in _imported_modules(fingerprint)}
