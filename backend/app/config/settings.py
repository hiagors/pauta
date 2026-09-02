"""Configuração do processo (§5, §10.4).

Tudo o que muda entre máquinas entra por variável de ambiente, definida no
`mise.toml`. O `DATABASE_URL` não tem default de propósito: um default
silencioso migraria ou leria o banco errado, e é a mesma decisão que o
`migrations/env.py` já tomou.

As origens do CORS moram aqui, e não no router, porque são configuração e não
regra: em produção local são as duas portas do dev server do Astro (§10.4).
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

#: As duas formas de escrever o mesmo dev server do Astro (§10.4). O navegador
#: manda a origem literalmente, então `localhost` e `127.0.0.1` são origens
#: diferentes e as duas precisam estar na lista.
DEFAULT_CORS_ORIGINS = ("http://localhost:4321", "http://127.0.0.1:4321")


class Settings(BaseSettings):
    """Lida do ambiente. Nenhum campo é lido em tempo de import — ver
    `get_settings`."""

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    #: Arquivo único do SQLite (RNF1). Exportado pelo `mise.toml`.
    database_url: str

    #: `allow_credentials = False` e todos os métodos e headers (§10.4). Não há
    #: autenticação (RNF6), então não há cookie a proteger.
    cors_origins: tuple[str, ...] = DEFAULT_CORS_ORIGINS

    #: Eco do SQL no stderr. Útil ao depurar uma consulta, nunca ligado por
    #: default.
    sql_echo: bool = False


@lru_cache
def get_settings() -> Settings:
    """Instância única.

    O cache não é micro-otimização: é o que faz `create_app()` poder rodar em
    tempo de import (o `uvicorn` importa `main:app`) sem ler o ambiente antes
    de a primeira requisição chegar — quem lê é a dependência do §5, e nos
    testes ela é substituída.
    """
    return Settings()  # type: ignore[call-arg]
