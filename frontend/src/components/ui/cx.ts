/** Junta classes ignorando `false`, `null` e `undefined`. Existe para os
 * componentes daqui não repetirem `[a, b].filter(Boolean).join(' ')`. */
export function cx(...values: Array<string | false | null | undefined>): string {
  return values.filter(Boolean).join(' ');
}
