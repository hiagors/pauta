import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api, type SprintOut, type SprintProposalOut } from '../../lib/api';
import { formatDate, pluralize } from '../../lib/format';
import { withQuery } from '../../lib/query';
import { isValidSprintRange, lengthInDays, suggestedEndDate } from '../../lib/sprints';
import { Button } from '../ui/Button';
import { Field } from '../ui/Field';
import { Lozenge } from '../ui/Lozenge';
import { Modal } from '../ui/Modal';
import { Card, EmptyState, ErrorState, Skeleton, describeError } from '../ui/States';
import { TBody, THead, Table, Td, Th, Tr } from '../ui/Table';
import { ToastProvider, useToast } from '../ui/Toast';

/**
 * A tela `/sprints` (§10.3).
 *
 * Lista com as datas, a marcação da sprint atual e o botão "Criar próxima
 * sprint", que mostra a proposta (RN10) antes de confirmar. **Sem ação de
 * excluir**: sprint nunca é excluída (D13), e é por isso que a invariante de
 * numeração sem buraco não pode ser violada.
 */
function SprintsScreen() {
  const [creating, setCreating] = useState(false);
  const sprints = useQuery({
    queryKey: ['sprints', {}],
    queryFn: ({ signal }) => api.listSprints(undefined, signal),
  });

  const isEmpty = sprints.data?.length === 0;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <p className="m-0 text-14 text-text-subtle">
          {sprints.data
            ? pluralize(
                sprints.data.length,
                'sprint cadastrada',
                'sprints cadastradas',
                'Nenhuma sprint cadastrada',
              )
            : ' '}
        </p>
        <Button
          variant="primary"
          disabled={!sprints.data}
          onClick={() => setCreating(true)}
        >
          {isEmpty ? 'Criar a primeira sprint' : 'Criar próxima sprint'}
        </Button>
      </div>

      <Card>
        {sprints.isPending ? (
          <Skeleton lines={5} />
        ) : sprints.isError ? (
          <ErrorState
            what="as sprints"
            error={sprints.error}
            onRetry={() => void sprints.refetch()}
          />
        ) : sprints.data.length === 0 ? (
          <EmptyState
            message="Nenhuma sprint cadastrada. Crie a primeira sprint para abrir a grade."
            action={
              <Button variant="primary" onClick={() => setCreating(true)}>
                Criar a primeira sprint
              </Button>
            }
          />
        ) : (
          <Table>
            <THead>
              <tr>
                <Th className="w-24">Sprint</Th>
                <Th>Início</Th>
                <Th>Fim</Th>
                <Th className="text-right">Dias</Th>
                <Th>Situação</Th>
              </tr>
            </THead>
            <TBody>
              {[...sprints.data]
                .sort((left, right) => left.number - right.number)
                .map((sprint) => (
                  <SprintRow key={sprint.id} sprint={sprint} />
                ))}
            </TBody>
          </Table>
        )}
      </Card>

      {creating && sprints.data && (
        <CreateSprintDialog
          hasSprints={sprints.data.length > 0}
          onClose={() => setCreating(false)}
        />
      )}
    </div>
  );
}

function SprintRow({ sprint }: { readonly sprint: SprintOut }) {
  const days = lengthInDays(sprint.start_date, sprint.end_date);
  return (
    <Tr>
      <Td className="font-semibold tabular-nums">{sprint.number}</Td>
      <Td className="tabular-nums">{formatDate(sprint.start_date)}</Td>
      <Td className="tabular-nums">{formatDate(sprint.end_date)}</Td>
      <Td className="text-right tabular-nums text-text-subtle">{days ?? '—'}</Td>
      <Td>
        {sprint.is_current ? (
          <Lozenge tone="primary">Sprint atual</Lozenge>
        ) : (
          <span className="text-text-subtle">—</span>
        )}
      </Td>
    </Tr>
  );
}

/**
 * A proposta da RN10, editável antes de confirmar.
 *
 * Com sprints cadastradas, o número vem do backend e não é editável: a
 * numeração é sequencial sem buraco (§6.6), e deixar o campo aberto seria
 * oferecer um 422. As datas são editáveis, como a RN10 manda.
 *
 * Sem nenhuma sprint não há o que propor — `GET /sprints/next/preview` é 404
 * nesse caso, de propósito. O formulário abre em branco e o número entra à
 * mão: a primeira sprint de um time real raramente é a 1.
 */
