/* Cálculos da tela de planejamento.
 *
 * Tudo aqui é função pura sobre o que `GET /planning/grid` devolveu — nenhuma
 * chamada de rede, nenhum React. É de propósito: a lógica que erra em silêncio
 * (o quanto uma barra ocupa, o que sobra ao mover, como a lista ordena) fica
 * testável sem DOM, e o componente vira só desenho.
 *
 * O backend já consolidou as barras e já resolveu a cor (§8). O que falta é
 * traduzir isso para a geometria da grade e para as linhas da lista.
 */
import type { GridOut, Schemas } from './api';

export type GridBar = Schemas['GridBarOut'];
export type GridSprint = Schemas['GridSprintOut'];
export type Priority = Schemas['Priority'];
export type InitiativeStatus = Schemas['InitiativeStatus'];

/** Intervalo fechado de sprints, do jeito que o §8 fala. */
export interface SprintRange {
  readonly from: number;
  readonly to: number;
}

/* -------------------------------------------------------------------------
 * Geometria da grade
 * ---------------------------------------------------------------------- */

/**
 * Um pedaço de uma linha: ou uma barra ocupando várias colunas, ou uma célula
 * vazia ocupando uma.
 *
 * A linha é montada como uma sequência destes, e não como uma célula por
 * sprint com barras por cima: assim o CSS Grid resolve o `span` sozinho e não
 * há posicionamento absoluto para sair do lugar quando a fonte muda de tamanho.
 */
export type RowSegment =
  | { readonly kind: 'bar'; readonly bar: GridBar; readonly span: number; readonly key: string }
  | { readonly kind: 'empty'; readonly sprintNumber: number; readonly key: string };

/**
 * Fatia a janela de sprints nos segmentos de uma linha.
 *
 * As barras já vêm sem sobreposição (RN8) e recortadas na janela, mas a função
 * não confia nisso: ela pergunta, sprint a sprint, quem cobre aquela coluna.
 */
export function rowSegments(
  bars: readonly GridBar[],
  sprintNumbers: readonly number[],
): RowSegment[] {
  const segments: RowSegment[] = [];
  let index = 0;
  while (index < sprintNumbers.length) {
    const number = sprintNumbers[index]!;
    const bar = bars.find(
      (candidate) =>
        candidate.from_sprint_number <= number && number <= candidate.to_sprint_number,
    );
    if (!bar) {
      segments.push({ kind: 'empty', sprintNumber: number, key: `vazio-${number}` });
      index += 1;
      continue;
    }
    let span = 0;
    while (index + span < sprintNumbers.length) {
      const next = sprintNumbers[index + span]!;
      if (next < bar.from_sprint_number || next > bar.to_sprint_number) break;
      span += 1;
    }
    segments.push({
      kind: 'bar',
      bar,
      span,
      key: `barra-${bar.assignee.id}-${bar.from_sprint_number}-${bar.to_sprint_number}`,
    });
    index += span;
  }
  return segments;
}

/* -------------------------------------------------------------------------
 * Mover, estender e remover
 * ---------------------------------------------------------------------- */

/** Mover preserva o comprimento: arrastar a barra, não redimensioná-la. */
export function movedRange(bar: GridBar, newFrom: number): SprintRange {
  const length = bar.to_sprint_number - bar.from_sprint_number;
  return { from: newFrom, to: newFrom + length };
}

/** Estender preserva o começo. Um valor menor que o fim atual encolhe — o
 * diálogo mostra o intervalo resultante antes de confirmar. */
export function extendedRange(bar: GridBar, newTo: number): SprintRange {
  return { from: bar.from_sprint_number, to: newTo };
}

/**
 * O que sobra do intervalo antigo depois de aplicar o novo — em até dois
 * pedaços contíguos, um de cada lado.
 *
 * É isto que faz "Mover" funcionar sem endpoint de mover: cria-se o intervalo
 * novo primeiro (idempotente, RN1) e só depois se apaga a sobra. Na ordem
 * inversa, um erro no meio deixaria a iniciativa sem alocação nenhuma.
 */
export function rangeLeftovers(origin: SprintRange, next: SprintRange): SprintRange[] {
  if (next.to < origin.from || next.from > origin.to) return [{ ...origin }];
  const leftovers: SprintRange[] = [];
  if (origin.from < next.from) leftovers.push({ from: origin.from, to: next.from - 1 });
  if (origin.to > next.to) leftovers.push({ from: next.to + 1, to: origin.to });
  return leftovers;
}

/* -------------------------------------------------------------------------
 * A visão de lista
 * ---------------------------------------------------------------------- */

/** Uma linha da tabela do §10.3: projeto, iniciativa, camada, prioridade,
 * responsável, sprint inicial, sprint final, status. */
