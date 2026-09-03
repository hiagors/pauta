import { useQuery } from '@tanstack/react-query';
import { useState, type ReactNode } from 'react';
import { api, type MemberOut, type SprintOut, type SquadOut } from '../../lib/api';
import { pluralize } from '../../lib/format';
import { withQuery } from '../../lib/query';
import { useUrlState } from '../../lib/url-state';
import { Avatar } from '../ui/Avatar';
import { Button } from '../ui/Button';
import { Lozenge } from '../ui/Lozenge';
import { Select } from '../ui/Select';
import { Card, EmptyState, ErrorState, Skeleton } from '../ui/States';
import { TBody, THead, Table, Td, Th, Tr } from '../ui/Table';
import { ToastProvider } from '../ui/Toast';
import { MemberDrawer } from './MemberDrawer';
import { SquadComposition } from './SquadComposition';
import { SquadDrawer } from './SquadDrawer';

/**
 * A tela `/team` (§10.3): três blocos na mesma página — pessoas, squads e a
 * composição por sprint.
 *
 * Uma página só, e não três, porque as três leituras se respondem: quem existe,
 * como o time está agrupado e quem está em qual squad em qual sprint. Separar
 * obrigaria a navegar para conferir o que a matriz já mostra ao lado.
 *
 * A squad e a janela de sprints da matriz vivem na URL: mandar o link de uma
 * composição específica tem que abrir aquela composição.
 */
const DEFAULTS = { squad: '', from: '', to: '' } as const;
type TeamParams = { -readonly [K in keyof typeof DEFAULTS]: string };
const BASE: TeamParams = { ...DEFAULTS };

/** Quantas sprints a matriz mostra quando a URL não pede outra coisa. */
const WINDOW_SIZE = 6;

/**
 * A janela default: da sprint atual (RN12) em diante.
 *
 * O passado não se edita — a composição de uma sprint que já aconteceu é
 * histórico. Sem sprint atual (nenhuma começou), a janela abre na primeira
 * cadastrada.
 */
function defaultWindow(sprints: readonly SprintOut[]): number[] {
  // `GET /sprints` já vem com `number` crescente (a porta o promete), então a
  // posição da sprint atual na lista é a posição dela na janela.
  const current = sprints.findIndex((sprint) => sprint.is_current);
  const start = current >= 0 ? current : 0;
  return sprints.slice(start, start + WINDOW_SIZE).map((sprint) => sprint.number);
}

/** O intervalo pedido na URL, recortado no que existe de fato. */
function requestedWindow(
  sprints: readonly SprintOut[],
  from: string,
  to: string,
): number[] | null {
  const fromNumber = Number(from);
  const toNumber = Number(to);
  if (!Number.isInteger(fromNumber) || from === '') return null;
  const end = Number.isInteger(toNumber) && to !== '' ? toNumber : fromNumber;
  const numbers = sprints
    .map((sprint) => sprint.number)
    .filter((number) => number >= fromNumber && number <= end);
  return numbers.length > 0 ? numbers : null;
}

