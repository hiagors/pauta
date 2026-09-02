"""Persistência em SQLite (§9).

`models.py` mapeia as tabelas, `mappers.py` traduz modelo <-> entidade,
`session.py` cria a engine e a fábrica de sessões, e `repositories/`
implementa os `Protocol` de `domain/ports/repositories.py`.

Nada daqui aparece na assinatura de um use case: o que atravessa a fronteira
são as portas e os DTOs.
"""
