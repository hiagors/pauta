"""Portas que a aplicação declara, e que o domínio não pode declarar.

`domain/ports/` é o lugar de toda porta cujo conceito é do negócio: o
repositório de um agregado, o relógio, o banco inteiro (`SnapshotStore`).
Nenhuma delas fala de arquivo, de rede ou de processo.

`SnapshotWriter` e `SnapshotReader` falam. Elas trocam `pathlib.Path`, e
`pathlib` é stdlib — a regra literal do §5 não era violada e o teste de
varredura de import passava. Mas o que entrou no domínio foi o **conceito**
"sistema de arquivos": a única implementação concebível dessas portas é um
diretório local, e o `Path` vazava daqui para `application/dto/snapshots.py` e
de lá para o schema HTTP.

Exportar o plano para uma pasta é caso de uso (§9), não regra de negócio. A
porta mora onde o caso de uso mora.
"""
