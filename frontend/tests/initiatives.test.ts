import { describe, expect, it } from 'vitest';
import type { InitiativeOut, ProjectOut } from '../src/lib/api';
import {
  groupByProject,
  isHexColor,
  isTerminal,
  manualTransitions,
  parseEstimate,
  sortInitiatives,
} from '../src/lib/initiatives';

function project(name: string, overrides: Partial<ProjectOut> = {}): ProjectOut {
  return {
    id: `projeto-${name}`,
    name,
    description: '',
    color: null,
    is_capacity_reserve: false,
    is_active: true,
    ...overrides,
  };
}

function initiative(
  name: string,
  overrides: Partial<InitiativeOut> = {},
): InitiativeOut {
  return {
    id: `iniciativa-${name}`,
    project_id: 'projeto-Aurora',
    name,
    layer: null,
    description: '',
    priority: 'MEDIUM',
    estimated_sprints: null,
    status: 'BACKLOG',
    entered_at: '2026-09-01',
    ...overrides,
  };
}

describe('manualTransitions', () => {
  it('não oferece a volta ao backlog para quem já foi planejado', () => {
    expect(manualTransitions('PLANNED')).not.toContain('BACKLOG');
    expect(manualTransitions('IN_PROGRESS')).not.toContain('BACKLOG');
    expect(manualTransitions('DEPRIORITIZED')).not.toContain('BACKLOG');
  });

  it('oferece despriorizar só a partir de em andamento (§6.3)', () => {
    expect(manualTransitions('IN_PROGRESS')).toContain('DEPRIORITIZED');
    expect(manualTransitions('BACKLOG')).not.toContain('DEPRIORITIZED');
    expect(manualTransitions('PLANNED')).not.toContain('DEPRIORITIZED');
  });

  it('deixa despriorizada voltar para planejada ou em andamento', () => {
    expect(manualTransitions('DEPRIORITIZED')).toEqual([
      'PLANNED',
      'IN_PROGRESS',
      'CANCELLED',
    ]);
  });

  it('permite cancelar de qualquer status não terminal', () => {
    for (const status of ['BACKLOG', 'PLANNED', 'IN_PROGRESS', 'DEPRIORITIZED'] as const) {
      expect(manualTransitions(status)).toContain('CANCELLED');
    }
  });

  it('não tem saída dos terminais', () => {
    expect(isTerminal('DONE')).toBe(true);
    expect(isTerminal('CANCELLED')).toBe(true);
    expect(isTerminal('BACKLOG')).toBe(false);
  });
});

describe('sortInitiatives', () => {
  it('ordena por prioridade, depois status, depois nome', () => {
    const sorted = sortInitiatives([
      initiative('Portal Externo', { priority: 'LOW' }),
      initiative('API de Cobrança', { priority: 'HIGH', status: 'IN_PROGRESS' }),
      initiative('Catálogo V1', { priority: 'HIGH', status: 'BACKLOG' }),
    ]);
    expect(sorted.map((item) => item.name)).toEqual([
      'Catálogo V1',
      'API de Cobrança',
      'Portal Externo',
    ]);
  });

  it('não muta a lista recebida', () => {
    const original = [initiative('B'), initiative('A')];
    sortInitiatives(original);
    expect(original.map((item) => item.name)).toEqual(['B', 'A']);
  });
});

describe('groupByProject', () => {
  const aurora = project('Aurora');
  const boreal = project('Boreal', { id: 'projeto-Boreal' });
  const catalogo = initiative('Catálogo V1');
  const portal = initiative('Portal Externo', { project_id: 'projeto-Boreal' });

  it('agrupa cada iniciativa no projeto dela, em ordem alfabética', () => {
    const groups = groupByProject([boreal, aurora], [portal, catalogo]);
    expect(groups.map((group) => group.project.name)).toEqual(['Aurora', 'Boreal']);
    expect(groups[0]!.initiatives.map((item) => item.name)).toEqual(['Catálogo V1']);
  });

  it('mantém o projeto sem iniciativa visível quando não há filtro', () => {
    const groups = groupByProject([aurora, boreal], [catalogo]);
    expect(groups).toHaveLength(2);
    expect(groups[1]!.initiatives).toEqual([]);
  });

  it('some com o projeto vazio quando a lista veio filtrada', () => {
    const groups = groupByProject([aurora, boreal], [catalogo], { dropEmpty: true });
    expect(groups.map((group) => group.project.name)).toEqual(['Aurora']);
  });

  it('ignora iniciativa de projeto que não está na lista', () => {
    const groups = groupByProject([aurora], [catalogo, portal]);
    expect(groups[0]!.initiatives.map((item) => item.name)).toEqual(['Catálogo V1']);
  });
});

describe('isHexColor', () => {
  it('aceita só `#RRGGBB`', () => {
    expect(isHexColor('#0052CC')).toBe(true);
    expect(isHexColor('#0052cc')).toBe(true);
    expect(isHexColor('#05C')).toBe(false);
    expect(isHexColor('0052CC')).toBe(false);
    expect(isHexColor('azul')).toBe(false);
  });
});

describe('parseEstimate', () => {
  it('trata vazio como sem estimativa', () => {
    expect(parseEstimate('')).toBeNull();
    expect(parseEstimate('   ')).toBeNull();
  });

  it('aceita inteiro maior que zero', () => {
    expect(parseEstimate('3')).toBe(3);
  });

  it('recusa zero, negativo e fracionário', () => {
    expect(parseEstimate('0')).toBeUndefined();
    expect(parseEstimate('-2')).toBeUndefined();
    expect(parseEstimate('1.5')).toBeUndefined();
    expect(parseEstimate('duas')).toBeUndefined();
  });
});
