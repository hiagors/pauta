import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import {
  api,
  type MemberOut,
  type ProjectOut,
  type SprintOut,
  type SquadOut,
} from '../../lib/api';
import { formatDateRange } from '../../lib/format';
import { withQuery } from '../../lib/query';
import { Card, ErrorState, Skeleton } from '../ui/States';

/**
 * Resumo da rota — o conteúdo provisório das telas que ainda não existem.
 *
 * `/planning` e `/backlog` já saíram daqui: viraram tela de verdade na Fase 7.
 * O que sobra são as três da Fase 8 (projetos, time e sprints), que continuam
 * mostrando dado real da API com os quatro estados do §10.5 até chegarem.
 */
export type RouteKey = 'projects' | 'team' | 'sprints';

interface RouteConfig<T> {
  /** Chave do cache; a mesma forma que as telas vão usar. */
  readonly queryKey: readonly unknown[];
  readonly load: (signal: AbortSignal) => Promise<T>;
  /** Completa "Não foi possível carregar …" na mensagem de erro. */
  readonly what: string;
  /** Vazio é convite, com a ação que resolve (§10.5). */
  readonly empty: string;
  readonly isEmpty: (data: T) => boolean;
  readonly summary: (data: T) => ReactNode;
  /** O que ainda falta nesta tela, dito sem rodeio. */
  readonly pending: string;
}

/** Um único ponto de conversão: o `useQuery` abaixo não conhece o tipo de cada
 * rota, mas cada config conhece o seu. */
function defineRoute<T>(config: RouteConfig<T>): RouteConfig<unknown> {
  return config as RouteConfig<unknown>;
}

interface TeamData {
  readonly members: MemberOut[];
  readonly squads: SquadOut[];
}

const ROUTES: Record<RouteKey, RouteConfig<unknown>> = {
  projects: defineRoute<ProjectOut[]>({
    queryKey: ['projects', {}],
    load: (signal) => api.listProjects(undefined, signal),
    what: 'os projetos',
    empty: 'Nenhum projeto cadastrado. Crie o primeiro projeto para começar a planejar.',
    isEmpty: (projects) => projects.length === 0,
    summary: (projects) => (
      <dl className="grid grid-cols-[auto_1fr] gap-x-5 gap-y-1">
        <Fact label="Projetos" value={String(projects.length)} />
        <Fact
          label="Ativos"
          value={String(projects.filter((project) => project.is_active).length)}
        />
        <Fact
          label="Reserva de capacidade"
          value={String(projects.filter((project) => project.is_capacity_reserve).length)}
        />
      </dl>
    ),
    pending: 'O CRUD de projeto e de iniciativa entra na Fase 8.',
  }),

  team: defineRoute<TeamData>({
    queryKey: ['team', 'overview'],
    load: async (signal) => {
      const [members, squads] = await Promise.all([
        api.listMembers(undefined, signal),
        api.listSquads(undefined, signal),
      ]);
      return { members, squads };
    },
    what: 'o time',
    empty: 'Nenhuma pessoa cadastrada. Cadastre o time para montar as squads.',
    isEmpty: (team) => team.members.length === 0 && team.squads.length === 0,
    summary: (team) => (
      <dl className="grid grid-cols-[auto_1fr] gap-x-5 gap-y-1">
        <Fact
          label="Pessoas ativas"
          value={String(team.members.filter((member) => member.is_active).length)}
        />
        <Fact
          label="Squads ativas"
          value={String(team.squads.filter((squad) => squad.is_active).length)}
        />
      </dl>
    ),
    pending: 'Os drawers e a matriz de composição por sprint entram na Fase 8.',
  }),

  sprints: defineRoute<SprintOut[]>({
    queryKey: ['sprints', {}],
    load: (signal) => api.listSprints(undefined, signal),
    what: 'as sprints',
    empty: 'Nenhuma sprint cadastrada. Crie a primeira sprint para abrir a grade.',
    isEmpty: (sprints) => sprints.length === 0,
    summary: (sprints) => {
      const current = sprints.find((sprint) => sprint.is_current);
      return (
        <dl className="grid grid-cols-[auto_1fr] gap-x-5 gap-y-1">
          <Fact label="Sprints cadastradas" value={String(sprints.length)} />
          <Fact
            label="Sprint atual"
            value={
              current
                ? `${current.number} · ${formatDateRange(current.start_date, current.end_date)}`
                : 'nenhuma (RN12)'
            }
          />
        </dl>
      );
    },
    pending: 'A lista e o botão "Criar próxima sprint" entram na Fase 8.',
  }),
};

function Fact({ label, value }: { readonly label: string; readonly value: string }) {
  return (
    <>
      <dt className="text-12 text-text-subtle">{label}</dt>
      <dd className="m-0 text-14 font-semibold tabular-nums">{value}</dd>
    </>
  );
}

function RouteSummary({ route }: { readonly route: RouteKey }) {
  const config = ROUTES[route];
  const query = useQuery({
    queryKey: config.queryKey,
    queryFn: ({ signal }) => config.load(signal),
  });

  if (query.isPending) {
    return (
      <Card>
        <Skeleton />
      </Card>
    );
  }

  if (query.isError) {
    return (
      <Card>
        <ErrorState
          what={config.what}
          error={query.error}
          onRetry={() => void query.refetch()}
        />
      </Card>
    );
  }

  if (config.isEmpty(query.data)) {
    return (
      <Card className="p-4">
        <p className="m-0 text-14">{config.empty}</p>
      </Card>
    );
  }

  return (
    <Card className="p-4">
      {config.summary(query.data)}
      <p className="mt-3 mb-0 text-12 text-text-subtle">{config.pending}</p>
    </Card>
  );
}

export default withQuery(RouteSummary);
