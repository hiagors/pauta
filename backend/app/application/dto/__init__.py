"""DTOs de entrada e saída dos use cases.

Dataclasses da stdlib, nunca modelos Pydantic: o Pydantic vive só nos schemas
de borda HTTP (§4.1). O que atravessa esta fronteira é DTO ou entidade de
domínio — nunca `Session`, `Request` ou modelo SQLAlchemy (§5).
"""