function CreateSprintDialog({
  hasSprints,
  onClose,
}: {
  readonly hasSprints: boolean;
  readonly onClose: () => void;
}) {
  const client = useQueryClient();
  const { notify } = useToast();
  const [number, setNumber] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [proposal, setProposal] = useState<SprintProposalOut | null>(null);

  const preview = useQuery({
    queryKey: ['sprints', 'next', 'preview'],
    queryFn: ({ signal }) => api.previewNextSprint(signal),
    enabled: hasSprints,
    // A proposta depende da última sprint cadastrada: guardá-la entre aberturas
    // do diálogo mostraria a de ontem depois de criar a de hoje.
    staleTime: 0,
  });

  useEffect(() => {
    if (!preview.data) return;
    setProposal(preview.data);
    setNumber(String(preview.data.number));
    setStart(preview.data.start_date);
    setEnd(preview.data.end_date);
  }, [preview.data]);

  const mutation = useMutation({
    mutationFn: () => {
      const untouched =
        proposal !== null &&
        proposal.start_date === start &&
        proposal.end_date === end;
      // Sem edição, quem cria é o endpoint da proposta: o cálculo da RN10 fica
      // num lugar só, e não recalculado aqui a partir do que a tela mostrou.
      if (untouched) return api.createNextSprint();
      return api.createSprint({
        number: Number(number),
        start_date: start,
        end_date: end,
      });
    },
    onSuccess: (created) => {
      void client.invalidateQueries({ queryKey: ['sprints'] });
      void client.invalidateQueries({ queryKey: ['planning'] });
      void client.invalidateQueries({ queryKey: ['alerts'] });
      notify(
        `Sprint ${created.number} criada: ${formatDate(created.start_date)} a ${formatDate(created.end_date)}.`,
        'success',
      );
      onClose();
    },
  });

  const numberIsValid = Number.isInteger(Number(number)) && Number(number) >= 1;
  const rangeIsValid = isValidSprintRange(start, end);
  const days = lengthInDays(start, end);

  return (
    <Modal
      open
      title={hasSprints ? 'Criar próxima sprint' : 'Criar a primeira sprint'}
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>Cancelar</Button>
          <Button
            variant="primary"
            disabled={!numberIsValid || !rangeIsValid || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? 'Criando…' : 'Criar sprint'}
          </Button>
        </>
      }
    >
      {hasSprints && preview.isPending ? (
        <Skeleton lines={2} />
      ) : hasSprints && preview.isError ? (
        <ErrorState
          what="a proposta da próxima sprint"
          error={preview.error}
          onRetry={() => void preview.refetch()}
        />
      ) : (
        <div className="flex flex-col gap-3">
          <Field
            label="Número"
            type="number"
            min={1}
            value={number}
            disabled={hasSprints}
            onChange={(event) => setNumber(event.target.value)}
            hint={
              hasSprints
                ? 'Sequencial, sem buraco: quem numera é a sequência cadastrada.'
                : 'A numeração começa aqui e segue daqui em diante.'
            }
            error={numberIsValid ? undefined : 'Informe um número de sprint válido.'}
          />
          <div className="grid grid-cols-2 gap-3">
            <Field
              label="Início"
              type="date"
              value={start}
              onChange={(event) => {
                setStart(event.target.value);
                // Sugestão de formulário, não regra: o padrão do §6.6 é duas
                // semanas de calendário, e quem quiser outra coisa edita o fim.
                if (event.target.value && !end) setEnd(suggestedEndDate(event.target.value));
              }}
            />
            <Field
              label="Fim"
              type="date"
              value={end}
              onChange={(event) => setEnd(event.target.value)}
              hint={days !== null && days > 1 ? `${days} dias de calendário.` : undefined}
              error={rangeIsValid ? undefined : 'O fim precisa ser depois do início.'}
            />
          </div>
          {proposal && (proposal.start_date !== start || proposal.end_date !== end) && (
            <p className="m-0 text-11 text-text-subtle">
              Proposta original: {formatDate(proposal.start_date)} a{' '}
              {formatDate(proposal.end_date)}.
            </p>
          )}
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

export default withQuery(function SprintsIsland() {
  return (
    <ToastProvider>
      <SprintsScreen />
    </ToastProvider>
  );
});
