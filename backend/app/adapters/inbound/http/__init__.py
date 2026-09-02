"""Borda HTTP (§8).

`main.py` monta a aplicação, `deps.py` faz o wiring, `schemas/` tem os modelos
Pydantic da borda e `routers/` tem um módulo por recurso do §8.

O Pydantic vive **só** aqui: os use cases falam em DTO da `application/`, e é o
schema que traduz JSON para DTO na entrada e DTO para JSON na saída.
"""
