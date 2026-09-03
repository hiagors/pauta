import { useState } from 'react';
import type { GridOut } from '../../lib/api';
import {
  ALERT_TYPE_LABEL,
  formatDate,
  formatDateRange,
  readableTextOn,
} from '../../lib/format';
import {
  acceptsAllocation,
  rowSegments,
  type GridBar,
  type SprintRange,
} from '../../lib/planning';
import { PriorityLozenge } from '../ui/Lozenge';
import { Popover, PopoverItem } from '../ui/Popover';
import { cx } from '../ui/cx';
import type { AllocationSubject, BarAction } from './AllocationDialog';

/**
 * A grade do §10.3: linhas são iniciativas agrupadas por projeto, colunas são
 * sprints, e a barra colorida cobre o intervalo.
 *
 * É um `grid` CSS único, do cabeçalho à última linha. A coluna da esquerda é
 * `sticky` e as colunas de sprint rolam na horizontal; a barra é um item que
 * ocupa `span` colunas, e não um bloco posicionado por cima — o navegador
 * resolve a largura, então nada sai do lugar quando a fonte muda de tamanho.
 *
 * Arrastar não foi implementado. O §10.3 diz que a grade legível e confiável
 * vale mais que a arrastável e instável, e que o caminho é o popover da barra.
 */

/** Largura da coluna congelada e de cada coluna de sprint, em pixels. As duas
 * viram `grid-template-columns` e a conta da faixa da sprint atual. */
const LEAD_WIDTH = 320;
const COLUMN_WIDTH = 88;

/**
 * As listras da reserva de capacidade (§10.2), em um lugar só.
 *
 * A barra da grade e a legenda do cabeçalho precisam do mesmo desenho: uma
 * legenda que não é exatamente o que está na tela é pior que nenhuma legenda.
 */
export const CAPACITY_RESERVE_STRIPES =
  'repeating-linear-gradient(45deg, rgba(255,255,255,.35) 0 4px, transparent 4px 9px)';

export interface PlanningGridProps {
  readonly grid: GridOut;
  readonly onAllocate: (subject: AllocationSubject, range: SprintRange) => void;
  readonly onBarAction: (
    action: BarAction,
    subject: AllocationSubject,
    bar: GridBar,
  ) => void;
}

