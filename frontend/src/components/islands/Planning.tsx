import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import {
  api,
  type GridOut,
  type MemberOut,
  type SprintOut,
  type SquadOut,
} from '../../lib/api';
import { pluralize } from '../../lib/format';
import type { GridBar, ListSortKey, SortDirection, SprintRange } from '../../lib/planning';
import { withQuery } from '../../lib/query';
import { useUrlState } from '../../lib/url-state';
import { Button } from '../ui/Button';
import { Select } from '../ui/Select';
import { Card, EmptyState, ErrorState, Skeleton } from '../ui/States';
import { ToastProvider } from '../ui/Toast';
import { cx } from '../ui/cx';
import {
  AllocationDialog,
  BarDialog,
  type AllocationSubject,
  type BarAction,
} from './AllocationDialog';
import { CAPACITY_RESERVE_STRIPES, PlanningGrid } from './PlanningGrid';
import { PlanningList } from './PlanningList';

/**
 * A tela `/planning` (§10.3).
 *
 * É a raiz da ilha: segura o filtro, a alternância Grade|Lista e os diálogos.
 * A grade e a lista são só desenho — recebem a mesma resposta de
 * `GET /planning/grid` e não sabem nada de rede.
 *
 * O filtro mora na URL: recarregar, voltar no histórico ou mandar o link tem
 * que reproduzir a mesma tela.
 */

/** Os parâmetros da URL e o que cada um vale quando não está lá. */
const DEFAULTS = {
  view: 'grid',
  squad: '',
  member: '',
  from: '',
  to: '',
  sort: 'project',
  dir: 'asc',
} as const;

type PlanningParams = { -readonly [K in keyof typeof DEFAULTS]: string };

const BASE: PlanningParams = { ...DEFAULTS };

/** Vazio na URL significa "sem filtro"; o cliente já omite `undefined`. */
function optionalId(value: string): string | undefined {
  return value === '' ? undefined : value;
}

function optionalNumber(value: string): number | undefined {
  const parsed = Number(value);
  return value === '' || !Number.isInteger(parsed) ? undefined : parsed;
}

function Planning() {
  const [params, patch, mounted] = useUrlState<PlanningParams>(BASE);
  const [allocating, setAllocating] = useState<{
    subject: AllocationSubject;
    range: SprintRange;
  } | null>(null);
  const [barAction, setBarAction] = useState<{
    action: BarAction;
    subject: AllocationSubject;
    bar: GridBar;
  } | null>(null);

  const filters = {
    squad_id: optionalId(params.squad),
    member_id: optionalId(params.member),
    sprint_from: optionalNumber(params.from),
    sprint_to: optionalNumber(params.to),
  };

  const grid = useQuery({
    queryKey: ['planning', 'grid', filters],
    queryFn: ({ signal }) => api.getGrid(filters, signal),
    enabled: mounted,
  });

  // Os três filtros do §10.3. Ficam ativados mesmo enquanto a grade carrega:
  // desabilitar o filtro a cada refetch faria o controle piscar.
  const squads = useQuery({
    queryKey: ['squads', { active: true }],
    queryFn: ({ signal }) => api.listSquads({ active: true }, signal),
    enabled: mounted,
  });
  const members = useQuery({
    queryKey: ['members', { active: true }],
    queryFn: ({ signal }) => api.listMembers({ active: true }, signal),
    enabled: mounted,
  });
  const sprints = useQuery({
    queryKey: ['sprints', {}],
    queryFn: ({ signal }) => api.listSprints(undefined, signal),
    enabled: mounted,
  });

  const isList = params.view === 'list';

  return (
    <div className="flex flex-col gap-4">
      {grid.data && <Summary grid={grid.data} />}

      <div className="flex flex-wrap items-end justify-between gap-4">
        <Filters
          params={params}
          patch={patch}
          squads={squads.data ?? []}
          members={members.data ?? []}
          sprints={sprints.data ?? []}
        />
        <ViewToggle value={isList ? 'list' : 'grid'} onChange={(view) => patch({ view })} />
      </div>

      {!mounted || grid.isPending ? (
        <Card>
          <Skeleton lines={5} />
        </Card>
      ) : grid.isError ? (
        <Card>
          <ErrorState
            what="a grade de planejamento"
            error={grid.error}
            onRetry={() => void grid.refetch()}
          />
        </Card>
      ) : grid.data.sprints.length === 0 ? (
        <Card>
          <EmptyState
            message="Nenhuma sprint nesta janela. Cadastre sprints para abrir a grade."
            action={
              <Button variant="primary" onClick={() => window.location.assign('/sprints')}>
                Ir para Sprints
              </Button>
            }
          />
        </Card>
      ) : grid.data.groups.length === 0 ? (
        <Card>
          <EmptyState
            message={
              hasFilter(params)
                ? 'Nenhuma alocação bate com o filtro. Limpe o filtro para ver a janela inteira.'
                : 'Nenhuma iniciativa alocada nesta janela. Aloque uma iniciativa do backlog para começar a planejar.'
            }
            action={
              hasFilter(params) ? (
                <Button onClick={() => patch({ squad: '', member: '', from: '', to: '' })}>
                  Limpar filtro
                </Button>
              ) : (
                <Button variant="primary" onClick={() => window.location.assign('/backlog')}>
                  Ir para o backlog
                </Button>
              )
            }
          />
        </Card>
      ) : isList ? (
        <PlanningList
          grid={grid.data}
          sort={params.sort as ListSortKey}
          direction={params.dir as SortDirection}
          onSort={(key) =>
            patch(
              key === params.sort
                ? { dir: params.dir === 'asc' ? 'desc' : 'asc' }
                : { sort: key, dir: 'asc' },
            )
          }
        />
      ) : (
        <PlanningGrid
          grid={grid.data}
          onAllocate={(subject, range) => setAllocating({ subject, range })}
          onBarAction={(action, subject, bar) => setBarAction({ action, subject, bar })}
        />
      )}

      {allocating && (
        <AllocationDialog
          open
          onClose={() => setAllocating(null)}
          subject={allocating.subject}
          defaultRange={allocating.range}
        />
      )}
      {barAction && (
        <BarDialog
          action={barAction.action}
          onClose={() => setBarAction(null)}
          subject={barAction.subject}
          bar={barAction.bar}
        />
      )}
    </div>
  );
}

