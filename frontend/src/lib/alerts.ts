/* Leitura do painel de alertas (§7.3, §10.3).
 *
 * Funções puras sobre o que `GET /alerts` devolveu. O cálculo do alerta é do
 * domínio e não se repete aqui: o que mora neste arquivo é como o painel
 * agrupa, conta e para onde cada alerta leva.
 */
import type { AlertOut, Schemas } from './api';

export type AlertType = Schemas['AlertType'];

/** Os alertas de uma sprint, na ordem em que o painel desenha o bloco. */
export interface AlertGroup {
  readonly sprintNumber: number;
  readonly alerts: readonly AlertOut[];
}

/** `WARNING` antes de `INFO`: o painel é lido de cima para baixo. */
const SEVERITY_RANK: Record<Schemas['Severity'], number> = { WARNING: 0, INFO: 1 };

/**
 * Agrupa por sprint, da mais próxima para a mais distante.
 *
 * A janela default do §8 já começa na sprint atual, então "crescente" é
 * "primeiro o que é para agora".
 */
export function groupBySprint(alerts: readonly AlertOut[]): AlertGroup[] {
  const bySprint = new Map<number, AlertOut[]>();
  for (const alert of alerts) {
    const bucket = bySprint.get(alert.sprint_number);
    if (bucket) bucket.push(alert);
    else bySprint.set(alert.sprint_number, [alert]);
  }
  return [...bySprint.entries()]
    .sort(([left], [right]) => left - right)
    .map(([sprintNumber, items]) => ({
      sprintNumber,
      alerts: [...items].sort(
        (left, right) =>
          SEVERITY_RANK[left.severity] - SEVERITY_RANK[right.severity] ||
          left.message.localeCompare(right.message, 'pt-BR'),
      ),
    }));
}

/**
 * O número do sino: só `WARNING` **não silenciado** (§10.3).
 *
 * `INFO` é informação, não aviso — `MEMBER_IDLE` sozinho encheria o contador
 * com uma pergunta de capacidade que ninguém pediu para responder agora.
 */
export function warningCount(alerts: readonly AlertOut[]): number {
  return alerts.filter((alert) => alert.severity === 'WARNING' && !alert.is_muted).length;
}

export function openAlerts(alerts: readonly AlertOut[]): AlertOut[] {
  return alerts.filter((alert) => !alert.is_muted);
}

export function mutedAlerts(alerts: readonly AlertOut[]): AlertOut[] {
  return alerts.filter((alert) => alert.is_muted);
}

/** Para onde o "link para o contexto" (§10.3) leva. */
export interface AlertContext {
  readonly href: string;
  readonly label: string;
}

function firstRefId(alert: AlertOut, type: Schemas['EntityRefType']): string | null {
  return alert.entity_refs.find((ref) => ref.type === type)?.id ?? null;
}

/**
 * A tela onde o alerta se **resolve**, não a tela onde ele apareceu.
 *
 * Sobrecarga e ociosidade se resolvem mexendo em alocação, que é o
 * planejamento filtrado naquela sprint. Conflito e squad vazia se resolvem
 * mexendo em composição, que é a matriz do time — e é por isso que o conflito
 * de um membro aponta para uma das squads dele, e não para ele.
 */
export function alertContext(alert: AlertOut): AlertContext {
  const sprint = `from=${alert.sprint_number}&to=${alert.sprint_number}`;
  switch (alert.type) {
    case 'SQUAD_OVERLOADED':
      return {
        href: `/planning?${sprint}&squad=${alert.subject_id}`,
        label: 'Ver no planejamento',
      };
    case 'MEMBER_IDLE':
      return {
        href: `/planning?${sprint}&member=${alert.subject_id}`,
        label: 'Ver no planejamento',
      };
    case 'EMPTY_SQUAD':
      return {
        href: `/team?${sprint}&squad=${alert.subject_id}`,
        label: 'Ver a composição',
      };
    case 'MEMBER_CONFLICT': {
      // O sujeito é o membro, mas quem se edita é a squad: a matriz abre numa
      // das duas em que ele está, e as outras aparecem anotadas na célula.
      const squadId = firstRefId(alert, 'squad');
      return squadId
        ? { href: `/team?${sprint}&squad=${squadId}`, label: 'Ver a composição' }
        : {
            href: `/planning?${sprint}&member=${alert.subject_id}`,
            label: 'Ver no planejamento',
          };
    }
  }
}

/**
 * A severidade de cada tipo, como o §7.3 fixa.
 *
 * O `AlertOut` já traz `severity` — esta tabela existe para o **único** lugar
 * onde a API manda tipo sem severidade: `alerts_by_sprint` da grade (§8), que
 * é uma lista de tipos por sprint. Sem ela, o ícone da coluna sairia vermelho
 * para `MEMBER_IDLE`, que é informação, e o vermelho pararia de significar
 * alguma coisa: com o time inteiro, quase toda sprint do horizonte tem uma
 * pessoa sem frente (§7.3).
 */
export const ALERT_TYPE_SEVERITY: Record<AlertType, Schemas['Severity']> = {
  SQUAD_OVERLOADED: 'WARNING',
  MEMBER_CONFLICT: 'WARNING',
  MEMBER_IDLE: 'INFO',
  EMPTY_SQUAD: 'INFO',
};

/** `WARNING` se algum dos tipos for aviso; `INFO` se só houver informação. */
export function worstSeverity(
  types: readonly AlertType[],
): Schemas['Severity'] | null {
  if (types.length === 0) return null;
  return types.some((type) => ALERT_TYPE_SEVERITY[type] === 'WARNING')
    ? 'WARNING'
    : 'INFO';
}