export interface ListRow {
  readonly key: string;
  readonly projectId: string;
  readonly projectName: string;
  readonly projectColor: string;
  readonly isCapacityReserve: boolean;
  readonly initiativeId: string;
  readonly initiativeName: string;
  readonly layer: string | null;
  readonly priority: Priority;
  readonly status: InitiativeStatus;
  readonly assigneeKind: Schemas['AssigneeKind'] | null;
  readonly assigneeName: string | null;
  readonly fromSprint: number | null;
  readonly toSprint: number | null;
}

/**
 * Uma linha por barra, não por iniciativa.
 *
 * Uma iniciativa que troca de responsável no meio do trimestre tem duas barras
 * e vira duas linhas: as colunas "responsável", "sprint inicial" e "sprint
 * final" são de uma barra, e espremer duas numa linha só mentiria sobre uma
 * delas.
 */
export function listRows(grid: GridOut): ListRow[] {
  const rows: ListRow[] = [];
  for (const group of grid.groups) {
    for (const row of group.rows) {
      const base = {
        projectId: group.project.id,
        projectName: group.project.name,
        projectColor: group.project.color,
        isCapacityReserve: group.project.is_capacity_reserve,
        initiativeId: row.initiative.id,
        initiativeName: row.initiative.name,
        layer: row.initiative.layer,
        priority: row.initiative.priority,
        status: row.initiative.status,
      };
      if (row.bars.length === 0) {
        rows.push({
          ...base,
          key: row.initiative.id,
          assigneeKind: null,
          assigneeName: null,
          fromSprint: null,
          toSprint: null,
        });
        continue;
      }
      for (const bar of row.bars) {
        rows.push({
          ...base,
          key: `${row.initiative.id}-${bar.from_sprint_number}-${bar.assignee.id}`,
          assigneeKind: bar.assignee.kind,
          assigneeName: bar.assignee.name,
          fromSprint: bar.from_sprint_number,
          toSprint: bar.to_sprint_number,
        });
      }
    }
  }
  return rows;
}

/** As colunas ordenáveis da lista. */
export type ListSortKey =
  | 'project'
  | 'initiative'
  | 'layer'
  | 'priority'
  | 'assignee'
  | 'from'
  | 'to'
  | 'status';

export type SortDirection = 'asc' | 'desc';

/** Alta primeiro. O mesmo `rank` que o backend usa para ordenar as linhas. */
const PRIORITY_RANK: Record<Priority, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };

/** Ordem de leitura do fluxo, não alfabética: backlog no começo, fim no fim. */
const STATUS_RANK: Record<InitiativeStatus, number> = {
  BACKLOG: 0,
  PLANNED: 1,
  IN_PROGRESS: 2,
  DEPRIORITIZED: 3,
  DONE: 4,
  CANCELLED: 5,
};

/** Nome próprio em português ordena por `localeCompare`: sem isso "Ávila" cai
 * depois de "Zuleica". */
const collator = new Intl.Collator('pt-BR', { sensitivity: 'base', numeric: true });

function valueOf(row: ListRow, key: ListSortKey): string | number | null {
  switch (key) {
    case 'project':
      return row.projectName;
    case 'initiative':
      return row.initiativeName;
    case 'layer':
      return row.layer;
    case 'priority':
      return PRIORITY_RANK[row.priority];
    case 'assignee':
      return row.assigneeName;
    case 'from':
      return row.fromSprint;
    case 'to':
      return row.toSprint;
    case 'status':
      return STATUS_RANK[row.status];
  }
}

/**
 * Ordena sem mutar, com nulos **sempre por último**.
 *
 * Nulo por último nas duas direções é a mesma regra que o §8 fixa para o
 * `order_by=size` do backlog: inverter a ordem é sobre os valores conhecidos,
 * e "sem camada" não é nem o maior nem o menor.
 */
export function sortListRows(
  rows: readonly ListRow[],
  key: ListSortKey,
  direction: SortDirection,
): ListRow[] {
  const factor = direction === 'asc' ? 1 : -1;
  return [...rows].sort((left, right) => {
    const a = valueOf(left, key);
    const b = valueOf(right, key);
    if (a === null && b === null) return collator.compare(left.initiativeName, right.initiativeName);
    if (a === null) return 1;
    if (b === null) return -1;
    const comparison =
      typeof a === 'number' && typeof b === 'number'
        ? a - b
        : collator.compare(String(a), String(b));
    if (comparison !== 0) return comparison * factor;
    // Desempate estável e legível: duas linhas iguais na coluna ordenada
    // continuam na mesma ordem em qualquer navegador.
    return collator.compare(left.initiativeName, right.initiativeName);
  });
}

/* -------------------------------------------------------------------------
 * Regras que a UI precisa saber
 * ---------------------------------------------------------------------- */

/** RN7: `DONE` e `CANCELLED` não aceitam nova alocação. A grade esconde o `+`
 * nessas linhas em vez de oferecer um botão que só sabe devolver 422. */
export function acceptsAllocation(status: InitiativeStatus): boolean {
  return status !== 'DONE' && status !== 'CANCELLED';
}
