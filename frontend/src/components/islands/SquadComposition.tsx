import { useMutation, useQueries, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, type MemberOut, type SquadOut } from '../../lib/api';
import { joinNames } from '../../lib/format';
import {
  compositionRows,
  currentMemberIds,
  inactiveWithComposition,
  memberIdsAfterToggle,
  representativeIsAbsent,
  type SprintComposition,
} from '../../lib/team';
import { Avatar } from '../ui/Avatar';
import { EmptyState, ErrorState, Skeleton, describeError } from '../ui/States';
import { TBody, THead, Table, Td, Th, Tr } from '../ui/Table';
import { cx } from '../ui/cx';

/**
 * A matriz membro × sprint de uma squad (§10.3, bloco 3 da tela de time).
 *
 * É o que torna o caso real editável: alguém no Boreal até a Sprint 19 e no
 * Aurora da 20 em diante não é conflito nenhum, porque composição é por sprint
 * (D11) — e é aqui que isso se escreve, uma célula por sprint.
 *
 * Cada célula também diz em qual **outra** squad a pessoa já está naquela
 * sprint. É onde o conflito fica visível antes de virar `MEMBER_CONFLICT`.
 *
 * O dado vem de uma chamada por sprint da janela (`GET /squads?sprint_number=`),
 * cada uma trazendo todas as squads com a composição daquela sprint: as duas
 * perguntas da célula saem da mesma resposta.
 */
export interface SquadCompositionProps {
  readonly squad: SquadOut;
  readonly members: readonly MemberOut[];
  readonly sprintNumbers: readonly number[];
  readonly currentSprintNumber: number | null;
}

