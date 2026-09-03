import { describe, expect, it } from 'vitest';
import type { GridOut } from '../src/lib/api';
import {
  acceptsAllocation,
  extendedRange,
  listRows,
  movedRange,
  rangeLeftovers,
  rowSegments,
  sortListRows,
  type GridBar,
} from '../src/lib/planning';

function bar(from: number, to: number, name = 'Alfa', kind: 'squad' | 'member' = 'squad'): GridBar {
  return {
    assignee: { kind, id: `${kind}-${name}`, name },
    from_sprint_number: from,
    to_sprint_number: to,
    allocation_ids: [],
  };
}

const WINDOW = [18, 19, 20, 21, 22];

describe('rowSegments', () => {
  it('cobre a janela inteira quando não há barra', () => {
    const segments = rowSegments([], WINDOW);
    expect(segments).toHaveLength(5);
    expect(segments.every((segment) => segment.kind === 'empty')).toBe(true);
  });

  it('funde as colunas de uma barra num segmento com o span certo', () => {
    const segments = rowSegments([bar(18, 20)], WINDOW);
    expect(segments.map((s) => (s.kind === 'bar' ? `bar:${s.span}` : `vazio:${s.sprintNumber}`))).toEqual([
      'bar:3',
      'vazio:21',
      'vazio:22',
    ]);
  });

  it('a soma dos spans é o tamanho da janela — nem coluna a mais, nem a menos', () => {
    const segments = rowSegments([bar(19, 19), bar(21, 22, 'Bruno', 'member')], WINDOW);
    const total = segments.reduce((sum, s) => sum + (s.kind === 'bar' ? s.span : 1), 0);
    expect(total).toBe(WINDOW.length);
  });

  it('uma pausa no meio abre duas barras separadas', () => {
    const segments = rowSegments([bar(18, 18), bar(21, 21)], WINDOW);
    expect(segments.map((s) => s.kind)).toEqual(['bar', 'empty', 'empty', 'bar', 'empty']);
  });

  it('recorta a barra que começa antes da janela', () => {
    const segments = rowSegments([bar(10, 19)], WINDOW);
    expect(segments[0]).toMatchObject({ kind: 'bar', span: 2 });
  });

  it('recorta a barra que termina depois da janela', () => {
    const segments = rowSegments([bar(21, 40)], WINDOW);
    expect(segments.at(-1)).toMatchObject({ kind: 'bar', span: 2 });
  });
});

describe('movedRange e extendedRange', () => {
  it('mover preserva o comprimento', () => {
    expect(movedRange(bar(18, 20), 21)).toEqual({ from: 21, to: 23 });
  });

  it('mover uma barra de uma sprint só continua com uma sprint', () => {
    expect(movedRange(bar(19, 19), 22)).toEqual({ from: 22, to: 22 });
  });

  it('estender preserva o começo', () => {
    expect(extendedRange(bar(18, 20), 24)).toEqual({ from: 18, to: 24 });
  });
});

describe('rangeLeftovers', () => {
  it('mover para a frente deixa a sobra atrás', () => {
    expect(rangeLeftovers({ from: 18, to: 20 }, { from: 20, to: 22 })).toEqual([
      { from: 18, to: 19 },
    ]);
  });

  it('mover para trás deixa a sobra na frente', () => {
    expect(rangeLeftovers({ from: 18, to: 20 }, { from: 16, to: 18 })).toEqual([
      { from: 19, to: 20 },
    ]);
  });

  it('encolher pelos dois lados deixa duas sobras', () => {
    expect(rangeLeftovers({ from: 18, to: 24 }, { from: 20, to: 21 })).toEqual([
      { from: 18, to: 19 },
      { from: 22, to: 24 },
    ]);
  });

  it('estender não deixa sobra nenhuma', () => {
    expect(rangeLeftovers({ from: 18, to: 20 }, { from: 18, to: 25 })).toEqual([]);
  });

  it('mover para longe apaga o intervalo antigo inteiro', () => {
    expect(rangeLeftovers({ from: 18, to: 20 }, { from: 30, to: 32 })).toEqual([
      { from: 18, to: 20 },
    ]);
  });

  it('o mesmo intervalo não apaga nada', () => {
    expect(rangeLeftovers({ from: 18, to: 20 }, { from: 18, to: 20 })).toEqual([]);
  });
});

