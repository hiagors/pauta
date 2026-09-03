import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import {
  api,
  type AllocationResultOut,
  type AlertOut,
  type MemberOut,
  type SquadOut,
} from '../../lib/api';
import { ALERT_TYPE_LABEL, INITIATIVE_STATUS_LABEL, formatSprintRange, pluralize } from '../../lib/format';
import {
  rangeLeftovers,
  extendedRange,
  movedRange,
  type GridBar,
  type SprintRange,
} from '../../lib/planning';
import { Button } from '../ui/Button';
import { Field } from '../ui/Field';
import { Lozenge } from '../ui/Lozenge';
import { Modal } from '../ui/Modal';
import { Select, type SelectOption } from '../ui/Select';
import { EmptyState, describeError } from '../ui/States';
import { useToast } from '../ui/Toast';

/**
 * O diálogo de alocação e as ações da barra (§10.3).
 *
 * Um arquivo só porque as três operações terminam na mesma chamada: alocar um
 * intervalo. Mover e estender são a mesma coisa com o intervalo calculado a
 * partir da barra, mais a limpeza da sobra — a API não tem "mover" (§8), e a
 * ordem "cria primeiro, apaga depois" é o que impede a barra de sumir se a
 * segunda chamada falhar.
 */

/** Quem recebe a alocação, no formato que os dois campos do §8 esperam. */
export interface AssigneeChoice {
  readonly kind: 'squad' | 'member';
  readonly id: string;
}

/** A iniciativa que a operação toca, com o contexto que o título mostra. */
export interface AllocationSubject {
  readonly initiativeId: string;
  readonly initiativeName: string;
  readonly projectName: string;
}

interface ApplyInput {
  readonly initiativeId: string;
  readonly assignee: AssigneeChoice;
  readonly range: SprintRange;
  /** Intervalo antigo, quando a operação move ou redimensiona uma barra. */
  readonly origin?: SprintRange;
}

/**
 * Aplica a alocação e, se veio de uma barra, apaga o que sobrou dela.
 *
 * `POST` primeiro (RN1 é idempotente, então a parte que já existia não vira
 * erro), `DELETE` depois. Se a limpeza falhar, o pior caso é uma barra maior
 * do que se pediu — visível e corrigível. Na ordem inversa, o pior caso seria
 * a iniciativa ficar sem alocação nenhuma.
 */
async function applyAllocation(input: ApplyInput): Promise<AllocationResultOut> {
  const result = await api.allocateRange({
    initiative_id: input.initiativeId,
    squad_id: input.assignee.kind === 'squad' ? input.assignee.id : null,
    member_id: input.assignee.kind === 'member' ? input.assignee.id : null,
    from_sprint_number: input.range.from,
    to_sprint_number: input.range.to,
  });
  if (input.origin) {
    for (const leftover of rangeLeftovers(input.origin, input.range)) {
      await api.deallocateRange({
        initiative_id: input.initiativeId,
        from_sprint_number: leftover.from,
        to_sprint_number: leftover.to,
      });
    }
  }
  return result;
}

/** Tudo que a grade, a lista, o backlog e o sino leem sai daqui. */
function useInvalidatePlanning() {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: ['planning'] });
    void client.invalidateQueries({ queryKey: ['alerts'] });
  };
}

/* -------------------------------------------------------------------------
 * Peças compartilhadas
 * ---------------------------------------------------------------------- */

/** Alertas das sprints tocadas, como vieram na resposta (§8). Sem segunda chamada. */
function AlertList({ alerts }: { readonly alerts: readonly AlertOut[] }) {
  if (alerts.length === 0) return null;
  return (
    <ul className="m-0 mt-3 flex list-none flex-col gap-2 p-0">
      {alerts.map((alert) => (
        <li
          key={alert.fingerprint}
          className="rounded-sm border border-border bg-neutral-soft p-2"
        >
          <div className="flex items-center gap-2">
            <Lozenge tone={alert.severity === 'WARNING' ? 'danger' : 'neutral'}>
              {ALERT_TYPE_LABEL[alert.type]}
            </Lozenge>
            <span className="text-11 text-text-subtle">Sprint {alert.sprint_number}</span>
            {alert.is_muted && (
              <span className="text-11 text-text-subtle">· já silenciado</span>
            )}
          </div>
          <p className="m-0 mt-1 text-12">{alert.message}</p>
        </li>
      ))}
    </ul>
  );
}