export function SquadComposition({
  squad,
  members,
  sprintNumbers,
  currentSprintNumber,
}: SquadCompositionProps) {
  const client = useQueryClient();
  const [pendingCell, setPendingCell] = useState<string | null>(null);

  const results = useQueries({
    queries: sprintNumbers.map((number) => ({
      queryKey: ['squads', { sprint_number: number }],
      queryFn: ({ signal }: { signal: AbortSignal }) =>
        api.listSquads({ sprint_number: number }, signal),
    })),
  });

  const failed = results.find((result) => result.isError);
  const loading = results.some((result) => result.isPending);

  const window: SprintComposition[] = results.flatMap((result, index) =>
    result.data
      ? [{ sprintNumber: sprintNumbers[index]!, squads: result.data }]
      : [],
  );

  /**
   * O `PUT` **substitui** a composição da sprint, então manda a lista inteira
   * — e ela sai do que está gravado, não das caixas marcadas. Quem foi
   * inativado não aparece na matriz (RN-S3) e continua no dado.
   */
  const toggle = useMutation({
    mutationFn: (input: { sprintNumber: number; memberId: string; present: boolean }) =>
      api.setMemberships(squad.id, {
        sprint_from: input.sprintNumber,
        sprint_to: input.sprintNumber,
        member_ids: memberIdsAfterToggle(
          currentMemberIds(window, squad.id, input.sprintNumber),
          input.memberId,
          input.present,
        ),
      }),
    onSettled: () => {
      setPendingCell(null);
      void client.invalidateQueries({ queryKey: ['squads'] });
      void client.invalidateQueries({ queryKey: ['alerts'] });
      void client.invalidateQueries({ queryKey: ['planning'] });
    },
  });

  if (failed) {
    return (
      <ErrorState
        what="a composição da squad"
        error={failed.error}
        onRetry={() => results.forEach((result) => void result.refetch())}
      />
    );
  }

  if (loading && window.length === 0) return <Skeleton lines={4} />;

  if (members.length === 0) {
    return (
      <EmptyState message="Nenhuma pessoa ativa. Cadastre o time acima para montar a composição." />
    );
  }

  const rows = compositionRows(members, squad.id, window);
  const absentRepresentative = representativeIsAbsent(squad, window, currentSprintNumber);
  const inactive = inactiveWithComposition(window, squad.id);

  return (
    <div className="flex flex-col gap-2">
      {absentRepresentative && (
        // RN-S1: aviso discreto, nunca erro. O representante é uma ponte e pode
        // legitimamente não executar nada na squad.
        <p className="m-0 text-12 text-warning">
          O representante desta squad não está na composição da sprint atual.
        </p>
      )}

      {inactive.length > 0 && (
        // RN-S3: a matriz só desenha pessoa ativa e a membership de quem saiu
        // fica no dado como histórico. Sem este aviso existiria composição
        // gravada que ninguém vê — e que reaparece inteira se a pessoa for
        // reativada. Discreto e sem ação: a regra manda preservar o dado.
        <p className="m-0 text-12 text-text-subtle">
          {joinNames(inactive)}{' '}
          {inactive.length === 1
            ? 'está inativa e ainda tem composição'
            : 'estão inativas e ainda têm composição'}{' '}
          nesta janela. A membership fica como histórico e não aparece na matriz.
        </p>
      )}

      {toggle.isError && (
        <p className="m-0 rounded-sm border border-danger bg-danger-soft p-2 text-12 text-danger">
          {describeError(toggle.error)}
        </p>
      )}

      <div className="overflow-x-auto">
        <Table>
          <THead>
            <tr>
              <Th className="min-w-[200px]">Pessoa</Th>
              {sprintNumbers.map((number) => (
                <Th
                  key={number}
                  className={cx(
                    'w-24 text-center',
                    number === currentSprintNumber && 'bg-primary-soft text-primary',
                  )}
                >
                  {number}
                </Th>
              ))}
            </tr>
          </THead>
          <TBody>
            {rows.map((row) => (
              <Tr key={row.member.id}>
                <Td>
                  <span className="flex items-center gap-2">
                    <Avatar name={row.member.name} decorative />
                    <span className="truncate">{row.member.name}</span>
                    {row.member.id === squad.representative_member_id && (
                      <span className="text-11 text-text-subtle">(representante)</span>
                    )}
                  </span>
                </Td>
                {row.cells.map((cell) => {
                  const key = `${row.member.id}-${cell.sprintNumber}`;
                  const conflicting = cell.present && cell.otherSquads.length > 0;
                  return (
                    <Td
                      key={cell.sprintNumber}
                      className={cx(
                        'text-center',
                        cell.sprintNumber === currentSprintNumber && 'bg-primary-soft/40',
                      )}
                    >
                      <span className="inline-flex flex-col items-center gap-px">
                        <input
                          type="checkbox"
                          checked={cell.present}
                          disabled={pendingCell === key}
                          aria-label={`${row.member.name} na squad ${squad.name} na Sprint ${cell.sprintNumber}`}
                          onChange={(event) => {
                            setPendingCell(key);
                            toggle.mutate({
                              sprintNumber: cell.sprintNumber,
                              memberId: row.member.id,
                              present: event.target.checked,
                            });
                          }}
                          className="size-4 accent-primary disabled:opacity-50"
                        />
                        {cell.otherSquads.length > 0 && (
                          <span
                            title={`Também em: ${cell.otherSquads.join(', ')}`}
                            className={cx(
                              'max-w-[80px] truncate text-11',
                              conflicting ? 'font-semibold text-danger' : 'text-text-subtle',
                            )}
                          >
                            {cell.otherSquads.join(', ')}
                          </span>
                        )}
                      </span>
                    </Td>
                  );
                })}
              </Tr>
            ))}
          </TBody>
        </Table>
      </div>

      <p className="m-0 text-11 text-text-subtle">
        A marca vermelha é a pessoa em duas squads na mesma sprint: aceito no dado e
        sinalizado como conflito (RN9), nunca bloqueado. Squad sem ninguém numa sprint
        em que tem alocação vira um aviso informativo.
      </p>
    </div>
  );
}
