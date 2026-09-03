import { describe, expect, it } from 'vitest';
import type { AlertOut } from '../src/lib/api';
import {
  ALERT_TYPE_SEVERITY,
  alertContext,
  groupBySprint,
  mutedAlerts,
  openAlerts,
  warningCount,
  worstSeverity,
} from '../src/lib/alerts';

function alert(overrides: Partial<AlertOut> = {}): AlertOut {
  return {
    type: 'SQUAD_OVERLOADED',
    severity: 'WARNING',
    sprint_number: 19,
    subject_id: 'squad-alfa',
    entity_refs: [],
    message: 'Alfa está em duas iniciativas na Sprint 19.',
    fingerprint: 'abc',
    is_muted: false,
    mute_id: null,
    mute_reason: null,
    ...overrides,
  };
}

describe('groupBySprint', () => {
  it('agrupa por sprint, da mais próxima para a mais distante', () => {
    const groups = groupBySprint([
      alert({ sprint_number: 21, fingerprint: 'a' }),
      alert({ sprint_number: 19, fingerprint: 'b' }),
      alert({ sprint_number: 21, fingerprint: 'c' }),
    ]);
    expect(groups.map((group) => group.sprintNumber)).toEqual([19, 21]);
    expect(groups[1]!.alerts).toHaveLength(2);
  });

  it('põe aviso antes de informação dentro da sprint', () => {
    const groups = groupBySprint([
      alert({ type: 'MEMBER_IDLE', severity: 'INFO', fingerprint: 'a', message: 'A' }),
      alert({ severity: 'WARNING', fingerprint: 'b', message: 'B' }),
    ]);
    expect(groups[0]!.alerts.map((item) => item.severity)).toEqual(['WARNING', 'INFO']);
  });
});

describe('warningCount', () => {
  it('conta só WARNING não silenciado', () => {
    const items = [
      alert({ fingerprint: 'a' }),
      alert({ fingerprint: 'b', is_muted: true, mute_id: 'm', mute_reason: 'combinado' }),
      alert({ fingerprint: 'c', type: 'MEMBER_IDLE', severity: 'INFO' }),
    ];
    expect(warningCount(items)).toBe(1);
    expect(openAlerts(items)).toHaveLength(2);
    expect(mutedAlerts(items)).toHaveLength(1);
  });
});

describe('alertContext', () => {
  it('manda sobrecarga de squad para o planejamento filtrado na sprint', () => {
    expect(alertContext(alert()).href).toBe(
      '/planning?from=19&to=19&squad=squad-alfa',
    );
  });

  it('manda ociosidade para o planejamento da pessoa', () => {
    const context = alertContext(
      alert({ type: 'MEMBER_IDLE', severity: 'INFO', subject_id: 'membro-ana', sprint_number: 20 }),
    );
    expect(context.href).toBe('/planning?from=20&to=20&member=membro-ana');
  });

  it('manda squad vazia para a composição do time', () => {
    const context = alertContext(
      alert({ type: 'EMPTY_SQUAD', severity: 'INFO', subject_id: 'squad-gama', sprint_number: 21 }),
    );
    expect(context.href).toBe('/team?from=21&to=21&squad=squad-gama');
  });

  it('manda conflito de pessoa para a composição de uma das squads dela', () => {
    const context = alertContext(
      alert({
        type: 'MEMBER_CONFLICT',
        subject_id: 'membro-ana',
        entity_refs: [
          { type: 'squad', id: 'squad-alfa', name: 'Alfa' },
          { type: 'squad', id: 'squad-beta', name: 'Beta' },
        ],
      }),
    );
    expect(context.href).toBe('/team?from=19&to=19&squad=squad-alfa');
  });

  it('cai no planejamento quando o conflito não trouxe squad nenhuma', () => {
    const context = alertContext(
      alert({ type: 'MEMBER_CONFLICT', subject_id: 'membro-ana', entity_refs: [] }),
    );
    expect(context.href).toBe('/planning?from=19&to=19&member=membro-ana');
  });
});

describe('worstSeverity', () => {
  it('é aviso quando há pelo menos um aviso', () => {
    expect(worstSeverity(['MEMBER_IDLE', 'SQUAD_OVERLOADED'])).toBe('WARNING');
    expect(worstSeverity(['MEMBER_CONFLICT'])).toBe('WARNING');
  });

  it('é informação quando só há informação', () => {
    expect(worstSeverity(['MEMBER_IDLE', 'EMPTY_SQUAD'])).toBe('INFO');
  });

  it('é nulo quando a sprint não tem alerta nenhum', () => {
    expect(worstSeverity([])).toBeNull();
  });

  it('concorda com a severidade que o próprio alerta traz (§7.3)', () => {
    // A tabela é uma cópia do §7.3 para o `alerts_by_sprint`, que manda tipo
    // sem severidade. Se as duas divergirem, é aqui que aparece.
    expect(ALERT_TYPE_SEVERITY[alert().type]).toBe(alert().severity);
    const ocioso = alert({ type: 'MEMBER_IDLE', severity: 'INFO' });
    expect(ALERT_TYPE_SEVERITY[ocioso.type]).toBe(ocioso.severity);
  });
});
