import { useQuery } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api, type ProjectOut, type Schemas } from '../../lib/api';
import {
  DEFAULT_PROJECT_COLOR,
  INITIATIVE_STATUS_LABEL,
  PRIORITY_LABEL,
  formatDate,
  pluralize,
} from '../../lib/format';
import { groupByProject } from '../../lib/initiatives';
import { withQuery } from '../../lib/query';
import { useUrlState } from '../../lib/url-state';
import { Button } from '../ui/Button';
import { PriorityLozenge, StatusLozenge } from '../ui/Lozenge';
import { Select } from '../ui/Select';
import { Card, EmptyState, ErrorState, Skeleton } from '../ui/States';
import { TBody, THead, Table, Td, Th, Tr } from '../ui/Table';
import { ToastProvider } from '../ui/Toast';
import { InitiativeDrawer } from './InitiativeDrawer';
import { ProjectDrawer } from './ProjectDrawer';

/**
 * A tela `/projects` (§10.3): CRUD de projeto e de iniciativa.
 *
 * As iniciativas aparecem agrupadas pelo projeto, do mesmo jeito que a grade
 * agrupa as linhas — é a leitura que o §8 fixa e não faz sentido inverter aqui.
 * Criar e editar acontece em drawer, nunca em página nova.
 *
 * O filtro de status inclui `DEPRIORITIZED`, e é isso que faz desta tela o
 * lugar onde o trabalho parado é revisitado: ele não aparece no backlog nem na
 * grade, então sem este filtro ele não apareceria em lugar nenhum.
 */
const DEFAULTS = { q: '', status: '', priority: '', active: '' } as const;
type ProjectParams = { -readonly [K in keyof typeof DEFAULTS]: string };
const BASE: ProjectParams = { ...DEFAULTS };

const STATUS_OPTIONS = (
  ['BACKLOG', 'PLANNED', 'IN_PROGRESS', 'DEPRIORITIZED', 'DONE', 'CANCELLED'] as const
).map((status) => ({ value: status, label: INITIATIVE_STATUS_LABEL[status] }));

const PRIORITY_OPTIONS = (['HIGH', 'MEDIUM', 'LOW'] as const).map((priority) => ({
  value: priority,
  label: PRIORITY_LABEL[priority],
}));

const ACTIVE_OPTIONS = [
  { value: 'true', label: 'Ativos' },
  { value: 'false', label: 'Inativos' },
];

/** O que a tela abriu num drawer. `null` é nenhum. */
type Editing =
  | { readonly kind: 'project'; readonly projectId: string | null }
  | {
      readonly kind: 'initiative';
      readonly project: ProjectOut;
      readonly initiativeId: string | null;
    }
  | null;