export function PlanningGrid({ grid, onAllocate, onBarAction }: PlanningGridProps) {
  const [openBar, setOpenBar] = useState<string | null>(null);
  const sprintNumbers = grid.sprints.map((sprint) => sprint.number);
  const currentIndex = grid.sprints.findIndex((sprint) => sprint.is_current);
  // A última faixa é sobra: as colunas de sprint têm largura fixa, e sem ela as
  // linhas parariam no meio do cartão quando a janela tivesse poucas sprints.
  const template = `${LEAD_WIDTH}px repeat(${grid.sprints.length}, ${COLUMN_WIDTH}px) minmax(0, 1fr)`;

  return (
    <div className="max-h-[70dvh] overflow-auto rounded-md border border-border bg-surface">
      <div className="relative w-max min-w-full">
        {currentIndex >= 0 && (
          // A marcação da sprint atual (RN12) é uma faixa vertical de verdade,
          // atrás de tudo: tingir só o cabeçalho sumiria assim que a coluna
          // saísse do topo da rolagem.
          <div
            aria-hidden
            className="pointer-events-none absolute inset-y-0 z-0 bg-primary-soft/60"
            style={{
              left: LEAD_WIDTH + currentIndex * COLUMN_WIDTH,
              width: COLUMN_WIDTH,
            }}
          />
        )}

        <div className="relative z-0 grid" style={{ gridTemplateColumns: template }}>
          {/* cabeçalho */}
          <div className="sticky top-0 left-0 z-30 flex h-12 items-end border-r border-b border-border bg-surface px-3 pb-2 text-12 font-semibold text-text-subtle">
            Iniciativa
          </div>
          {grid.sprints.map((sprint) => {
            const alerts = grid.alerts_by_sprint[String(sprint.number)] ?? [];
            return (
              <div
                key={sprint.id}
                title={`Sprint ${sprint.number} · ${formatDateRange(sprint.start_date, sprint.end_date)}`}
                className={cx(
                  'sticky top-0 z-20 flex h-12 flex-col items-center justify-center gap-px',
                  'border-r border-b border-border text-12',
                  sprint.is_current ? 'bg-primary-soft font-semibold text-primary' : 'bg-surface',
                )}
              >
                <span className="flex items-center gap-1">
                  {sprint.number}
                  {/* O ícone resume a sprint inteira: `alerts_by_sprint` não é
                      afetado pelos filtros, de propósito (§8). */}
                  {alerts.length > 0 && (
                    <svg className="icon size-3 text-danger" role="img">
                      <title>
                        {`Alertas na Sprint ${sprint.number}: ${alerts
                          .map((type) => ALERT_TYPE_LABEL[type])
                          .join(', ')}`}
                      </title>
                      <use href="#icon-warning" />
                    </svg>
                  )}
                </span>
                <span className="text-11 font-normal text-text-subtle">
                  {formatDate(sprint.start_date).slice(0, 5)}
                </span>
              </div>
            );
          })}

          <div className="sticky top-0 z-20 h-12 border-b border-border bg-surface" />

          {/* grupos */}
          {grid.groups.map((group) => (
            <GroupRows
              key={group.project.id}
              group={group}
              sprintNumbers={sprintNumbers}
              openBar={openBar}
              setOpenBar={setOpenBar}
              onAllocate={onAllocate}
              onBarAction={onBarAction}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

interface GroupRowsProps {
  readonly group: GridOut['groups'][number];
  readonly sprintNumbers: readonly number[];
  readonly openBar: string | null;
  readonly setOpenBar: (key: string | null) => void;
  readonly onAllocate: PlanningGridProps['onAllocate'];
  readonly onBarAction: PlanningGridProps['onBarAction'];
}

function GroupRows({
  group,
  sprintNumbers,
  openBar,
  setOpenBar,
  onAllocate,
  onBarAction,
}: GroupRowsProps) {
  const { project } = group;
  return (
    <>
      <div
        className="border-b border-border bg-neutral-soft"
        style={{ gridColumn: '1 / -1' }}
      >
        {/* O nome do projeto acompanha a rolagem horizontal: é ele que dá a
            leitura vertical do agrupamento (§10.3). */}
        <div
          className="sticky left-0 flex h-8 items-center gap-2 px-3"
          style={{ width: LEAD_WIDTH }}
        >
          <span
            aria-hidden
            className="size-3 shrink-0 rounded-sm"
            style={{ backgroundColor: project.color }}
          />
          <span className="truncate text-12 font-semibold">{project.name}</span>
          {project.is_capacity_reserve && (
            <span className="text-11 text-text-subtle">(reserva)</span>
          )}
        </div>
      </div>

      {group.rows.map((row) => {
        const subject: AllocationSubject = {
          initiativeId: row.initiative.id,
          initiativeName: row.initiative.name,
          projectName: project.name,
        };
        const allocatable = acceptsAllocation(row.initiative.status);
        return (
          <RowCells
            key={row.initiative.id}
            row={row}
            project={project}
            subject={subject}
            allocatable={allocatable}
            sprintNumbers={sprintNumbers}
            openBar={openBar}
            setOpenBar={setOpenBar}
            onAllocate={onAllocate}
            onBarAction={onBarAction}
          />
        );
      })}
    </>
  );
}

interface RowCellsProps {
  readonly row: GridOut['groups'][number]['rows'][number];
  readonly project: GridOut['groups'][number]['project'];
  readonly subject: AllocationSubject;
  readonly allocatable: boolean;
  readonly sprintNumbers: readonly number[];
  readonly openBar: string | null;
  readonly setOpenBar: (key: string | null) => void;
  readonly onAllocate: PlanningGridProps['onAllocate'];
  readonly onBarAction: PlanningGridProps['onBarAction'];
}

function RowCells({
  row,
  project,
  subject,
  allocatable,
  sprintNumbers,
  openBar,
  setOpenBar,
  onAllocate,
  onBarAction,
}: RowCellsProps) {
  const textColor = readableTextOn(project.color);
  return (
    <>
      {/* Duas linhas: o nome fica com os 320px inteiros antes de truncar, e a
          prioridade e a camada descem para a segunda. Numa linha só, o nome
          disputava a largura com o lozenge e era ele que perdia. */}
      <div
        className="sticky left-0 z-10 flex h-row flex-col justify-center border-r border-b border-border bg-surface px-3"
        title={row.initiative.name}
      >
        <span className="truncate text-14 leading-4">{row.initiative.name}</span>
        <span className="flex min-w-0 items-center gap-2 leading-4">
          <PriorityLozenge priority={row.initiative.priority} />
          {row.initiative.layer && (
            <span className="truncate text-11 text-text-subtle">
              {row.initiative.layer}
            </span>
          )}
        </span>
      </div>

      {rowSegments(row.bars, sprintNumbers).map((segment) => {
        if (segment.kind === 'empty') {
          return (
            <div
              key={segment.key}
              className="group/cell relative h-row border-r border-b border-border"
            >
              {allocatable && (
                <button
                  type="button"
                  onClick={() =>
                    onAllocate(subject, {
                      from: segment.sprintNumber,
                      to: segment.sprintNumber,
                    })
                  }
                  aria-label={`Alocar ${row.initiative.name} na Sprint ${segment.sprintNumber}`}
                  className={cx(
                    'absolute inset-1 flex items-center justify-center rounded-sm',
                    'text-16 text-text-subtle opacity-0 transition-opacity',
                    'hover:bg-primary-soft hover:text-primary',
                    'group-hover/cell:opacity-100 focus-visible:opacity-100',
                  )}
                >
                  +
                </button>
              )}
            </div>
          );
        }

        const { bar } = segment;
        const key = `${row.initiative.id}-${bar.from_sprint_number}`;
        const label = `${bar.assignee.name} · Sprints ${bar.from_sprint_number} a ${bar.to_sprint_number}`;
        return (
          <div
            key={segment.key}
            className="relative flex h-row items-center border-b border-border"
            style={{ gridColumn: `span ${segment.span}` }}
          >
            <button
              type="button"
              title={label}
              aria-label={label}
              aria-haspopup="menu"
              aria-expanded={openBar === key}
              onClick={() => setOpenBar(openBar === key ? null : key)}
              style={{
                backgroundColor: project.color,
                color: textColor,
                // Reserva de capacidade ganha listras diagonais em cima da cor
                // (§10.2) — é o que separa "reservado" de "alocado" sem gastar
                // uma segunda cor.
                backgroundImage: project.is_capacity_reserve
                  ? CAPACITY_RESERVE_STRIPES
                  : undefined,
              }}
              className="h-8 w-full truncate rounded-sm px-2 text-left text-12 font-semibold"
            >
              {bar.assignee.name}
            </button>
            <Popover
              open={openBar === key}
              onClose={() => setOpenBar(null)}
              label={`Ações da barra de ${bar.assignee.name}`}
            >
              <PopoverItem
                onClick={() => {
                  setOpenBar(null);
                  onBarAction('move', subject, bar);
                }}
              >
                Mover
              </PopoverItem>
              <PopoverItem
                onClick={() => {
                  setOpenBar(null);
                  onBarAction('extend', subject, bar);
                }}
              >
                Estender até
              </PopoverItem>
              <PopoverItem
                danger
                onClick={() => {
                  setOpenBar(null);
                  onBarAction('remove', subject, bar);
                }}
              >
                Remover
              </PopoverItem>
            </Popover>
          </div>
        );
      })}
      <div className="h-row border-b border-border" />
    </>
  );
}
