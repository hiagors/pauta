"""Peças compartilhadas pelos schemas da borda.

Três bases, e a razão de cada uma:

- `InputModel` recusa campo desconhecido. Um `is_capacity_reserv` escrito
  errado que o servidor aceita em silêncio é pior que um 422.
- `PatchModel` resolve o "ausente ≠ nulo" do §8 pelo `model_fields_set`: só o
  que o pedido realmente mandou é traduzido para o DTO, e o resto vira `UNSET`.
- `OutputModel` lê os DTOs por atributo, o que permite `model_validate` direto
  sobre a dataclass que o use case devolveu, sem passo intermediário.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict, GetJsonSchemaHandler
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema

from app.application.dto.common import UNSET, Patch


class InputModel(BaseModel):
    """Corpo de requisição. Campo a mais é erro, não é ignorado."""

    model_config = ConfigDict(extra="forbid")


class PatchModel(InputModel):
    """Corpo de `PATCH`: o que não vem não é alterado.

    Os defaults declarados nos campos **nunca são lidos** — `patch()` só
    devolve o valor quando o campo veio no pedido. Eles existem para que o
    tipo do campo continue honesto: onde o domínio não aceita nulo, o campo
    não é anulável, e `{"name": null}` é 422 em vez de virar `None` lá dentro.
    """

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        """Publica todo campo como opcional e sem default.

        Não é cosmético: o front não redigita tipo, ele gera do OpenAPI
        (§10.5). O `openapi-typescript` trata propriedade com `default` como
        não-opcional, e o schema sairia dizendo que um `PATCH` precisa mandar
        todos os campos — o contrário de um pedido parcial. Os defaults do
        Python continuam lá, como placeholder de tipo que `patch()` nunca lê.
        """
        schema = handler.resolve_ref_schema(handler(core_schema))
        schema.pop("required", None)
        for field in schema.get("properties", {}).values():
            field.pop("default", None)
        return schema

    def patch(self, field: str) -> Patch[Any]:
        if field not in self.model_fields_set:
            return UNSET
        return getattr(self, field)


class OutputModel(BaseModel):
    """Corpo de resposta, montado a partir do DTO do use case."""

    model_config = ConfigDict(from_attributes=True)


class ErrorBody(OutputModel):
    """O corpo do erro do §8.

    `code` é o contrato estável — é por ele que a UI decide a mensagem, não
    pelo texto. `details` carrega os dados que o aviso usa (qual sprint, qual
    projeto), sempre em primitivos.
    """

    code: str
    message: str
    details: dict[str, Any] = {}


class ErrorEnvelope(OutputModel):
    """`{ "error": { "code": ..., "message": ..., "details": {} } }` (§8)."""

    error: ErrorBody
