"""A aplicação Typer (§4.3).

`cli` é montada no import, e isso é seguro: declarar comando não lê ambiente
nem abre banco — quem lê as configurações é `deps.ports()`, dentro do comando.
É a mesma promessa que o `--factory` do uvicorn faz do outro lado (ver
`http/main.py`).
"""

import typer

from app.adapters.inbound.cli import snapshot

cli = typer.Typer(
    name="pauta",
    help="Ferramentas de linha de comando do Pauta.",
    no_args_is_help=True,
    add_completion=False,
)
cli.add_typer(snapshot.cli, name="snapshot")