function ProjectsScreen() {
  const [params, patch, mounted] = useUrlState<ProjectParams>(BASE);
  const [editing, setEditing] = useState<Editing>(null);
  const [search, setSearch] = useState('');

  // A busca digita rápido e a URL é o estado: sem a espera, cada tecla viraria
  // uma entrada de histórico de filtro e uma requisição.
  useEffect(() => {
    if (mounted) setSearch(params.q);
  }, [mounted]);
  useEffect(() => {
    if (!mounted || search === params.q) return;
    const timer = globalThis.setTimeout(() => patch({ q: search }), 250);
    return () => globalThis.clearTimeout(timer);
  }, [search, mounted, params.q, patch]);

  const projectFilter = {
    active: params.active === '' ? undefined : params.active === 'true',
  };
  const initiativeFilter = {
    status: (params.status || undefined) as Schemas['InitiativeStatus'] | undefined,
    priority: (params.priority || undefined) as Schemas['Priority'] | undefined,
    q: params.q || undefined,
  };

  const projects = useQuery({
    queryKey: ['projects', projectFilter],
    queryFn: ({ signal }) => api.listProjects(projectFilter, signal),
    enabled: mounted,
  });
  const initiatives = useQuery({
    queryKey: ['initiatives', initiativeFilter],
    queryFn: ({ signal }) => api.listInitiatives(initiativeFilter, signal),
    enabled: mounted,
  });

  const filtering = Boolean(params.q || params.status || params.priority);
  const groups =
    projects.data && initiatives.data
      ? groupByProject(projects.data, initiatives.data, { dropEmpty: filtering })
      : [];

  const pending = !mounted || projects.isPending || initiatives.isPending;
  const failed = projects.isError || initiatives.isError;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="inline-flex flex-col gap-1">
            <span className="text-12 text-text-subtle">Buscar iniciativa</span>
            <input
              type="search"
              value={search}
              placeholder="Nome da iniciativa"
              onChange={(event) => setSearch(event.target.value)}
              className="h-8 w-56 rounded-sm border border-border-strong bg-surface px-2 text-14 text-text placeholder:text-text-disabled hover:border-primary focus:border-primary"
            />
          </label>
          <Select
            label="Status"
            placeholder="Todos"
            value={params.status}
            onChange={(event) => patch({ status: event.target.value })}
            options={STATUS_OPTIONS}
          />
          <Select
            label="Prioridade"
            placeholder="Todas"
            value={params.priority}
            onChange={(event) => patch({ priority: event.target.value })}
            options={PRIORITY_OPTIONS}
          />
          <Select
            label="Projeto"
            placeholder="Todos"
            value={params.active}
            onChange={(event) => patch({ active: event.target.value })}
            options={ACTIVE_OPTIONS}
          />
          {(filtering || params.active) && (
            <Button
              onClick={() => {
                setSearch('');
                patch({ q: '', status: '', priority: '', active: '' });
              }}
            >
              Limpar
            </Button>
          )}
        </div>
        <Button
          variant="primary"
          onClick={() => setEditing({ kind: 'project', projectId: null })}
        >
          Novo projeto
        </Button>
      </div>

      <Card>
        {pending ? (
          <Skeleton lines={5} />
        ) : failed ? (
          <ErrorState
            what="os projetos"
            error={projects.error ?? initiatives.error}
            onRetry={() => {
              void projects.refetch();
              void initiatives.refetch();
            }}
          />
        ) : groups.length === 0 ? (
          <EmptyState
            message={
              filtering || params.active
                ? 'Nenhuma iniciativa bate com o filtro. Limpe o filtro para ver todos os projetos.'
                : 'Nenhum projeto cadastrado. Crie o primeiro projeto para começar a planejar.'
            }
            action={
              filtering || params.active ? (
                <Button
                  onClick={() => {
                    setSearch('');
                    patch({ q: '', status: '', priority: '', active: '' });
                  }}
                >
                  Limpar filtro
                </Button>
              ) : (
                <Button
                  variant="primary"
                  onClick={() => setEditing({ kind: 'project', projectId: null })}
                >
                  Novo projeto
                </Button>
              )
            }
          />
        ) : (
          <Table>
            <THead>
              <tr>
                <Th>Iniciativa</Th>
                <Th>Camada</Th>
                <Th>Prioridade</Th>
                <Th className="text-right">Estimativa</Th>
                <Th>Status</Th>
                <Th>Entrou em</Th>
              </tr>
            </THead>
            <TBody>
              {groups.map((group) => (
                <ProjectGroupRows
                  key={group.project.id}
                  project={group.project}
                  initiatives={group.initiatives}
                  onEditProject={() =>
                    setEditing({ kind: 'project', projectId: group.project.id })
                  }
                  onAddInitiative={() =>
                    setEditing({
                      kind: 'initiative',
                      project: group.project,
                      initiativeId: null,
                    })
                  }
                  onEditInitiative={(initiativeId) =>
                    setEditing({ kind: 'initiative', project: group.project, initiativeId })
                  }
                />
              ))}
            </TBody>
          </Table>
        )}
      </Card>

      {editing?.kind === 'project' && (
        <ProjectDrawer
          projectId={editing.projectId}
          onClose={() => setEditing(null)}
          onAddInitiative={(project) =>
            setEditing({ kind: 'initiative', project, initiativeId: null })
          }
          onEditInitiative={(project, initiativeId) =>
            setEditing({ kind: 'initiative', project, initiativeId })
          }
        />
      )}
      {editing?.kind === 'initiative' && (
        <InitiativeDrawer
          initiativeId={editing.initiativeId}
          projectId={editing.project.id}
          projectName={editing.project.name}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

interface ProjectGroupRowsProps {
  readonly project: ProjectOut;
  readonly initiatives: readonly Schemas['InitiativeOut'][];
  readonly onEditProject: () => void;
  readonly onAddInitiative: () => void;
  readonly onEditInitiative: (initiativeId: string) => void;
}

function ProjectGroupRows({
  project,
  initiatives,
  onEditProject,
  onAddInitiative,
  onEditInitiative,
}: ProjectGroupRowsProps) {
  return (
    <>
      <tr className="border-b border-border bg-neutral-soft">
        <td colSpan={6} className="h-8 px-3">
          <div className="flex items-center gap-2">
            <span
              aria-hidden
              className="size-3 shrink-0 rounded-sm"
              style={{ backgroundColor: project.color ?? DEFAULT_PROJECT_COLOR }}
            />
            <span className="truncate text-12 font-semibold">{project.name}</span>
            {project.is_capacity_reserve && (
              <span className="text-11 text-text-subtle">(reserva)</span>
            )}
            {!project.is_active && (
              <span className="text-11 text-text-subtle">(inativo)</span>
            )}
            <span className="text-11 text-text-subtle">
              · {pluralize(initiatives.length, 'iniciativa', 'iniciativas')}
            </span>
            <span className="ml-auto flex items-center gap-1">
              <Button variant="ghost" onClick={onEditProject}>
                Editar projeto
              </Button>
              <Button variant="ghost" onClick={onAddInitiative}>
                Nova iniciativa
              </Button>
            </span>
          </div>
        </td>
      </tr>

      {initiatives.length === 0 ? (
        <tr className="border-b border-border">
          <td colSpan={6} className="h-row px-3 text-12 text-text-subtle">
            Nenhuma iniciativa neste projeto.
          </td>
        </tr>
      ) : (
        initiatives.map((initiative) => (
          <Tr key={initiative.id} onClick={() => onEditInitiative(initiative.id)}>
            <Td className="max-w-[320px] truncate" title={initiative.name}>
              {initiative.name}
            </Td>
            <Td className="text-text-subtle">{initiative.layer ?? '—'}</Td>
            <Td>
              <PriorityLozenge priority={initiative.priority} />
            </Td>
            <Td className="text-right tabular-nums">
              {initiative.estimated_sprints ?? (
                <span className="text-text-subtle">—</span>
              )}
            </Td>
            <Td>
              <StatusLozenge status={initiative.status} />
            </Td>
            <Td className="tabular-nums">{formatDate(initiative.entered_at)}</Td>
          </Tr>
        ))
      )}
    </>
  );
}

export default withQuery(function ProjectsIsland() {
  return (
    <ToastProvider>
      <ProjectsScreen />
    </ToastProvider>
  );
});
