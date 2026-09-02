"""Adapter de entrada de linha de comando (§5).

Um grupo só na v1: `snapshot`, com `export` e `import` (§9). Roda por
`python -m app.adapters.inbound.cli`, que é o que o `mise run snapshot` chama.

Como a borda HTTP, a CLI é dona da transação: o comando abre a sessão, faz
`commit` no fim e `rollback` na exceção. Repositório não faz `commit` (ver
`persistence/session.py`).
"""

from app.adapters.inbound.cli.main import cli

__all__ = ["cli"]
