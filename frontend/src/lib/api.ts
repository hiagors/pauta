/* Cliente da API (§10.5).
 *
 * É o **único** lugar do front que chama `fetch`. Nenhum componente monta URL,
 * nenhum componente lê `PUBLIC_API_URL`: quem precisa de dado chama um método
 * daqui. Um método por endpoint do §8, com o mesmo nome do recurso.
 *
 * Os tipos não são redigitados à mão — vêm de `types.ts`, gerado do OpenAPI do
 * backend por `mise run types`. Se o contrato mudar e o front não acompanhar, é
 * o `tsc` que reclama, não o navegador.
 */
import type { components, operations } from './types';

/** Atalho para os schemas do §8, para não escrever `components['schemas'][…]`. */
export type Schemas = components['schemas'];

export type ProjectOut = Schemas['ProjectOut'];
export type ProjectDetailOut = Schemas['ProjectDetailOut'];
export type InitiativeOut = Schemas['InitiativeOut'];
export type MemberOut = Schemas['MemberOut'];
export type SquadOut = Schemas['SquadOut'];
export type SquadDetailOut = Schemas['SquadDetailOut'];
export type SprintOut = Schemas['SprintOut'];
export type SprintProposalOut = Schemas['SprintProposalOut'];
export type AllocationOut = Schemas['AllocationOut'];
export type AllocationResultOut = Schemas['AllocationResultOut'];
export type DeallocationResultOut = Schemas['DeallocationResultOut'];
export type GridOut = Schemas['GridOut'];
export type BacklogOut = Schemas['BacklogOut'];
export type AlertOut = Schemas['AlertOut'];
export type AlertsOut = Schemas['AlertsOut'];
export type MutedAlertOut = Schemas['MutedAlertOut'];
export type SnapshotExportOut = Schemas['SnapshotExportOut'];
export type SnapshotImportOut = Schemas['SnapshotImportOut'];

/* -------------------------------------------------------------------------
 * Tipos derivados do OpenAPI
 *
 * `QueryOf` e `BodyOf` leem a operação gerada em vez de repetir a lista de
 * filtros. Acrescentar um filtro no backend e rodar `mise run types` é o
 * bastante para o método daqui aceitá-lo.
 * ---------------------------------------------------------------------- */

type Operation = keyof operations;

type QueryOf<K extends Operation> = NonNullable<operations[K]['parameters']['query']>;

type BodyOf<K extends Operation> = operations[K] extends {
  requestBody: { content: { 'application/json': infer B } };
}
  ? B
  : never;

/** Códigos de erro do §8 que o cliente reconhece sem consultar o servidor. */
export const NETWORK_ERROR_CODE = 'NETWORK_UNREACHABLE';
export const UNEXPECTED_ERROR_CODE = 'UNEXPECTED_RESPONSE';

/**
 * Erro vindo da API, já traduzido do envelope do §8.
 *
 * `code` é o contrato estável: é por ele que a UI decide a mensagem, nunca pelo
 * texto. `status` distingue 404 de 409 de 422 quando a tela precisa reagir
 * diferente ao mesmo `code`.
 */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

/** Valores que sabemos escrever numa query string. */
type QueryValue = string | number | boolean | null | undefined;

export interface ApiClientOptions {
  /** Sem barra no fim; o `request` já cuida da junção. */
  readonly baseUrl: string;
  /** Injetável para o teste não precisar de rede nem de servidor. */
  readonly fetchImpl?: typeof fetch;
}

interface RequestOptions {
  readonly method: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  readonly path: string;
  readonly query?: Record<string, QueryValue> | undefined;
  readonly body?: unknown;
  readonly signal?: AbortSignal | undefined;
}

/** `undefined` e `null` somem da query: o backend trata ausência como "sem
 * filtro", e mandar `active=null` viraria erro de validação. */
function buildQuery(query: Record<string, QueryValue> | undefined): string {
  if (!query) return '';
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null) continue;
    params.append(key, String(value));
  }
  const serialized = params.toString();
  return serialized ? `?${serialized}` : '';
}

