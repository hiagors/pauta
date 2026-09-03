"""Engine e sessões do SQLite (RNF1).

Duas responsabilidades, e só duas: criar a engine com
`PRAGMA foreign_keys=ON` em **cada** conexão, e devolver a fábrica de sessões.

O `PRAGMA` é por conexão, não por banco: o SQLite nasce com chave estrangeira
desligada e cada nova conexão volta ao default. Por isso ele é registrado como
listener do evento `connect`, e não executado uma vez na criação da engine. A
função `pauta_casefold` entra pelo mesmo caminho, e pelo mesmo motivo.

Quem abre e fecha a transação é o adapter de entrada — a requisição HTTP na
Fase 4, o comando da CLI na Fase 5. Repositório não faz `commit`: ele faz
`flush`, para que a leitura seguinte dentro do mesmo use case veja o que a
anterior escreveu, e nada mais.
"""

from sqlite3 import Connection as SQLite3Connection
from typing import Any

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

#: Nome da função de dobra de caixa registrada em cada conexão. Ver
#: `_register_casefold` e `repositories/filters.contains_text`.
CASEFOLD = "pauta_casefold"


def make_engine(url: str, *, echo: bool = False, **options: Any) -> Engine:
    """Engine para a `DATABASE_URL` do `mise.toml` (arquivo único em `data/`).

    `options` vai direto para o `create_engine`. Existe por um caso concreto: a
    suíte de HTTP roda em `:memory:`, que exige `StaticPool` e
    `check_same_thread=False` — um banco em memória vive dentro da conexão, e
    um pool que abre a segunda conexão abre um banco vazio. Esse caso tem de
    passar por aqui, e não montar a engine à mão, para ganhar o `PRAGMA` e o
    `pauta_casefold` como qualquer outra.
    """
    engine = create_engine(url, echo=echo, **options)
    event.listen(engine, "connect", _prepare_connection)
    return engine


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    """`expire_on_commit=False` porque a entidade que o use case devolveu já é
    uma cópia: expirar o modelo depois do commit só provocaria um `SELECT` a
    mais para ninguém ler."""
    return sessionmaker(bind=engine, expire_on_commit=False)


def _prepare_connection(dbapi_connection: Any, _record: Any) -> None:
    """O `isinstance` evita preparar uma conexão que não é SQLite, caso um
    adapter futuro use outro driver."""
    if not isinstance(dbapi_connection, SQLite3Connection):
        return
    _enable_foreign_keys(dbapi_connection)
    _register_casefold(dbapi_connection)


def _enable_foreign_keys(connection: SQLite3Connection) -> None:
    """RNF1."""
    cursor = connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def _register_casefold(connection: SQLite3Connection) -> None:
    """Dá ao SQLite o `casefold()` do Python, para a busca do `?q=`.

    O `lower()` nativo do SQLite só dobra ASCII: sem isso, procurar
    "CATÁLOGO" não acha "Catálogo", e o repositório de verdade divergiria do
    fake — que usa `casefold()` — justamente nos nomes em português, que são
    todos os nomes deste sistema.

    O custo é que a comparação não usa índice. Num banco local de uso
    individual, com dezenas de projetos, isso não é custo nenhum.
    """
    connection.create_function(CASEFOLD, 1, _casefold, deterministic=True)


def _casefold(value: str | None) -> str | None:
    return None if value is None else value.casefold()
