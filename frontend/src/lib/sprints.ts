/* Apoio da tela de sprints (§10.3).
 *
 * O cálculo da proposta é do backend (RN10, `GET /sprints/next/preview`) e não
 * se repete aqui. O que este arquivo faz é aritmética de data ISO para o
 * formulário: sugerir o fim quando o usuário escolhe o começo, e dizer quantos
 * dias o intervalo tem.
 */

/** O padrão do §6.6: duas semanas de calendário, da segunda à sexta seguinte. */
export const DEFAULT_SPRINT_LENGTH_DAYS = 11;

/**
 * Soma dias a uma data ISO (`YYYY-MM-DD`) sem sair do calendário civil.
 *
 * O `T00:00:00Z` no meio é o mesmo cuidado de `formatDate`: `new Date(iso)`
 * sozinho já lê a data como UTC, mas somar dias e formatar de volta com
 * `toISOString()` num fuso negativo devolveria o dia anterior. Ancorar em UTC
 * dos dois lados mantém a conta fechada.
 */
export function addDays(isoDate: string, days: number): string {
  const parsed = Date.parse(`${isoDate}T00:00:00Z`);
  if (Number.isNaN(parsed)) return isoDate;
  return new Date(parsed + days * 86_400_000).toISOString().slice(0, 10);
}

/**
 * O fim sugerido para um começo escolhido à mão.
 *
 * É sugestão de formulário, não regra: `POST /sprints` aceita datas
 * arbitrárias que respeitem as invariantes do §6.6, e quem valida o conjunto
 * inteiro é o backend.
 */
export function suggestedEndDate(startIso: string): string {
  return addDays(startIso, DEFAULT_SPRINT_LENGTH_DAYS);
}

/** Dias de calendário do intervalo fechado — 12 na sprint padrão do §6.6. */
export function lengthInDays(startIso: string, endIso: string): number | null {
  const start = Date.parse(`${startIso}T00:00:00Z`);
  const end = Date.parse(`${endIso}T00:00:00Z`);
  if (Number.isNaN(start) || Number.isNaN(end)) return null;
  return Math.round((end - start) / 86_400_000) + 1;
}

/** `end_date > start_date` (§6.6). O resto das invariantes é do backend. */
export function isValidSprintRange(startIso: string, endIso: string): boolean {
  const length = lengthInDays(startIso, endIso);
  return length !== null && length > 1;
}
