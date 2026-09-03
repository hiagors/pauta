import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api, type Schemas } from '../../lib/api';
import { formatDate, pluralize } from '../../lib/format';
import type { SprintRange } from '../../lib/planning';
import { withQuery } from '../../lib/query';
import { useUrlState } from '../../lib/url-state';
import { Button } from '../ui/Button';
import { PriorityLozenge } from '../ui/Lozenge';
import { Select } from '../ui/Select';
import { Card, EmptyState, ErrorState, Skeleton } from '../ui/States';
import { TBody, THead, Table, Td, Th, Tr } from '../ui/Table';
import { ToastProvider } from '../ui/Toast';
import { AllocationDialog, type AllocationSubject } from './AllocationDialog';

/**
 * A tela `/backlog` (§10.3).
 *
 * O contador do topo e a ordenação vêm prontos do backend: `order_by` e o
 * `summary` são do §8, e `estimated_sprints_total` já soma só quem tem
 * estimativa. O front não recalcula nada disso — se recalculasse, a tela e o
 * snapshot exportado poderiam discordar.
 *
 * `DEPRIORITIZED` não aparece aqui: é filtro da tela de projetos (§8).
 */

const DEFAULTS = { order: 'priority', dir: 'asc' } as const;
type BacklogParams = { -readonly [K in keyof typeof DEFAULTS]: string };
const BASE: BacklogParams = { ...DEFAULTS };

const ORDER_OPTIONS = [
  { value: 'priority', label: 'Prioridade' },
  { value: 'size', label: 'Tamanho' },
  { value: 'entered_at', label: 'Data de entrada' },
];

function BacklogScreen() {
  const [params, patch, mounted] = useUrlState<BacklogParams>(BASE);
  const [allocating, setAllocating] = useState<{
    subject: AllocationSubject;
    range: SprintRange;
  } | null>(null);

  const query = {
    order_by: params.order as Schemas['BacklogOrder'],
    descending: params.dir === 'desc',
  };

  const backlog = useQuery({
    queryKey: ['planning', 'backlog', query],
    queryFn: ({ signal }) => api.getBacklog(query, signal),
    enabled: mounted,
  });

  // A sprint atual é o ponto de partida natural do diálogo (§10.3: "já com
  // iniciativa e sprint preenchidos"). Sem nenhuma sprint começada (RN12), o
  // default cai na última cadastrada, e em nenhuma, na 1 — que o backend
  // devolve em `missing_sprint_numbers`, não em erro (RN5).
  const sprints = useQuery({
    queryKey: ['sprints', {}],
    queryFn: ({ signal }) => api.listSprints(undefined, signal),
    enabled: mounted,
  });
  const startSprint =
    sprints.data?.find((sprint) => sprint.is_current)?.number ??
    sprints.data?.[sprints.data.length - 1]?.number ??
    1;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <Summary summary={backlog.data?.summary} />
        <div className="flex items-end gap-3">
          <Select
            label="Ordenar por"
            value={params.order}
            onChange={(event) => patch({ order: event.target.value })}
            options={ORDER_OPTIONS}
          />
          <Button
            onClick={() => patch({ dir: params.dir === 'asc' ? 'desc' : 'asc' })}
            aria-label={
              params.dir === 'asc' ? 'Ordem crescente; inverter' : 'Ordem decrescente; inverter'
            }
          >
            {params.dir === 'asc' ? '↑ Crescente' : '↓ Decrescente'}
          </Button>
        </div>
      </div>

      <Card>
        {!mounted || backlog.isPending ? (
          <Skeleton lines={4} />
        ) : backlog.isError ? (
          <ErrorState
            what="o backlog"
            error={backlog.error}
            onRetry={() => void backlog.refetch()}
          />
        ) : backlog.data.items.length === 0 ? (
          <EmptyState
            message="Nenhuma iniciativa no backlog. Cadastre um projeto para começar a planejar."
            action={
              <Button variant="primary" onClick={() => window.location.assign('/projects')}>
                Ir para Projetos
              </Button>
            }
          />
        ) : (
          <Table>
            <THead>
              <tr>
                <Th>Projeto</Th>
                <Th>Iniciativa</Th>
                <Th>Camada</Th>
                <Th>Prioridade</Th>
                <Th className="text-right">Estimativa</Th>
                <Th>Entrou em</Th>
                <Th className="text-right">Ação</Th>
              </tr>
            </THead>
            <TBody>
              {backlog.data.items.map((item) => (
                <Tr key={item.initiative.id}>
                  <Td>
                    <span className="flex items-center gap-2">
                      <span
                        aria-hidden
                        className="size-3 shrink-0 rounded-sm"
                        style={{ backgroundColor: item.project.color }}
                      />
                      <span className="truncate">{item.project.name}</span>
                    </span>
                  </Td>
                  <Td className="max-w-[280px] truncate" title={item.initiative.name}>
                    {item.initiative.name}
                  </Td>
                  <Td className="text-text-subtle">{item.initiative.layer ?? '—'}</Td>
                  <Td>
                    <PriorityLozenge priority={item.initiative.priority} />
                  </Td>
                  <Td className="text-right tabular-nums">
                    {item.initiative.estimated_sprints ?? (
                      <span className="text-text-subtle">sem estimativa</span>
                    )}
                  </Td>
                  <Td className="tabular-nums">{formatDate(item.initiative.entered_at)}</Td>
                  <Td className="text-right">
                    {/* Ação de linha não é a ação primária da tela: o §10.1
                        pede uma azul por tela, e aqui haveria uma por linha. */}
                    <Button
                      onClick={() =>
                        setAllocating({
                          subject: {
                            initiativeId: item.initiative.id,
                            initiativeName: item.initiative.name,
                            projectName: item.project.name,
                          },
                          range: {
                            from: startSprint,
                            to: startSprint + Math.max(item.initiative.estimated_sprints ?? 1, 1) - 1,
                          },
                        })
                      }
                    >
                      Alocar
                    </Button>
                  </Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        )}
      </Card>

      {allocating && (
        <AllocationDialog
          open
          onClose={() => setAllocating(null)}
          subject={allocating.subject}
          defaultRange={allocating.range}
        />
      )}
    </div>
  );
}

/** O contador do topo do §10.3, com o aviso de quem está sem estimativa. */
function Summary({ summary }: { readonly summary?: Schemas['BacklogSummaryOut'] }) {
  if (!summary) {
    return <div aria-hidden className="h-8 w-72 animate-pulse rounded-sm bg-neutral-soft" />;
  }
  return (
    <p className="m-0 flex flex-wrap items-baseline gap-x-2 text-14">
      <strong className="text-16">{summary.count}</strong>
      <span>{summary.count === 1 ? 'iniciativa' : 'iniciativas'}</span>
      <span className="text-text-subtle">·</span>
      <strong className="text-16">{summary.estimated_sprints_total}</strong>
      <span>
        {summary.estimated_sprints_total === 1
          ? 'sprint de trabalho'
          : 'sprints de trabalho'}
      </span>
      {summary.items_without_estimate > 0 && (
        <span className="text-12 text-warning">
          ({pluralize(summary.items_without_estimate, 'sem estimativa', 'sem estimativa')})
        </span>
      )}
    </p>
  );
}

export default withQuery(function BacklogIsland() {
  return (
    <ToastProvider>
      <BacklogScreen />
    </ToastProvider>
  );
});
