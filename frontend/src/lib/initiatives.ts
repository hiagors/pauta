/* Regras do cadastro de projeto e de iniciativa que a tela precisa saber.
 *
 * Tudo aqui é função pura sobre o que a API devolveu — sem React, sem rede.
 * É a mesma divisão de `planning.ts`: a lógica que erra em silêncio fica
 * testável, e o componente vira só desenho.
 *
 * O backend continua sendo a autoridade. A tabela de transição repetida aqui
 * não valida nada: ela decide **o que oferecer**, para a tela não mostrar um
 * botão cuja única resposta possível é 422.
 */
import type { InitiativeOut, ProjectOut, Schemas } from './api';

export type InitiativeStatus = Schemas['InitiativeStatus'];
export type Priority = Schemas['Priority'];

/**
 * As transições **manuais** do §6.3, e só elas.
 *
 * `BACKLOG → PLANNED` e a volta não estão aqui de propósito: são automáticas,
 * efeito de ganhar ou perder alocação (RN2), e não há botão para elas. Nada
 * volta para `BACKLOG` depois de ter começado — quem parou vai para
 * `DEPRIORITIZED`.
 */
export const MANUAL_TRANSITIONS: Record<InitiativeStatus, readonly InitiativeStatus[]> = {
  BACKLOG: ['CANCELLED'],
  PLANNED: ['IN_PROGRESS', 'CANCELLED'],
  IN_PROGRESS: ['DEPRIORITIZED', 'DONE', 'CANCELLED'],
  DEPRIORITIZED: ['PLANNED', 'IN_PROGRESS', 'CANCELLED'],
  DONE: [],
  CANCELLED: [],
};

export function manualTransitions(status: InitiativeStatus): readonly InitiativeStatus[] {
  return MANUAL_TRANSITIONS[status];
}

/** `DONE` e `CANCELLED` são terminais (§6.3): nada sai deles. */
export function isTerminal(status: InitiativeStatus): boolean {
  return MANUAL_TRANSITIONS[status].length === 0;
}

/** Ordem de leitura do fluxo, a mesma de `planning.ts`. */
const STATUS_RANK: Record<InitiativeStatus, number> = {
  BACKLOG: 0,
  PLANNED: 1,
  IN_PROGRESS: 2,
  DEPRIORITIZED: 3,
  DONE: 4,
  CANCELLED: 5,
};

const PRIORITY_RANK: Record<Priority, number> = { HIGH: 0, MEDIUM: 1, LOW: 2 };

const collator = new Intl.Collator('pt-BR', { sensitivity: 'base', numeric: true });

/** Um projeto e as iniciativas dele, na ordem em que a tela desenha. */
export interface ProjectGroup {
  readonly project: ProjectOut;
  readonly initiatives: readonly InitiativeOut[];
}

/**
 * Agrupa as iniciativas pelo projeto, como a grade agrupa as linhas.
 *
 * `dropEmpty` existe por causa do filtro de status: com "Despriorizadas"
 * selecionado, um projeto sem nenhuma iniciativa naquele status é ruído. Sem
 * filtro nenhum ele precisa aparecer — é assim que um projeto recém-criado, ou
 * um que ficou sem iniciativa visível, continua alcançável para edição.
 */
export function groupByProject(
  projects: readonly ProjectOut[],
  initiatives: readonly InitiativeOut[],
  options: { readonly dropEmpty?: boolean } = {},
): ProjectGroup[] {
  const byProject = new Map<string, InitiativeOut[]>();
  for (const initiative of initiatives) {
    const bucket = byProject.get(initiative.project_id);
    if (bucket) bucket.push(initiative);
    else byProject.set(initiative.project_id, [initiative]);
  }
  return [...projects]
    .sort((left, right) => collator.compare(left.name, right.name))
    .map((project) => ({
      project,
      initiatives: sortInitiatives(byProject.get(project.id) ?? []),
    }))
    .filter((group) => !options.dropEmpty || group.initiatives.length > 0);
}

/** Prioridade primeiro, status depois, nome para desempatar: a leitura é "o
 * que é urgente e ainda não terminou". */
export function sortInitiatives(
  initiatives: readonly InitiativeOut[],
): InitiativeOut[] {
  return [...initiatives].sort((left, right) => {
    const byPriority = PRIORITY_RANK[left.priority] - PRIORITY_RANK[right.priority];
    if (byPriority !== 0) return byPriority;
    const byStatus = STATUS_RANK[left.status] - STATUS_RANK[right.status];
    if (byStatus !== 0) return byStatus;
    return collator.compare(left.name, right.name);
  });
}

/**
 * `#RRGGBB`, que é o que o §6.1 aceita.
 *
 * O `<input type="color">` só produz esse formato, então a checagem existe
 * para o valor que veio gravado: um projeto criado pela CLI ou por um snapshot
 * antigo não pode quebrar o formulário.
 */
export function isHexColor(value: string): boolean {
  return /^#[0-9a-fA-F]{6}$/.test(value);
}

/**
 * Estimativa em sprints: inteiro maior que zero, ou nulo (§6.2).
 *
 * Devolve `undefined` quando o texto não é nenhum dos dois, e é isso que o
 * formulário usa para bloquear o botão em vez de mandar lixo para a API.
 */
export function parseEstimate(value: string): number | null | undefined {
  const trimmed = value.trim();
  if (trimmed === '') return null;
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed <= 0) return undefined;
  return parsed;
}
