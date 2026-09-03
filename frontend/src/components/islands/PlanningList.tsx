import type { GridOut } from '../../lib/api';
import { ASSIGNEE_KIND_LABEL } from '../../lib/format';
import {
  listRows,
  sortListRows,
  type ListSortKey,
  type SortDirection,
} from '../../lib/planning';
import { PriorityLozenge, StatusLozenge } from '../ui/Lozenge';
import { TBody, THead, Table, Td, Th, Tr } from '../ui/Table';
import { cx } from '../ui/cx';

/**
 * A visão de lista do §10.3.
 *
 * Lê a **mesma** resposta da grade. Nada de um segundo endpoint: o
 * `planning/grid` já traz projeto, iniciativa, camada, prioridade, status e as
 * barras — e barra é exatamente "responsável, sprint inicial, sprint final".
 * Alternar Grade/Lista, portanto, não custa uma requisição.
 */

interface Column {
  readonly key: ListSortKey;
  readonly label: string;
  /** Números alinham à direita; texto, à esquerda. */
  readonly numeric?: boolean;
}

const COLUMNS: readonly Column[] = [
  { key: 'project', label: 'Projeto' },
  { key: 'initiative', label: 'Iniciativa' },
  { key: 'layer', label: 'Camada' },
  { key: 'priority', label: 'Prioridade' },
  { key: 'assignee', label: 'Responsável' },
  { key: 'from', label: 'Sprint inicial', numeric: true },
  { key: 'to', label: 'Sprint final', numeric: true },
  { key: 'status', label: 'Status' },
];

export interface PlanningListProps {
  readonly grid: GridOut;
  readonly sort: ListSortKey;
  readonly direction: SortDirection;
  readonly onSort: (key: ListSortKey) => void;
}

export function PlanningList({ grid, sort, direction, onSort }: PlanningListProps) {
  const rows = sortListRows(listRows(grid), sort, direction);

  return (
    <div className="max-h-[70dvh] overflow-auto rounded-md border border-border bg-surface">
      <Table>
        <THead>
          <tr>
            {COLUMNS.map((column) => {
              const active = column.key === sort;
              return (
                <Th
                  key={column.key}
                  // `aria-sort` é o que conta a ordenação para quem não vê a
                  // setinha; a seta é o reforço visual, não a informação.
                  aria-sort={
                    active ? (direction === 'asc' ? 'ascending' : 'descending') : 'none'
                  }
                  className={cx('p-0', column.numeric && 'text-right')}
                >
                  <button
                    type="button"
                    onClick={() => onSort(column.key)}
                    className={cx(
                      'flex h-row w-full items-center gap-1 px-3 hover:text-text',
                      column.numeric && 'justify-end',
                      active && 'text-text',
                    )}
                  >
                    {column.label}
                    <span aria-hidden className={cx(!active && 'invisible')}>
                      {direction === 'asc' ? '↑' : '↓'}
                    </span>
                  </button>
                </Th>
              );
            })}
          </tr>
        </THead>
        <TBody>
          {rows.map((row) => (
            <Tr key={row.key}>
              <Td>
                <span className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className="size-3 shrink-0 rounded-sm"
                    style={{ backgroundColor: row.projectColor }}
                  />
                  <span className="truncate">{row.projectName}</span>
                  {row.isCapacityReserve && (
                    <span className="text-11 text-text-subtle">(reserva)</span>
                  )}
                </span>
              </Td>
              <Td className="max-w-[280px] truncate" title={row.initiativeName}>
                {row.initiativeName}
              </Td>
              <Td className="text-text-subtle">{row.layer ?? '—'}</Td>
              <Td>
                <PriorityLozenge priority={row.priority} />
              </Td>
              <Td>
                {row.assigneeName ? (
                  <span
                    title={`${ASSIGNEE_KIND_LABEL[row.assigneeKind!]}: ${row.assigneeName}`}
                  >
                    {row.assigneeName}
                  </span>
                ) : (
                  <span className="text-text-subtle">—</span>
                )}
              </Td>
              <Td className="text-right tabular-nums">{row.fromSprint ?? '—'}</Td>
              <Td className="text-right tabular-nums">{row.toSprint ?? '—'}</Td>
              <Td>
                <StatusLozenge status={row.status} />
              </Td>
            </Tr>
          ))}
        </TBody>
      </Table>
      <p className="m-0 border-t border-border px-3 py-2 text-11 text-text-subtle">
        Uma linha por trecho contínuo: a iniciativa que troca de responsável no meio da
        janela aparece mais de uma vez, uma linha por barra.
      </p>
    </div>
  );
}
