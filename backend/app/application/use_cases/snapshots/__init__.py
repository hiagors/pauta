"""Export e import do snapshot (§9).

Os dois use cases da Fase 5. Nenhum dos dois sabe em que formato o snapshot é
escrito nem de onde ele é lido: isso é `SnapshotWriter` e `SnapshotReader`,
implementados em `adapters/outbound/snapshot/`.
"""