/* ------------------------------------------------------------------------ */

function grid(): GridOut {
  return {
    sprints: [],
    alerts_by_sprint: {},
    groups: [
      {
        project: { id: 'p1', name: 'Aurora', color: '#0052CC', is_capacity_reserve: false },
        rows: [
          {
            initiative: {
              id: 'i1',
              name: 'Catálogo V1',
              layer: null,
              status: 'IN_PROGRESS',
              priority: 'HIGH',
            },
            bars: [bar(18, 20), bar(22, 22, 'Bruno', 'member')],
          },
          {
            initiative: {
              id: 'i2',
              name: 'Serviço de Envio',
              layer: 'Backend',
              status: 'PLANNED',
              priority: 'MEDIUM',
            },
            bars: [bar(19, 19, 'Beta')],
          },
        ],
      },
    ],
  };
}

describe('listRows', () => {
  it('gera uma linha por barra, não por iniciativa', () => {
    const rows = listRows(grid());
    expect(rows).toHaveLength(3);
    expect(rows.filter((row) => row.initiativeId === 'i1')).toHaveLength(2);
  });

  it('cada linha carrega o intervalo e o responsável da própria barra', () => {
    const [first, second] = listRows(grid());
    expect(first).toMatchObject({ assigneeName: 'Alfa', fromSprint: 18, toSprint: 20 });
    expect(second).toMatchObject({ assigneeName: 'Bruno', fromSprint: 22, toSprint: 22 });
  });

  it('iniciativa sem barra vira uma linha com os campos de alocação nulos', () => {
    const source = grid();
    source.groups[0]!.rows[1]!.bars = [];
    const row = listRows(source).find((candidate) => candidate.initiativeId === 'i2');
    expect(row).toMatchObject({ assigneeName: null, fromSprint: null, toSprint: null });
  });
});

describe('sortListRows', () => {
  const rows = listRows(grid());

  it('ordena prioridade por peso, não em ordem alfabética', () => {
    const ordered = sortListRows(rows, 'priority', 'asc').map((row) => row.priority);
    expect(ordered[0]).toBe('HIGH');
    expect(ordered.at(-1)).toBe('MEDIUM');
  });

  it('inverte a direção', () => {
    const asc = sortListRows(rows, 'from', 'asc').map((row) => row.fromSprint);
    const desc = sortListRows(rows, 'from', 'desc').map((row) => row.fromSprint);
    expect(asc).toEqual([18, 19, 22]);
    expect(desc).toEqual([22, 19, 18]);
  });

  it('deixa os nulos por último nas duas direções', () => {
    const withNull = [...rows, { ...rows[0]!, key: 'x', layer: null, initiativeName: 'Zeta' }];
    for (const direction of ['asc', 'desc'] as const) {
      const layers = sortListRows(withNull, 'layer', direction).map((row) => row.layer);
      expect(layers.at(-1)).toBeNull();
    }
  });

  it('não muta o array de entrada', () => {
    const before = [...rows];
    sortListRows(rows, 'initiative', 'desc');
    expect(rows).toEqual(before);
  });

  it('ordena nome com acento pelo alfabeto português', () => {
    const base = rows[0]!;
    const names = sortListRows(
      [
        { ...base, key: 'a', initiativeName: 'Zebra' },
        { ...base, key: 'b', initiativeName: 'Ávila' },
        { ...base, key: 'c', initiativeName: 'Base' },
      ],
      'initiative',
      'asc',
    ).map((row) => row.initiativeName);
    expect(names).toEqual(['Ávila', 'Base', 'Zebra']);
  });
});

describe('acceptsAllocation', () => {
  it('RN7: só DONE e CANCELLED recusam', () => {
    expect(acceptsAllocation('BACKLOG')).toBe(true);
    expect(acceptsAllocation('PLANNED')).toBe(true);
    expect(acceptsAllocation('IN_PROGRESS')).toBe(true);
    expect(acceptsAllocation('DEPRIORITIZED')).toBe(true);
    expect(acceptsAllocation('DONE')).toBe(false);
    expect(acceptsAllocation('CANCELLED')).toBe(false);
  });
});
