import { describe, expect, it } from 'vitest';
import {
  ALERT_TYPE_LABEL,
  INITIATIVE_STATUS_LABEL,
  PRIORITY_LABEL,
  formatDate,
  formatDateRange,
  formatSprintRange,
  initials,
  pluralize,
  projectColor,
  readableTextOn,
  DEFAULT_PROJECT_COLOR,
} from '../src/lib/format';

describe('formatDate', () => {
  it('escreve a data ISO no formato brasileiro', () => {
    expect(formatDate('2026-08-31')).toBe('31/08/2026');
  });

  it('não perde um dia em fuso negativo', () => {
    // `new Date('2026-08-31')` é meia-noite UTC, que em UTC-3 ainda é 30/08.
    // O corte é feito na string justamente para o dia não andar para trás.
    expect(formatDate('2026-01-01')).toBe('01/01/2026');
  });

  it('devolve a entrada quando ela não é uma data ISO', () => {
    expect(formatDate('sem data')).toBe('sem data');
  });
});

describe('formatDateRange', () => {
  it('omite o ano da primeira data quando as duas são do mesmo ano', () => {
    expect(formatDateRange('2026-08-31', '2026-09-11')).toBe('31/08 a 11/09/2026');
  });

  it('escreve os dois anos na virada', () => {
    expect(formatDateRange('2026-12-28', '2027-01-08')).toBe('28/12/2026 a 08/01/2027');
  });
});

describe('initials', () => {
  it('usa primeira e última palavra do nome composto', () => {
    expect(initials('Ana Martins')).toBe('AM');
  });

  it('usa uma letra só quando o nome é único', () => {
    expect(initials('Carla')).toBe('C');
  });

  it('ignora espaço sobrando', () => {
    expect(initials('  Diana   Martins  ')).toBe('DM');
  });

  it('não quebra com nome vazio', () => {
    expect(initials('   ')).toBe('?');
  });
});

describe('projectColor', () => {
  it('devolve a cor gravada', () => {
    expect(projectColor('#0052CC')).toBe('#0052CC');
  });

  it('cai na cor default do §10.2 quando o projeto não tem cor', () => {
    expect(projectColor(null)).toBe(DEFAULT_PROJECT_COLOR);
  });
});

describe('pluralize', () => {
  it('flexiona pelo par que o chamador passou', () => {
    expect(pluralize(1, 'iniciativa', 'iniciativas')).toBe('1 iniciativa');
    expect(pluralize(3, 'iniciativa', 'iniciativas')).toBe('3 iniciativas');
  });

  it('usa a forma de zero quando ela existe', () => {
    expect(pluralize(0, 'iniciativa', 'iniciativas', 'nenhuma')).toBe('nenhuma');
    expect(pluralize(0, 'iniciativa', 'iniciativas')).toBe('0 iniciativas');
  });
});

describe('rótulos', () => {
  it('traduz todo status, prioridade e tipo de alerta do contrato', () => {
    // Os mapas são `Record` completo: um valor novo no OpenAPI quebra o `tsc`
    // aqui antes de aparecer em branco na tela.
    expect(Object.keys(INITIATIVE_STATUS_LABEL)).toHaveLength(6);
    expect(Object.keys(PRIORITY_LABEL)).toHaveLength(3);
    expect(Object.keys(ALERT_TYPE_LABEL)).toHaveLength(4);
    expect(INITIATIVE_STATUS_LABEL.IN_PROGRESS).toBe('Em andamento');
    expect(ALERT_TYPE_LABEL.MEMBER_IDLE).toBe('Membro sem alocação');
  });
});

describe('formatSprintRange', () => {
  it('mostra um número só quando a barra ocupa uma sprint', () => {
    expect(formatSprintRange(19, 19)).toBe('19');
  });

  it('mostra o intervalo quando ocupa mais de uma', () => {
    expect(formatSprintRange(18, 22)).toBe('18–22');
  });
});

describe('readableTextOn', () => {
  it('usa texto branco sobre o azul de ação', () => {
    expect(readableTextOn('#0052CC')).toBe('#FFFFFF');
  });

  it('usa o texto escuro do tema sobre fundo claro', () => {
    expect(readableTextOn('#FFF7D6')).toBe('#172B4D');
    expect(readableTextOn('#FFFFFF')).toBe('#172B4D');
  });

  it('usa branco sobre preto', () => {
    expect(readableTextOn('#000000')).toBe('#FFFFFF');
  });

  it('não quebra com valor fora do formato', () => {
    expect(readableTextOn('vermelho')).toBe('#FFFFFF');
  });
});