/** O que a operação fez, em números, mais o aviso da RN5. */
function ResultPanel({ result }: { readonly result: AllocationResultOut }) {
  return (
    <div>
      <p className="m-0 text-14">
        {pluralize(result.created.length, 'sprint alocada', 'sprints alocadas', 'Nenhuma sprint nova alocada')}
        {result.already_existed.length > 0 &&
          `; ${pluralize(result.already_existed.length, 'já existia', 'já existiam')}`}
        .
      </p>
      <p className="m-0 mt-1 flex items-center gap-2 text-12 text-text-subtle">
        Status da iniciativa:
        <Lozenge tone="primary">{INITIATIVE_STATUS_LABEL[result.initiative_status]}</Lozenge>
      </p>
      {result.missing_sprint_numbers.length > 0 && (
        // RN5: sprint que não existe não derruba a operação. O que falta vira
        // aviso com o caminho para resolver, que é a tela de sprints.
        <p className="mt-3 mb-0 rounded-sm border border-warning bg-warning-soft p-2 text-12 text-warning">
          {pluralize(result.missing_sprint_numbers.length, 'Esta sprint não está cadastrada', 'Estas sprints não estão cadastradas')}
          : {result.missing_sprint_numbers.join(', ')}. Cadastre-as em{' '}
          <a href="/sprints" className="font-semibold underline">
            Sprints
          </a>
          .
        </p>
      )}
      <AlertList alerts={result.alerts} />
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Alocar
 * ---------------------------------------------------------------------- */

export interface AllocationDialogProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly subject: AllocationSubject;
  /** Sprint inicial e final já preenchidas pelo contexto (§10.3). */
  readonly defaultRange: SprintRange;
  readonly defaultAssignee?: AssigneeChoice | null;
}

/** O valor do `<select>` carrega o tipo junto: um controle, não dois. */
function assigneeValue(assignee: AssigneeChoice | null | undefined): string {
  return assignee ? `${assignee.kind}:${assignee.id}` : '';
}

function parseAssignee(value: string): AssigneeChoice | null {
  const [kind, id] = value.split(':');
  if ((kind !== 'squad' && kind !== 'member') || !id) return null;
  return { kind, id };
}

function assigneeOptions(
  squads: readonly SquadOut[],
  members: readonly MemberOut[],
): SelectOption[] {
  return [
    ...squads.map((squad) => ({
      value: `squad:${squad.id}`,
      label: squad.name,
      group: 'Squads',
    })),
    ...members.map((member) => ({
      value: `member:${member.id}`,
      label: member.short_name,
      group: 'Pessoas',
    })),
  ];
}

export function AllocationDialog({
  open,
  onClose,
  subject,
  defaultRange,
  defaultAssignee,
}: AllocationDialogProps) {
  const { notify } = useToast();
  const invalidate = useInvalidatePlanning();
  const [assignee, setAssignee] = useState(assigneeValue(defaultAssignee));
  const [from, setFrom] = useState(String(defaultRange.from));
  const [to, setTo] = useState(String(defaultRange.to));
  const [result, setResult] = useState<AllocationResultOut | null>(null);

  // Reabrir o diálogo em outra célula tem que reabrir com aquela célula, não
  // com o que ficou da vez anterior.
  useEffect(() => {
    if (!open) return;
    setAssignee(assigneeValue(defaultAssignee));
    setFrom(String(defaultRange.from));
    setTo(String(defaultRange.to));
    setResult(null);
  }, [open, defaultAssignee, defaultRange.from, defaultRange.to]);

  // Só os ativos: alocar em squad inativa é criar trabalho para ninguém. As
  // barras já existentes continuam mostrando o nome de quem foi inativado,
  // porque o nome vem do backend por id (§8).
  const squads = useQuery({
    queryKey: ['squads', { active: true }],
    queryFn: ({ signal }) => api.listSquads({ active: true }, signal),
    enabled: open,
  });
  const members = useQuery({
    queryKey: ['members', { active: true }],
    queryFn: ({ signal }) => api.listMembers({ active: true }, signal),
    enabled: open,
  });

  const mutation = useMutation({
    mutationFn: applyAllocation,
    onSuccess: (applied) => {
      invalidate();
      const quiet =
        applied.alerts.length === 0 && applied.missing_sprint_numbers.length === 0;
      if (quiet) {
        notify(
          `${subject.initiativeName}: ${formatSprintRange(Number(from), Number(to))} alocada.`,
          'success',
        );
        onClose();
        return;
      }
      setResult(applied);
    },
  });

  // Alocar é escolher um responsável: sem nenhuma squad nem pessoa ativa, o
  // diálogo não tem o que oferecer. Vale exatamente no caminho "planejar do
  // zero", em que o time é cadastrado depois do primeiro projeto.
  const assigneesLoaded = squads.data !== undefined && members.data !== undefined;
  const noAssignees =
    assigneesLoaded && squads.data.length === 0 && members.data.length === 0;

  const choice = parseAssignee(assignee);
  const range = { from: Number(from), to: Number(to) };
  const rangeIsValid =
    Number.isInteger(range.from) &&
    Number.isInteger(range.to) &&
    range.from >= 1 &&
    range.to >= range.from;

  return (
    <Modal
      open={open}
      title="Alocar iniciativa"
      onClose={onClose}
      footer={
        result || noAssignees ? (
          <Button variant="primary" onClick={onClose}>
            Fechar
          </Button>
        ) : (
          <>
            <Button onClick={onClose}>Cancelar</Button>
            <Button
              variant="primary"
              disabled={!choice || !rangeIsValid || mutation.isPending}
              onClick={() => {
                if (!choice || !rangeIsValid) return;
                mutation.mutate({
                  initiativeId: subject.initiativeId,
                  assignee: choice,
                  range,
                });
              }}
            >
              {mutation.isPending ? 'Alocando…' : 'Alocar'}
            </Button>
          </>
        )
      }
    >
      <p className="m-0 mb-4 text-12 text-text-subtle">
        {subject.projectName} · <span className="text-text">{subject.initiativeName}</span>
      </p>

      {result ? (
        <ResultPanel result={result} />
      ) : noAssignees ? (
        <EmptyState
          message="Nenhuma squad nem pessoa ativa para receber a alocação. Cadastre o time antes de alocar."
          action={
            <Button variant="primary" onClick={() => window.location.assign('/team')}>
              Ir para Time
            </Button>
          }
        />
      ) : (
        <div className="flex flex-col gap-3">
          <Select
            label="Responsável"
            placeholder={squads.isPending || members.isPending ? 'Carregando…' : 'Escolha uma squad ou pessoa'}
            value={assignee}
            onChange={(event) => setAssignee(event.target.value)}
            options={assigneeOptions(squads.data ?? [], members.data ?? [])}
          />
          <div className="grid grid-cols-2 gap-3">
            <Field
              label="Sprint inicial"
              type="number"
              min={1}
              value={from}
              onChange={(event) => setFrom(event.target.value)}
            />
            <Field
              label="Sprint final"
              type="number"
              min={1}
              value={to}
              onChange={(event) => setTo(event.target.value)}
              error={rangeIsValid ? undefined : 'A sprint final não pode ser anterior à inicial.'}
            />
          </div>
          <p className="m-0 text-11 text-text-subtle">
            Uma alocação por sprint do intervalo. Sprint ainda não cadastrada não
            impede o resto — ela volta na lista do que falta criar.
          </p>
          {mutation.isError && (
            <p className="m-0 rounded-sm border border-danger bg-danger-soft p-2 text-12 text-danger">
              {describeError(mutation.error)}
            </p>
          )}
        </div>
      )}
    </Modal>
  );
}

/* -------------------------------------------------------------------------
 * Ações da barra: mover, estender, remover
 * ---------------------------------------------------------------------- */

export type BarAction = 'move' | 'extend' | 'remove';

export interface BarDialogProps {
  readonly action: BarAction | null;
  readonly onClose: () => void;
  readonly subject: AllocationSubject;
  readonly bar: GridBar;
}

const BAR_TITLE: Record<BarAction, string> = {
  move: 'Mover alocação',
  extend: 'Estender alocação',
  remove: 'Remover alocação',
};

/**
 * O diálogo das três ações do popover da barra.
 *
 * Mover pede a nova sprint inicial e preserva o comprimento; estender pede a
 * sprint final e preserva o começo. Os dois mostram o intervalo resultante
 * antes de confirmar, porque a conta é feita aqui e não na cabeça de quem usa.
 */
export function BarDialog({ action, onClose, subject, bar }: BarDialogProps) {
  const { notify } = useToast();
  const invalidate = useInvalidatePlanning();
  const [value, setValue] = useState('');
  const [result, setResult] = useState<AllocationResultOut | null>(null);

  useEffect(() => {
    if (!action) return;
    setValue(String(action === 'move' ? bar.from_sprint_number : bar.to_sprint_number));
    setResult(null);
  }, [action, bar.from_sprint_number, bar.to_sprint_number]);

  const origin: SprintRange = {
    from: bar.from_sprint_number,
    to: bar.to_sprint_number,
  };
  const target = Number(value);
  const next =
    action === 'move' ? movedRange(bar, target) : extendedRange(bar, target);
  const valid = Number.isInteger(target) && target >= 1 && next.to >= next.from;

  const mutation = useMutation({
    mutationFn: async () => {
      if (action === 'remove') {
        await api.deallocateRange({
          initiative_id: subject.initiativeId,
          from_sprint_number: origin.from,
          to_sprint_number: origin.to,
        });
        return null;
      }
      return applyAllocation({
        initiativeId: subject.initiativeId,
        assignee: { kind: bar.assignee.kind, id: bar.assignee.id },
        range: next,
        origin,
      });
    },
    onSuccess: (applied) => {
      invalidate();
      if (!applied) {
        notify(`${subject.initiativeName}: alocação removida.`, 'success');
        onClose();
        return;
      }
      const quiet =
        applied.alerts.length === 0 && applied.missing_sprint_numbers.length === 0;
      if (quiet) {
        notify(
          `${subject.initiativeName}: agora em ${formatSprintRange(next.from, next.to)}.`,
          'success',
        );
        onClose();
        return;
      }
      setResult(applied);
    },
  });

  if (!action) return null;

  const confirmLabel = action === 'remove' ? 'Remover' : 'Confirmar';

  return (
    <Modal
      open
      title={BAR_TITLE[action]}
      onClose={onClose}
      footer={
        result ? (
          <Button variant="primary" onClick={onClose}>
            Fechar
          </Button>
        ) : (
          <>
            <Button onClick={onClose}>Cancelar</Button>
            <Button
              variant={action === 'remove' ? 'danger' : 'primary'}
              disabled={(action !== 'remove' && !valid) || mutation.isPending}
              onClick={() => mutation.mutate()}
            >
              {mutation.isPending ? 'Aplicando…' : confirmLabel}
            </Button>
          </>
        )
      }
    >
      <p className="m-0 mb-4 text-12 text-text-subtle">
        {subject.projectName} · <span className="text-text">{subject.initiativeName}</span>
        {' · '}
        {bar.assignee.name} em {formatSprintRange(origin.from, origin.to)}
      </p>

      {result ? (
        <ResultPanel result={result} />
      ) : action === 'remove' ? (
        <p className="m-0 text-14">
          Isto apaga {pluralize(origin.to - origin.from + 1, 'alocação', 'alocações')} de{' '}
          {bar.assignee.name}. A iniciativa não é excluída; se ela ficar sem nenhuma
          alocação, volta para o backlog.
        </p>
      ) : (
        <div className="flex flex-col gap-3">
          <Field
            label={action === 'move' ? 'Nova sprint inicial' : 'Estender até a sprint'}
            type="number"
            min={1}
            autoFocus
            value={value}
            onChange={(event) => setValue(event.target.value)}
            hint={
              valid
                ? `A barra passa a cobrir ${formatSprintRange(next.from, next.to)}.`
                : undefined
            }
            error={valid ? undefined : 'Informe um número de sprint válido.'}
          />
          {mutation.isError && (
            <p className="m-0 rounded-sm border border-danger bg-danger-soft p-2 text-12 text-danger">
              {describeError(mutation.error)}
            </p>
          )}
        </div>
      )}
    </Modal>
  );
}
