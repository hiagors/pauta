"""Tradução de exceção para o JSON de erro do §8.

Um lugar só faz essa tradução — nenhum router monta erro à mão. O mapa é o das
três bases de `domain/errors.py`, e é por isso que o domínio tem exatamente
três: o handler escolhe o código HTTP sem conhecer nenhum erro concreto.

    NotFoundError -> 404      ConflictError -> 409      DomainError -> 422

Os outros dois handlers existem para que a UI tenha **um** formato de erro para
tratar: sem eles, um corpo malformado sairia no formato do FastAPI e uma rota
inexistente no do Starlette, e o `lib/api.ts` precisaria de três caminhos.
"""

from typing import Final

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.errors import ConflictError, DomainError, NotFoundError

#: `code` do erro de corpo/query malformado, o 422 que o Pydantic levanta antes
#: de qualquer use case rodar.
VALIDATION_ERROR: Final = "VALIDATION_ERROR"

#: `code` do que o Starlette levanta sozinho: rota inexistente, método errado.
HTTP_ERROR: Final = "HTTP_ERROR"


def envelope(
    *, code: str, message: str, details: object, status_code: int
) -> JSONResponse:
    """O formato do §8, com os `details` passados pelo encoder do FastAPI."""
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": jsonable_encoder(details),
            }
        },
    )


def status_for(error: DomainError) -> int:
    """A ordem importa: as duas primeiras são subclasses da terceira."""
    if isinstance(error, NotFoundError):
        return status.HTTP_404_NOT_FOUND
    if isinstance(error, ConflictError):
        return status.HTTP_409_CONFLICT
    return status.HTTP_422_UNPROCESSABLE_CONTENT


async def handle_domain_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, DomainError)
    return envelope(
        code=exc.code,
        message=exc.message,
        details=exc.details,
        status_code=status_for(exc),
    )


async def handle_validation_error(_: Request, exc: Exception) -> JSONResponse:
    """Corpo ou query que não bate com o schema.

    `details.errors` é a lista do Pydantic, com o caminho do campo — é o que
    permite a UI apontar o campo errado em vez de dizer "dados inválidos".
    """
    assert isinstance(exc, RequestValidationError)
    return envelope(
        code=VALIDATION_ERROR,
        message="Os dados enviados não são válidos.",
        details={"errors": exc.errors()},
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )


async def handle_http_error(_: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)
    return envelope(
        code=HTTP_ERROR,
        message=str(exc.detail),
        details={},
        status_code=exc.status_code,
    )


def register(app: FastAPI) -> None:
    """Registrar em `DomainError` cobre as subclasses: o Starlette procura o
    handler subindo o `__mro__` da exceção."""
    app.add_exception_handler(DomainError, handle_domain_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.add_exception_handler(StarletteHTTPException, handle_http_error)
