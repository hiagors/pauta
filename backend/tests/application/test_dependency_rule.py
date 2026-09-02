"""O critério de aceite da Fase 2: nenhum use case conhece banco.

A varredura de imports é a mesma da suíte de domínio — importada dela em vez
de copiada, para a regra ter um scanner só. Aqui o alvo é `app/application`:
pode importar stdlib, `app.domain` e ele mesmo. Nada de SQLAlchemy, Pydantic,
FastAPI ou `app.adapters`.
"""

import sys

from tests.domain.test_dependency_rule import (
    APPLICATION,
    BACKEND,
    FORBIDDEN_IN_DOMAIN,
    _imported_modules,
    _python_files,
    _top_level,
)


def test_application_imports_only_stdlib_domain_and_itself() -> None:
    violations: list[str] = []
    for path in _python_files(APPLICATION):
        for lineno, module in _imported_modules(path):
            if module.startswith(("app.domain", "app.application")):
                continue
            if _top_level(module) in sys.stdlib_module_names:
                continue
            violations.append(
                f"{path.relative_to(BACKEND)}:{lineno} importa {module!r}"
            )
    assert not violations, (
        "app/application só pode importar stdlib, app.domain e app.application:\n  "
        + "\n  ".join(violations)
    )


def test_application_never_imports_infrastructure() -> None:
    """Redundante de propósito: falha nomeando a biblioteca."""
    violations: list[str] = []
    for path in _python_files(APPLICATION):
        for lineno, module in _imported_modules(path):
            if _top_level(module) in FORBIDDEN_IN_DOMAIN:
                violations.append(
                    f"{path.relative_to(BACKEND)}:{lineno} importa {module!r}"
                )
    assert not violations, "infraestrutura dentro de application/:\n  " + "\n  ".join(
        violations
    )


def test_the_scan_actually_sees_the_use_cases() -> None:
    """Guarda contra o pior modo de falha: um teste que passa vazio."""
    scanned = list(_python_files(APPLICATION))
    assert len(scanned) > 30
    allocate = APPLICATION / "use_cases" / "planning" / "allocate_range.py"
    assert "app.domain.services.planning_rules" in {
        module for _, module in _imported_modules(allocate)
    }
