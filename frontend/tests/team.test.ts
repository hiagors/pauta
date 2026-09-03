import { describe, expect, it } from 'vitest';
import type { MemberOut, SquadOut } from '../src/lib/api';
import {
  compositionRows,
  currentMemberIds,
  memberIdsAfterToggle,
  representativeIsAbsent,
  type SprintComposition,
} from '../src/lib/team';

function member(name: string, overrides: Partial<MemberOut> = {}): MemberOut {
  return {
    id: `membro-${name}`,
    name,
    short_name: name,
    role: '',
    is_active: true,
    ...overrides,
  };
}

function squad(
  name: string,
  members: readonly MemberOut[],
  overrides: Partial<SquadOut> = {},
): SquadOut {
  return {
    id: `squad-${name}`,
    name,
    representative_member_id: null,
    is_active: true,
    members: [...members],
    ...overrides,
  };
}

const ana = member('Ana');
const carla = member('Carla');
const diana = member('Diana', { is_active: false });

/** Carla no Boreal (Beta) até a 19 e no Aurora (Alfa) da 20 em diante (§6.5). */
const WINDOW: SprintComposition[] = [
  { sprintNumber: 19, squads: [squad('Alfa', [ana]), squad('Beta', [ana, carla])] },
  { sprintNumber: 20, squads: [squad('Alfa', [carla]), squad('Beta', [])] },
];

describe('compositionRows', () => {
  it('marca a célula em que a pessoa está na squad escolhida', () => {
    const rows = compositionRows([ana, carla], 'squad-Alfa', WINDOW);
    expect(rows[0]!.cells.map((cell) => cell.present)).toEqual([true, false]);
    expect(rows[1]!.cells.map((cell) => cell.present)).toEqual([false, true]);
  });

  it('anota a outra squad da pessoa naquela sprint', () => {
    const rows = compositionRows([ana], 'squad-Alfa', WINDOW);
    expect(rows[0]!.cells[0]!.otherSquads).toEqual(['Beta']);
    expect(rows[0]!.cells[1]!.otherSquads).toEqual([]);
  });

  it('não conta squad inativa como outra squad', () => {
    const rows = compositionRows([ana], 'squad-Alfa', [
      {
        sprintNumber: 19,
        squads: [squad('Alfa', [ana]), squad('Beta', [ana], { is_active: false })],
      },
    ]);
    expect(rows[0]!.cells[0]!.otherSquads).toEqual([]);
  });

  it('não acusa conflito quando as sprints não se cruzam (o caso da Carla)', () => {
    // Conflito é estar nas duas ao mesmo tempo: presente na squad escolhida
    // **e** anotada em outra. Estar só na outra é informação, não conflito.
    const rows = compositionRows([carla], 'squad-Alfa', WINDOW);
    const conflicting = rows[0]!.cells.filter(
      (cell) => cell.present && cell.otherSquads.length > 0,
    );
    expect(conflicting).toEqual([]);
    expect(rows[0]!.cells.map((cell) => cell.otherSquads)).toEqual([['Beta'], []]);
  });

  it('acusa conflito quando a pessoa está nas duas na mesma sprint (RN9)', () => {
    const rows = compositionRows([ana], 'squad-Alfa', WINDOW);
    expect(rows[0]!.cells[0]!.present).toBe(true);
    expect(rows[0]!.cells[0]!.otherSquads).toEqual(['Beta']);
  });

  it('devolve uma linha por pessoa e uma célula por sprint da janela', () => {
    const rows = compositionRows([ana, carla], 'squad-Alfa', WINDOW);
    expect(rows).toHaveLength(2);
    expect(rows[0]!.cells.map((cell) => cell.sprintNumber)).toEqual([19, 20]);
  });
});

describe('currentMemberIds', () => {
  it('lê os ids gravados da squad naquela sprint', () => {
    expect(currentMemberIds(WINDOW, 'squad-Beta', 19)).toEqual([ana.id, carla.id]);
  });

  it('devolve vazio para sprint fora da janela', () => {
    expect(currentMemberIds(WINDOW, 'squad-Beta', 25)).toEqual([]);
  });
});

describe('memberIdsAfterToggle', () => {
  it('acrescenta quem foi marcado', () => {
    expect(memberIdsAfterToggle([ana.id], carla.id, true)).toEqual([ana.id, carla.id]);
  });

  it('não duplica quem já estava', () => {
    expect(memberIdsAfterToggle([ana.id], ana.id, true)).toEqual([ana.id]);
  });

  it('remove quem foi desmarcado', () => {
    expect(memberIdsAfterToggle([ana.id, carla.id], ana.id, false)).toEqual([carla.id]);
  });

  it('preserva a membership de quem foi inativado e não aparece na matriz', () => {
    // Premissa A3 do §16: a membership fica no dado, como histórico. Montar a
    // lista a partir das caixas marcadas a apagaria em silêncio.
    const gravado = [ana.id, diana.id];
    expect(memberIdsAfterToggle(gravado, carla.id, true)).toEqual([
      ana.id,
      diana.id,
      carla.id,
    ]);
  });
});

describe('representativeIsAbsent', () => {
  const alfa = squad('Alfa', [ana], { representative_member_id: carla.id });

  it('avisa quando o representante não está na composição da sprint atual', () => {
    expect(representativeIsAbsent(alfa, WINDOW, 19)).toBe(true);
  });

  it('cala quando ele está', () => {
    expect(representativeIsAbsent(alfa, WINDOW, 20)).toBe(false);
  });

  it('cala quando a squad não tem representante', () => {
    expect(representativeIsAbsent(squad('Alfa', [ana]), WINDOW, 19)).toBe(false);
  });

  it('cala quando nenhuma sprint começou (RN12)', () => {
    expect(representativeIsAbsent(alfa, WINDOW, null)).toBe(false);
  });
});
