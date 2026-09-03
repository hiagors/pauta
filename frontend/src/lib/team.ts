/* A matriz de composição por sprint (§10.3, bloco 3 da tela de time).
 *
 * Funções puras sobre o que `GET /squads?sprint_number=` devolveu — uma
 * chamada por sprint da janela, cada uma trazendo **todas** as squads com a
 * composição daquela sprint. É essa forma que permite responder, na mesma
 * célula, as duas perguntas do §10.3: "esta pessoa está nesta squad nesta
 * sprint?" e "em qual outra squad ela já está?".
 */
import type { MemberOut, SquadOut } from './api';

/** Todas as squads com a composição de **uma** sprint já expandida. */
export interface SprintComposition {
  readonly sprintNumber: number;
  readonly squads: readonly SquadOut[];
}

export interface CompositionCell {
  readonly sprintNumber: number;
  readonly present: boolean;
  /** Nomes das outras squads em que a pessoa está naquela sprint (RN9). */
  readonly otherSquads: readonly string[];
}

export interface CompositionRow {
  readonly member: MemberOut;
  readonly cells: readonly CompositionCell[];
}

function membersOf(composition: SprintComposition, squadId: string): readonly MemberOut[] {
  return composition.squads.find((squad) => squad.id === squadId)?.members ?? [];
}

/**
 * Uma linha por pessoa, uma célula por sprint da janela.
 *
 * `members` é a lista que a tela mostra — as ativas, por §6.4 e pela RN-S3.
 * Quem foi inativado some daqui e **continua no dado**: quem preserva isso é
 * `memberIdsAfterToggle`, não esta função — e quem avisa que existe é
 * `inactiveWithComposition`.
 */
export function compositionRows(
  members: readonly MemberOut[],
  squadId: string,
  window: readonly SprintComposition[],
): CompositionRow[] {
  return members.map((member) => ({
    member,
    cells: window.map((composition) => ({
      sprintNumber: composition.sprintNumber,
      present: membersOf(composition, squadId).some((other) => other.id === member.id),
      // Só squad ativa entra na anotação: estar numa squad desativada não é o
      // conflito que a matriz existe para mostrar antes de virar alerta.
      otherSquads: composition.squads
        .filter(
          (squad) =>
            squad.id !== squadId &&
            squad.is_active &&
            squad.members.some((other) => other.id === member.id),
        )
        .map((squad) => squad.name),
    })),
  }));
}

/** Os ids gravados da squad naquela sprint, na ordem em que vieram. */
export function currentMemberIds(
  window: readonly SprintComposition[],
  squadId: string,
  sprintNumber: number,
): string[] {
  const composition = window.find((entry) => entry.sprintNumber === sprintNumber);
  if (!composition) return [];
  return membersOf(composition, squadId).map((member) => member.id);
}

/**
 * A lista que vai no `PUT /squads/{id}/memberships` depois de marcar ou
 * desmarcar uma célula.
 *
 * O `PUT` **substitui** a composição da sprint, então a lista precisa ser a
 * composição inteira — e não só quem a tela desenha. Uma pessoa inativada que
 * ainda tenha membership naquela sprint não aparece na matriz (RN-S3); montar
 * a lista a partir das caixas marcadas a apagaria em silêncio, e a regra diz o
 * contrário: a membership fica, como histórico — e `inactiveWithComposition`
 * avisa que ela está lá.
 */
export function memberIdsAfterToggle(
  currentIds: readonly string[],
  memberId: string,
  present: boolean,
): string[] {
  if (present) {
    return currentIds.includes(memberId) ? [...currentIds] : [...currentIds, memberId];
  }
  return currentIds.filter((id) => id !== memberId);
}

/**
 * Quem foi inativado e **ainda** tem composição na janela.
 *
 * A matriz só desenha pessoa ativa (§6.4), e a membership de quem saiu fica no
 * dado como histórico — é o que `memberIdsAfterToggle` preserva. As duas
 * coisas juntas criam um ponto cego: existe composição gravada que ninguém vê,
 * e ela reaparece inteira no dia em que a pessoa for reativada.
 *
 * O aviso fecha esse ponto cego sem mudar o modelo: diz que o dado existe, e
 * não oferece uma edição que a premissa manda não fazer.
 *
 * A resposta de `GET /squads?sprint_number=` traz a composição inteira, ativos
 * e inativos — nenhuma chamada nova é preciso para saber isto.
 */
export function inactiveWithComposition(
  window: readonly SprintComposition[],
  squadId: string,
): string[] {
  const found = new Map<string, string>();
  for (const composition of window) {
    for (const member of membersOf(composition, squadId)) {
      if (!member.is_active) found.set(member.id, member.name);
    }
  }
  return [...found.values()].sort((left, right) => left.localeCompare(right, 'pt-BR'));
}

/**
 * RN-S1: o representante não precisa estar na composição, mas se não estiver
 * na sprint atual a UI avisa — discreto, nunca erro.
 *
 * Sem sprint atual (RN12, nenhuma sprint começou) não há o que conferir.
 */
export function representativeIsAbsent(
  squad: SquadOut,
  window: readonly SprintComposition[],
  currentSprintNumber: number | null,
): boolean {
  if (!squad.representative_member_id || currentSprintNumber === null) return false;
  const composition = window.find((entry) => entry.sprintNumber === currentSprintNumber);
  if (!composition) return false;
  return !membersOf(composition, squad.id).some(
    (member) => member.id === squad.representative_member_id,
  );
}