function TeamScreen() {
  const [params, patch, mounted] = useUrlState<TeamParams>(BASE);
  const [editingMember, setEditingMember] = useState<MemberOut | null | undefined>(undefined);
  const [editingSquad, setEditingSquad] = useState<SquadOut | null | undefined>(undefined);

  const members = useQuery({
    queryKey: ['members', {}],
    queryFn: ({ signal }) => api.listMembers(undefined, signal),
    enabled: mounted,
  });
  const squads = useQuery({
    queryKey: ['squads', {}],
    queryFn: ({ signal }) => api.listSquads(undefined, signal),
    enabled: mounted,
  });
  const sprints = useQuery({
    queryKey: ['sprints', {}],
    queryFn: ({ signal }) => api.listSprints(undefined, signal),
    enabled: mounted,
  });

  const activeMembers = (members.data ?? []).filter((member) => member.is_active);
  const allSprints = sprints.data ?? [];
  const sprintNumbers =
    requestedWindow(allSprints, params.from, params.to) ?? defaultWindow(allSprints);
  const currentSprintNumber =
    allSprints.find((sprint) => sprint.is_current)?.number ?? null;
  const selectedSquad =
    (squads.data ?? []).find((squad) => squad.id === params.squad) ??
    (squads.data ?? []).find((squad) => squad.is_active) ??
    null;

  return (
    <div className="flex flex-col gap-5">
      <Block
        title="Pessoas"
        count={members.data?.length}
        singular="pessoa"
        plural="pessoas"
        action={
          <Button variant="primary" data-primary-action onClick={() => setEditingMember(null)}>
            Nova pessoa
          </Button>
        }
      >
        {!mounted || members.isPending ? (
          <Skeleton lines={3} />
        ) : members.isError ? (
          <ErrorState
            what="as pessoas"
            error={members.error}
            onRetry={() => void members.refetch()}
          />
        ) : members.data.length === 0 ? (
          <EmptyState
            message="Nenhuma pessoa cadastrada. Cadastre o time para montar as squads."
            action={
              <Button variant="primary" onClick={() => setEditingMember(null)}>
                Nova pessoa
              </Button>
            }
          />
        ) : (
          <Table>
            <THead>
              <tr>
                <Th>Nome</Th>
                <Th>Nome curto</Th>
                <Th>Papel</Th>
                <Th>Situação</Th>
              </tr>
            </THead>
            <TBody>
              {members.data.map((member) => (
                <Tr key={member.id} onClick={() => setEditingMember(member)}>
                  <Td>
                    <span className="flex items-center gap-2">
                      <Avatar name={member.name} decorative />
                      <span className="truncate">{member.name}</span>
                    </span>
                  </Td>
                  <Td className="text-text-subtle">{member.short_name}</Td>
                  <Td className="text-text-subtle">{member.role || '—'}</Td>
                  <Td>
                    {member.is_active ? (
                      <Lozenge tone="success">Ativa</Lozenge>
                    ) : (
                      <Lozenge tone="muted">Inativa</Lozenge>
                    )}
                  </Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        )}
      </Block>

      <Block
        title="Squads"
        count={squads.data?.length}
        singular="squad"
        plural="squads"
        action={<Button onClick={() => setEditingSquad(null)}>Nova squad</Button>}
      >
        {!mounted || squads.isPending ? (
          <Skeleton lines={3} />
        ) : squads.isError ? (
          <ErrorState
            what="as squads"
            error={squads.error}
            onRetry={() => void squads.refetch()}
          />
        ) : squads.data.length === 0 ? (
          <EmptyState
            message="Nenhuma squad cadastrada. Crie uma squad para agrupar quem trabalha junto numa frente."
            action={<Button onClick={() => setEditingSquad(null)}>Nova squad</Button>}
          />
        ) : (
          <Table>
            <THead>
              <tr>
                <Th>Nome</Th>
                <Th>Representante</Th>
                <Th>Situação</Th>
              </tr>
            </THead>
            <TBody>
              {squads.data.map((squad) => (
                <Tr key={squad.id} onClick={() => setEditingSquad(squad)}>
                  <Td>{squad.name}</Td>
                  <Td className="text-text-subtle">
                    {representativeName(squad, members.data ?? [])}
                  </Td>
                  <Td>
                    {squad.is_active ? (
                      <Lozenge tone="success">Ativa</Lozenge>
                    ) : (
                      <Lozenge tone="muted">Inativa</Lozenge>
                    )}
                  </Td>
                </Tr>
              ))}
            </TBody>
          </Table>
        )}
      </Block>

      <Block
        title="Composição por sprint"
        action={
          selectedSquad && sprintNumbers.length > 0 ? (
            <div className="flex flex-wrap items-end gap-3">
              <Select
                label="Squad"
                value={selectedSquad.id}
                onChange={(event) => patch({ squad: event.target.value })}
                options={(squads.data ?? []).map((squad) => ({
                  value: squad.id,
                  label: squad.is_active ? squad.name : `${squad.name} (inativa)`,
                }))}
              />
              <Select
                label="Da sprint"
                value={String(sprintNumbers[0])}
                onChange={(event) =>
                  patch({
                    from: event.target.value,
                    to: String(
                      Number(event.target.value) + sprintNumbers.length - 1,
                    ),
                  })
                }
                options={allSprints.map((sprint) => ({
                  value: String(sprint.number),
                  label: `Sprint ${sprint.number}`,
                }))}
              />
              <Select
                label="Até a sprint"
                value={String(sprintNumbers[sprintNumbers.length - 1])}
                onChange={(event) =>
                  patch({ from: String(sprintNumbers[0]), to: event.target.value })
                }
                options={allSprints.map((sprint) => ({
                  value: String(sprint.number),
                  label: `Sprint ${sprint.number}`,
                }))}
              />
            </div>
          ) : null
        }
      >
        {!mounted || squads.isPending || sprints.isPending || members.isPending ? (
          <Skeleton lines={4} />
        ) : allSprints.length === 0 ? (
          <EmptyState
            message="Nenhuma sprint cadastrada. A composição é por sprint, então ela precisa de sprints para existir."
            action={
              <Button variant="primary" onClick={() => window.location.assign('/sprints')}>
                Ir para Sprints
              </Button>
            }
          />
        ) : !selectedSquad ? (
          <EmptyState message="Nenhuma squad para compor. Crie uma squad no bloco acima." />
        ) : (
          <SquadComposition
            squad={selectedSquad}
            members={activeMembers}
            sprintNumbers={sprintNumbers}
            currentSprintNumber={currentSprintNumber}
          />
        )}
      </Block>

      {editingMember !== undefined && (
        <MemberDrawer member={editingMember} onClose={() => setEditingMember(undefined)} />
      )}
      {editingSquad !== undefined && (
        <SquadDrawer
          squad={editingSquad}
          members={activeMembers}
          onClose={() => setEditingSquad(undefined)}
        />
      )}
    </div>
  );
}

function representativeName(squad: SquadOut, members: readonly MemberOut[]): string {
  if (!squad.representative_member_id) return '—';
  return (
    members.find((member) => member.id === squad.representative_member_id)?.name ??
    'pessoa não encontrada'
  );
}

interface BlockProps {
  readonly title: string;
  readonly count?: number;
  readonly singular?: string;
  readonly plural?: string;
  readonly action?: ReactNode;
  readonly children: ReactNode;
}

/** Um dos três blocos da página, com título, contador e a ação do bloco. */
function Block({ title, count, singular, plural, action, children }: BlockProps) {
  return (
    <section className="flex flex-col gap-2">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-16 font-semibold">{title}</h2>
          {count !== undefined && singular && plural && (
            <p className="mt-1 mb-0 text-12 text-text-subtle">
              {pluralize(count, singular, plural)}
            </p>
          )}
        </div>
        {action}
      </div>
      <Card>{children}</Card>
    </section>
  );
}

export default withQuery(function TeamIsland() {
  return (
    <ToastProvider>
      <TeamScreen />
    </ToastProvider>
  );
});
