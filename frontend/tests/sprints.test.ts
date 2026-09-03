import { describe, expect, it } from 'vitest';
import {
  addDays,
  isValidSprintRange,
  lengthInDays,
  suggestedEndDate,
} from '../src/lib/sprints';

describe('addDays', () => {
  it('atravessa a virada de mês sem cair no fuso', () => {
    // A Sprint 18 do dado real: segunda 31/08 a sexta 11/09.
    expect(addDays('2026-08-31', 11)).toBe('2026-09-11');
  });

  it('atravessa a virada de ano', () => {
    expect(addDays('2026-12-28', 11)).toBe('2027-01-08');
  });

  it('devolve a entrada quando ela não é uma data', () => {
    expect(addDays('', 11)).toBe('');
  });
});

describe('suggestedEndDate', () => {
  it('sugere as duas semanas de calendário do §6.6', () => {
    expect(suggestedEndDate('2026-09-14')).toBe('2026-09-25');
  });
});

describe('lengthInDays', () => {
  it('conta o intervalo fechado: a sprint padrão tem 12 dias', () => {
    expect(lengthInDays('2026-08-31', '2026-09-11')).toBe(12);
  });

  it('devolve nulo para data inválida', () => {
    expect(lengthInDays('2026-08-31', '')).toBeNull();
  });
});

describe('isValidSprintRange', () => {
  it('exige fim depois do início', () => {
    expect(isValidSprintRange('2026-08-31', '2026-09-11')).toBe(true);
    expect(isValidSprintRange('2026-08-31', '2026-08-31')).toBe(false);
    expect(isValidSprintRange('2026-09-11', '2026-08-31')).toBe(false);
    expect(isValidSprintRange('', '2026-09-11')).toBe(false);
  });
});
