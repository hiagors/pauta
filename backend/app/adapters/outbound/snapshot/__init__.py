"""Snapshot em JSON e Markdown (§9).

O banco é a fonte da verdade; estes arquivos são saída (D5), com uma exceção:
a restauração da RNF4 lê de volta o JSON que este mesmo pacote escreveu.

- `codec.py` — a forma de cada linha, nas duas direções;
- `json_writer.py` — os oito arquivos de entidade e o `meta.json`;
- `markdown_writer.py` — `plan-sprint-N.md` e `plan-grid.md`;
- `writer.py` — a porta `SnapshotWriter`, que é os dois writers juntos;
- `reader.py` — a porta `SnapshotReader`;
- `debounce.py` — o debounce de 5 segundos da RNF3.
"""