function hasFilter(params: PlanningParams): boolean {
  return Boolean(params.squad || params.member || params.from || params.to);
}

/**
 * O que a janela contém, e o que as duas marcações da grade querem dizer.
 *
 * A legenda só mostra o que está na tela: sem projeto de reserva não há listra
 * para explicar, e sem sprint atual não há faixa azul. Legenda de coisa
 * ausente é ruído, e ensina a ignorar a legenda.
 */
function Summary({ grid }: { readonly grid: GridOut }) {
  const first = grid.sprints[0];
  const last = grid.sprints[grid.sprints.length - 1];
  const hasReserve = grid.groups.some((group) => group.project.is_capacity_reserve);
  const hasCurrent = grid.sprints.some((sprint) => sprint.is_current);

  return (
    <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
      <p className="m-0 text-12 text-text-subtle">
        {pluralize(grid.groups.length, 'projeto', 'projetos')}
        {first && last && (
          <>
            {' · '}
            {first.number === last.number
              ? `Sprint ${first.number}`
              : `Sprints ${first.number} a ${last.number}`}
          </>
        )}
      </p>
      {(hasCurrent || hasReserve) && (
        <p className="m-0 flex flex-wrap items-center gap-4 text-11 text-text-subtle">
          {hasCurrent && (
            <span className="flex items-center gap-2">
              <span aria-hidden className="size-3 rounded-sm bg-primary-soft" />
              Sprint atual
            </span>
          )}
          {hasReserve && (
            <span className="flex items-center gap-2">
              <span
                aria-hidden
                className="size-3 rounded-sm bg-project-default"
                style={{ backgroundImage: CAPACITY_RESERVE_STRIPES }}
              />
              Reserva de capacidade
            </span>
          )}
        </p>
      )}
    </div>
  );
}

function ViewToggle({
  value,
  onChange,
}: {
  readonly value: 'grid' | 'list';
  readonly onChange: (view: 'grid' | 'list') => void;
}) {
  return (
    <div
      role="group"
      aria-label="Visão"
      className="inline-flex rounded-sm border border-border-strong p-px"
    >
      {(
        [
          ['grid', 'Grade'],
          ['list', 'Lista'],
        ] as const
      ).map(([key, label]) => (
        <button
          key={key}
          type="button"
          aria-pressed={value === key}
          onClick={() => onChange(key)}
          className={cx(
            'h-7 rounded-sm px-3 text-12 font-semibold',
            value === key ? 'bg-primary-soft text-primary' : 'text-text-subtle hover:text-text',
          )}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

interface FiltersProps {
  readonly params: PlanningParams;
  readonly patch: (patch: Partial<PlanningParams>) => void;
  readonly squads: readonly SquadOut[];
  readonly members: readonly MemberOut[];
  readonly sprints: readonly SprintOut[];
}

function Filters({ params, patch, squads, members, sprints }: FiltersProps) {
  const sprintOptions = sprints.map((sprint) => ({
    value: String(sprint.number),
    label: `Sprint ${sprint.number}`,
  }));
  return (
    <div className="flex flex-wrap items-end gap-3">
      <Select
        label="Squad"
        placeholder="Todas"
        value={params.squad}
        onChange={(event) => patch({ squad: event.target.value })}
        options={squads.map((squad) => ({ value: squad.id, label: squad.name }))}
      />
      <Select
        label="Pessoa"
        placeholder="Todas"
        value={params.member}
        onChange={(event) => patch({ member: event.target.value })}
        options={members.map((member) => ({
          value: member.id,
          label: member.short_name,
        }))}
      />
      <Select
        label="Da sprint"
        placeholder="Trimestre"
        value={params.from}
        onChange={(event) => patch({ from: event.target.value })}
        options={sprintOptions}
      />
      <Select
        label="Até a sprint"
        placeholder="Trimestre"
        value={params.to}
        onChange={(event) => patch({ to: event.target.value })}
        options={sprintOptions}
      />
      {hasFilter(params) && (
        <Button onClick={() => patch({ squad: '', member: '', from: '', to: '' })}>
          Limpar
        </Button>
      )}
    </div>
  );
}

export default withQuery(function PlanningIsland() {
  return (
    <ToastProvider>
      <Planning />
    </ToastProvider>
  );
});