/** Lê o envelope do §8. Uma resposta de erro que não seja o envelope é bug do
 * backend, e vira `UNEXPECTED_ERROR_CODE` em vez de um `undefined` silencioso. */
function toApiError(status: number, payload: unknown): ApiError {
  const envelope = payload as Partial<Schemas['ErrorEnvelope']> | null;
  const body = envelope?.error;
  if (body && typeof body.code === 'string' && typeof body.message === 'string') {
    return new ApiError(status, body.code, body.message, body.details ?? {});
  }
  return new ApiError(
    status,
    UNEXPECTED_ERROR_CODE,
    `A API respondeu ${status} num formato que o front não reconhece.`,
  );
}

export function createApiClient(options: ApiClientOptions) {
  const baseUrl = options.baseUrl.replace(/\/+$/, '');
  const doFetch = options.fetchImpl ?? globalThis.fetch;

  async function request<T>(init: RequestOptions): Promise<T> {
    const url = `${baseUrl}${init.path}${buildQuery(init.query)}`;
    const hasBody = init.body !== undefined;

    let response: Response;
    try {
      response = await doFetch(url, {
        method: init.method,
        headers: hasBody
          ? { 'content-type': 'application/json', accept: 'application/json' }
          : { accept: 'application/json' },
        body: hasBody ? JSON.stringify(init.body) : undefined,
        signal: init.signal ?? null,
      });
    } catch (cause) {
      // Sem servidor no ar não há envelope para ler. A mensagem diz o que
      // aconteceu e onde (§10.5: erro não é vago), e a tela oferece o retry.
      throw new ApiError(
        0,
        NETWORK_ERROR_CODE,
        `Não foi possível falar com a API em ${baseUrl}. Verifique se ela está no ar.`,
        { cause: String(cause) },
      );
    }

    if (response.status === 204) return undefined as T;

    const text = await response.text();
    const payload: unknown = text ? JSON.parse(text) : null;
    if (!response.ok) throw toApiError(response.status, payload);
    return payload as T;
  }

  return {
    /** Exposto para a mensagem de erro poder dizer contra quem falhou. */
    baseUrl,

    /* ---------------------------------------------------------------- §8 */

    /* projetos */
    listProjects: (
      query?: QueryOf<'list_projects_api_v1_projects_get'>,
      signal?: AbortSignal,
    ) => request<ProjectOut[]>({ method: 'GET', path: '/api/v1/projects', query, signal }),

    /** Cria também a primeira iniciativa (RN-I1) — por isso devolve o detalhe. */
    createProject: (body: BodyOf<'create_project_api_v1_projects_post'>) =>
      request<ProjectDetailOut>({ method: 'POST', path: '/api/v1/projects', body }),

    getProject: (projectId: string, signal?: AbortSignal) =>
      request<ProjectDetailOut>({
        method: 'GET',
        path: `/api/v1/projects/${projectId}`,
        signal,
      }),

    updateProject: (
      projectId: string,
      body: BodyOf<'update_project_api_v1_projects__project_id__patch'>,
    ) => request<ProjectOut>({ method: 'PATCH', path: `/api/v1/projects/${projectId}`, body }),

    /** 409 se alguma iniciativa do projeto tiver alocação (§8). */
    deleteProject: (projectId: string) =>
      request<void>({ method: 'DELETE', path: `/api/v1/projects/${projectId}` }),

    /* iniciativas */
    listInitiatives: (
      query?: QueryOf<'list_initiatives_api_v1_initiatives_get'>,
      signal?: AbortSignal,
    ) =>
      request<InitiativeOut[]>({
        method: 'GET',
        path: '/api/v1/initiatives',
        query,
        signal,
      }),

    createInitiative: (body: BodyOf<'create_initiative_api_v1_initiatives_post'>) =>
      request<InitiativeOut>({ method: 'POST', path: '/api/v1/initiatives', body }),

    getInitiative: (initiativeId: string, signal?: AbortSignal) =>
      request<InitiativeOut>({
        method: 'GET',
        path: `/api/v1/initiatives/${initiativeId}`,
        signal,
      }),

    updateInitiative: (
      initiativeId: string,
      body: BodyOf<'update_initiative_api_v1_initiatives__initiative_id__patch'>,
    ) =>
      request<InitiativeOut>({
        method: 'PATCH',
        path: `/api/v1/initiatives/${initiativeId}`,
        body,
      }),

    /** Só as transições manuais do §6.3; `BACKLOG <-> PLANNED` é automático. */
    changeInitiativeStatus: (
      initiativeId: string,
      body: BodyOf<'change_status_api_v1_initiatives__initiative_id__status_post'>,
    ) =>
      request<InitiativeOut>({
        method: 'POST',
        path: `/api/v1/initiatives/${initiativeId}/status`,
        body,
      }),

    /** 409 se houver alocação ou se for a última do projeto; o caminho é `CANCELLED`. */
    deleteInitiative: (initiativeId: string) =>
      request<void>({ method: 'DELETE', path: `/api/v1/initiatives/${initiativeId}` }),

    /* membros */
    listMembers: (
      query?: QueryOf<'list_members_api_v1_members_get'>,
      signal?: AbortSignal,
    ) => request<MemberOut[]>({ method: 'GET', path: '/api/v1/members', query, signal }),

    createMember: (body: BodyOf<'create_member_api_v1_members_post'>) =>
      request<MemberOut>({ method: 'POST', path: '/api/v1/members', body }),

    updateMember: (
      memberId: string,
      body: BodyOf<'update_member_api_v1_members__member_id__patch'>,
    ) => request<MemberOut>({ method: 'PATCH', path: `/api/v1/members/${memberId}`, body }),

    /** Soft delete: membro nunca é apagado, só `is_active = false` (§6.4). */
    deactivateMember: (memberId: string) =>
      request<MemberOut>({ method: 'DELETE', path: `/api/v1/members/${memberId}` }),

    /* squads */
    listSquads: (query?: QueryOf<'list_squads_api_v1_squads_get'>, signal?: AbortSignal) =>
      request<SquadOut[]>({ method: 'GET', path: '/api/v1/squads', query, signal }),

    createSquad: (body: BodyOf<'create_squad_api_v1_squads_post'>) =>
      request<SquadOut>({ method: 'POST', path: '/api/v1/squads', body }),

    getSquad: (squadId: string, signal?: AbortSignal) =>
      request<SquadDetailOut>({ method: 'GET', path: `/api/v1/squads/${squadId}`, signal }),

    updateSquad: (
      squadId: string,
      body: BodyOf<'update_squad_api_v1_squads__squad_id__patch'>,
    ) => request<SquadOut>({ method: 'PATCH', path: `/api/v1/squads/${squadId}`, body }),

    deactivateSquad: (squadId: string) =>
      request<SquadOut>({ method: 'DELETE', path: `/api/v1/squads/${squadId}` }),

    /* composição por sprint (D11) */
    listMemberships: (
      squadId: string,
      query?: QueryOf<'list_memberships_api_v1_squads__squad_id__memberships_get'>,
      signal?: AbortSignal,
    ) =>
      request<Schemas['SprintCompositionOut'][]>({
        method: 'GET',
        path: `/api/v1/squads/${squadId}/memberships`,
        query,
        signal,
      }),

    /** **Substitui** a composição no intervalo; lista vazia esvazia a squad. */
    setMemberships: (
      squadId: string,
      body: BodyOf<'set_memberships_api_v1_squads__squad_id__memberships_put'>,
    ) =>
      request<Schemas['SprintCompositionOut'][]>({
        method: 'PUT',
        path: `/api/v1/squads/${squadId}/memberships`,
        body,
      }),

    removeMemberships: (
      squadId: string,
      body: BodyOf<'remove_memberships_api_v1_squads__squad_id__memberships_delete'>,
    ) =>
      request<Schemas['SprintCompositionOut'][]>({
        method: 'DELETE',
        path: `/api/v1/squads/${squadId}/memberships`,
        body,
      }),

    /* sprints — sem DELETE por regra (D13) */
    listSprints: (
      query?: QueryOf<'list_sprints_api_v1_sprints_get'>,
      signal?: AbortSignal,
    ) => request<SprintOut[]>({ method: 'GET', path: '/api/v1/sprints', query, signal }),

    createSprint: (body: BodyOf<'create_sprint_api_v1_sprints_post'>) =>
      request<SprintOut>({ method: 'POST', path: '/api/v1/sprints', body }),

    /** Proposta da RN10, para a tela mostrar antes de confirmar. */
    previewNextSprint: (signal?: AbortSignal) =>
      request<SprintProposalOut>({
        method: 'GET',
        path: '/api/v1/sprints/next/preview',
        signal,
      }),

    createNextSprint: () =>
      request<SprintOut>({ method: 'POST', path: '/api/v1/sprints/next' }),

    /* alocações */
    listAllocations: (
      query?: QueryOf<'list_allocations_api_v1_allocations_get'>,
      signal?: AbortSignal,
    ) =>
      request<AllocationOut[]>({
        method: 'GET',
        path: '/api/v1/allocations',
        query,
        signal,
      }),

    allocateRange: (body: BodyOf<'allocate_range_api_v1_allocations_post'>) =>
      request<AllocationResultOut>({ method: 'POST', path: '/api/v1/allocations', body }),

    /** O intervalo vai no corpo, não na query (§8). */
    deallocateRange: (body: BodyOf<'deallocate_range_api_v1_allocations_delete'>) =>
      request<DeallocationResultOut>({
        method: 'DELETE',
        path: '/api/v1/allocations',
        body,
      }),

    deallocateCell: (allocationId: string) =>
      request<DeallocationResultOut>({
        method: 'DELETE',
        path: `/api/v1/allocations/${allocationId}`,
      }),

    /* planejamento */
    /** Sem intervalo, a janela é o trimestre corrente (RN13). */
    getGrid: (query?: QueryOf<'get_grid_api_v1_planning_grid_get'>, signal?: AbortSignal) =>
      request<GridOut>({ method: 'GET', path: '/api/v1/planning/grid', query, signal }),

    getBacklog: (
      query?: QueryOf<'get_backlog_api_v1_planning_backlog_get'>,
      signal?: AbortSignal,
    ) =>
      request<BacklogOut>({
        method: 'GET',
        path: '/api/v1/planning/backlog',
        query,
        signal,
      }),

    /* alertas */
    /** Sem intervalo, a janela é da sprint atual (RN12) até a última cadastrada. */
    listAlerts: (query?: QueryOf<'list_alerts_api_v1_alerts_get'>, signal?: AbortSignal) =>
      request<AlertsOut>({ method: 'GET', path: '/api/v1/alerts', query, signal }),

    muteAlert: (body: BodyOf<'mute_alert_api_v1_alerts_mute_post'>) =>
      request<MutedAlertOut>({ method: 'POST', path: '/api/v1/alerts/mute', body }),

    /** Reativa o alerta silenciado; o `mute_id` vem no próprio alerta. */
    unmuteAlert: (muteId: string) =>
      request<void>({ method: 'DELETE', path: `/api/v1/alerts/mute/${muteId}` }),

    /* snapshots */
    exportSnapshot: () =>
      request<SnapshotExportOut>({ method: 'POST', path: '/api/v1/snapshots/export' }),

    /** Destrutivo: substitui o banco inteiro. O `confirm=true` é obrigatório. */
    importSnapshot: (body: BodyOf<'import_snapshot_api_v1_snapshots_import_post'>) =>
      request<SnapshotImportOut>({
        method: 'POST',
        path: '/api/v1/snapshots/import',
        query: { confirm: true },
        body,
      }),
  };
}

export type ApiClient = ReturnType<typeof createApiClient>;

/** Porta da API fixada pelo §10.4. Só serve de rede de segurança para quando o
 * `PUBLIC_API_URL` não chegar ao build — em uso normal quem manda é o mise. */
const DEFAULT_API_URL = 'http://127.0.0.1:8000';

/** O cliente que os componentes usam. Base URL de `PUBLIC_API_URL` (§10.5). */
export const api: ApiClient = createApiClient({
  baseUrl: import.meta.env.PUBLIC_API_URL ?? DEFAULT_API_URL,
});
