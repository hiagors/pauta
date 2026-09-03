/* Formatação e rótulos.
 *
 * O backend fala em inglês (`HIGH`, `SQUAD_OVERLOADED`) porque é código; a UI
 * fala português (§14). O mapa de um para o outro mora aqui, num lugar só, para
 * que "Alta" não seja escrita de três jeitos em três telas.
 */
import type { Schemas } from './api';

/** Mesma constante do domínio (`value_objects/color.py`), para projeto sem cor. */
export const DEFAULT_PROJECT_COLOR = '#7A869A';

export const PRIORITY_LABEL: Record<Schemas['Priority'], string> = {
  HIGH: 'Alta',
  MEDIUM: 'Média',
  LOW: 'Baixa',
};

export const INITIATIVE_STATUS_LABEL: Record<Schemas['InitiativeStatus'], string> = {
  BACKLOG: 'Backlog',
  PLANNED: 'Planejada',
  IN_PROGRESS: 'Em andamento',
  DEPRIORITIZED: 'Despriorizada',
  DONE: 'Concluída',
  CANCELLED: 'Cancelada',
};

export const ALERT_TYPE_LABEL: Record<Schemas['AlertType'], string> = {
  SQUAD_OVERLOADED: 'Squad sobrecarregada',
  MEMBER_CONFLICT: 'Membro em conflito',
  MEMBER_IDLE: 'Membro sem alocação',
  EMPTY_SQUAD: 'Squad sem composição',
};

export const SEVERITY_LABEL: Record<Schemas['Severity'], string> = {
  WARNING: 'Aviso',
  INFO: 'Informação',
};

export const ASSIGNEE_KIND_LABEL: Record<Schemas['AssigneeKind'], string> = {
  squad: 'Squad',
  member: 'Pessoa',
};

/**
 * Formata a data ISO (`YYYY-MM-DD`) que a API devolve.
 *
 * O corte é feito na string, e não com `new Date(iso)`: o construtor lê a data
 * simples como UTC, e num fuso negativo — o nosso — 31/08 volta como 30/08.
 */
export function formatDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-');
  if (!year || !month || !day) return isoDate;
  return `${day}/${month}/${year}`;
}

/** "31/08 a 11/09/2026" quando o ano é o mesmo; datas inteiras quando não é. */
export function formatDateRange(startIso: string, endIso: string): string {
  const start = formatDate(startIso);
  const end = formatDate(endIso);
  if (startIso.slice(0, 4) === endIso.slice(0, 4)) {
    return `${start.slice(0, 5)} a ${end}`;
  }
  return `${start} a ${end}`;
}

/** Iniciais do avatar (§10.1): uma letra para nome único, duas para nome composto. */
export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  const first = parts[0]!.charAt(0);
  const last = parts.length > 1 ? parts[parts.length - 1]!.charAt(0) : '';
  return (first + last).toUpperCase();
}

/** Cor da barra da grade: a do projeto, ou a default do §10.2 quando não há. */
export function projectColor(color: string | null | undefined): string {
  return color ?? DEFAULT_PROJECT_COLOR;
}

/**
 * "1 iniciativa", "3 iniciativas", "nenhuma iniciativa".
 *
 * O plural do português não sai de um `+ 's'` genérico, então o chamador passa
 * as duas formas. `zero` é opcional porque nem todo contador quer "nenhuma".
 */
export function pluralize(
  count: number,
  singular: string,
  plural: string,
  zero?: string,
): string {
  if (count === 0 && zero !== undefined) return zero;
  return `${count} ${count === 1 ? singular : plural}`;
}

/**
 * `"a"`, `"a e b"`, `"a, b e c"` — em português, sem vírgula antes do "e".
 *
 * A mesma regra que o `_join_names` do domínio aplica nas frases de alerta.
 * Está repetida aqui, e não importada, porque o backend a usa para montar o
 * `message` que já chega pronto: o front só precisa dela para as frases que
 * **ele** escreve.
 */
export function joinNames(names: readonly string[]): string {
  if (names.length === 0) return '';
  if (names.length === 1) return names[0]!;
  return `${names.slice(0, -1).join(', ')} e ${names[names.length - 1]}`;
}

/**
 * Cor de texto legível sobre um fundo `#RRGGBB`.
 *
 * A cor da barra da grade é escolhida no cadastro do projeto e pode ser
 * qualquer uma: texto branco fixo some sobre amarelo, texto escuro fixo some
 * sobre azul-marinho. O corte é a luminância relativa da WCAG — acima dela o
 * texto escuro do tema contrasta melhor; abaixo, o branco.
 */
export function readableTextOn(background: string): string {
  const hex = background.replace('#', '');
  if (hex.length !== 6) return '#FFFFFF';
  const channel = (offset: number) => {
    const value = Number.parseInt(hex.slice(offset, offset + 2), 16) / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  };
  const luminance = 0.2126 * channel(0) + 0.7152 * channel(2) + 0.0722 * channel(4);
  return luminance > 0.45 ? '#172B4D' : '#FFFFFF';
}

/** Rótulo curto de um intervalo de sprints: "18" quando é uma só, "18–20" quando não. */
export function formatSprintRange(from: number, to: number): string {
  return from === to ? String(from) : `${from}–${to}`;
}
