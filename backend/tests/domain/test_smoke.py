"""Teste-fumaça do backend.

Existe por dois motivos: `pytest` sem nenhum teste sai com código 5 e faria
`mise run test` falhar (§13, Fase 0), e a importação do pacote de domínio prova
que o venv e o `pythonpath` estão de pé. A Fase 1 traz os testes de verdade.
"""

import app.application
import app.domain


def test_domain_and_application_packages_are_importable() -> None:
    assert app.domain.__name__ == "app.domain"
    assert app.application.__name__ == "app.application"
