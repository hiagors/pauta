import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api, type InitiativeOut, type Schemas } from '../../lib/api';
import { INITIATIVE_STATUS_LABEL, PRIORITY_LABEL } from '../../lib/format';
import { manualTransitions, parseEstimate } from '../../lib/initiatives';
import { Button } from '../ui/Button';
import { Drawer } from '../ui/Drawer';
import { Field, TextArea } from '../ui/Field';
import { StatusLozenge } from '../ui/Lozenge';
import { Select } from '../ui/Select';
import { ErrorState, Skeleton, describeError } from '../ui/States';
import { useToast } from '../ui/Toast';

/**
 * O drawer de iniciativa (§10.3): a unidade de trabalho, onde moram
 * prioridade, estimativa e status.
 *
 * Status **não** é um campo do formulário. `BACKLOG ⇄ PLANNED` é automático,
 * efeito de ganhar ou perder alocação (RN2), e as transições manuais têm
 * tabela própria (§6.3) — por isso viram botões, e só aparecem os que a tabela
 * permite. Um `<select>` com os seis valores ofereceria caminhos que só sabem
 * responder 422.
 */
export interface InitiativeDrawerProps {
  /** `null` cria dentro de `projectId`; um id edita. */
  readonly initiativeId: string | null;
  readonly projectId: string;
  readonly projectName: string;
  readonly onClose: () => void;
}

interface InitiativeForm {
  name: string;
  layer: string;
  description: string;
  priority: Schemas['Priority'];
  estimate: string;
}

const BLANK: InitiativeForm = {
  name: '',
  layer: '',
  description: '',
  priority: 'MEDIUM',
  estimate: '',
};

function toForm(initiative: InitiativeOut): InitiativeForm {
  return {
    name: initiative.name,
    layer: initiative.layer ?? '',
    description: initiative.description,
    priority: initiative.priority,
    estimate: initiative.estimated_sprints === null ? '' : String(initiative.estimated_sprints),
  };
}

/** Campo em branco vira `null`, não `""`: `layer` é texto livre **opcional**. */
function optionalText(value: string): string | null {
  const trimmed = value.trim();
  return trimmed === '' ? null : trimmed;
}

/** Como no projeto, só o que mudou entra no `PATCH` (§8). */
function initiativePatch(
  original: InitiativeOut,
  form: InitiativeForm,
): Schemas['InitiativePatchIn'] {
  const patch: Schemas['InitiativePatchIn'] = {};
  const layer = optionalText(form.layer);
  const estimate = parseEstimate(form.estimate);
  if (form.name.trim() !== original.name) patch.name = form.name.trim();
  if (layer !== original.layer) patch.layer = layer;
  if (form.description !== original.description) patch.description = form.description;
  if (form.priority !== original.priority) patch.priority = form.priority;
  if (estimate !== undefined && estimate !== original.estimated_sprints) {
    patch.estimated_sprints = estimate;
  }
  return patch;
}

const PRIORITY_OPTIONS = (['HIGH', 'MEDIUM', 'LOW'] as const).map((priority) => ({
  value: priority,
  label: PRIORITY_LABEL[priority],
}));

export function InitiativeDrawer({
  initiativeId,
  projectId,
  projectName,
  onClose,
}: InitiativeDrawerProps) {
  const client = useQueryClient();
  const { notify } = useToast();
  const [form, setForm] = useState<InitiativeForm>(BLANK);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const initiative = useQuery({
    queryKey: ['initiatives', 'detail', initiativeId],
    queryFn: ({ signal }) => api.getInitiative(initiativeId ?? '', signal),
    enabled: initiativeId !== null,
  });

  useEffect(() => {
    setConfirmingDelete(false);
    setForm(initiative.data ? toForm(initiative.data) : BLANK);
  }, [initiative.data, initiativeId]);

  function invalidate() {
    void client.invalidateQueries({ queryKey: ['initiatives'] });
    void client.invalidateQueries({ queryKey: ['projects'] });
    void client.invalidateQueries({ queryKey: ['planning'] });
    void client.invalidateQueries({ queryKey: ['alerts'] });
  }

  const estimate = parseEstimate(form.estimate);

  const save = useMutation({
    mutationFn: () => {
      if (initiative.data) {
        return api.updateInitiative(initiative.data.id, initiativePatch(initiative.data, form));
      }
      return api.createInitiative({
        project_id: projectId,
        name: form.name.trim(),
        layer: optionalText(form.layer),
        description: form.description,
        priority: form.priority,
        estimated_sprints: estimate ?? null,
      });
    },
    onSuccess: () => {
      invalidate();
      notify(
        initiative.data
          ? `Iniciativa ${form.name.trim()} salva.`
          : `Iniciativa ${form.name.trim()} criada em ${projectName}.`,
        'success',
      );
      onClose();
    },
  });

  const changeStatus = useMutation({
    mutationFn: (status: Schemas['InitiativeStatus']) =>
      api.changeInitiativeStatus(initiativeId ?? '', { status }),
    onSuccess: (updated) => {
      invalidate();
      void initiative.refetch();
      notify(
        `${updated.name}: ${INITIATIVE_STATUS_LABEL[updated.status].toLowerCase()}.`,
        'success',
      );
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteInitiative(initiativeId ?? ''),
    onSuccess: () => {
      invalidate();
      notify(`Iniciativa ${form.name.trim()} excluída.`, 'success');
      onClose();
    },
  });

  const isEditing = initiativeId !== null;
  const loading = isEditing && initiative.isPending;
  const nameIsValid = form.name.trim() !== '';
  const estimateIsValid = estimate !== undefined;

  return (
    <Drawer
      open
      onClose={onClose}
      title={isEditing ? 'Editar iniciativa' : 'Nova iniciativa'}
      subtitle={projectName}
      footer={
        <>
          <Button onClick={onClose}>Cancelar</Button>
          <Button
            variant="primary"
            disabled={!nameIsValid || !estimateIsValid || loading || save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending ? 'Salvando…' : 'Salvar'}
          </Button>
        </>
      }
    >
      {loading ? (
        <Skeleton lines={4} />
      ) : initiative.isError ? (
        <ErrorState
          what="esta iniciativa"
          error={initiative.error}
          onRetry={() => void initiative.refetch()}
        />
      ) : (
        <div className="flex flex-col gap-4">
          <Field
            label="Nome"
            value={form.name}
            autoFocus
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            hint="Único dentro do projeto."
            error={nameIsValid ? undefined : 'O nome é obrigatório.'}
          />
          <Field
            label="Camada"
            value={form.layer}
            onChange={(event) => setForm({ ...form, layer: event.target.value })}
            hint="Texto livre, opcional. Ex.: Dados, Backend, Serviço de Envio."
          />
          <TextArea
            label="Descrição"
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
          />
          <div className="grid grid-cols-2 gap-3">
            <Select
              label="Prioridade"
              value={form.priority}
              onChange={(event) =>
                setForm({ ...form, priority: event.target.value as Schemas['Priority'] })
              }
              options={PRIORITY_OPTIONS}
            />
            <Field
              label="Estimativa (sprints)"
              type="number"
              min={1}
              value={form.estimate}
              onChange={(event) => setForm({ ...form, estimate: event.target.value })}
              hint={estimateIsValid ? 'Em branco: sem estimativa.' : undefined}
              error={estimateIsValid ? undefined : 'Informe um número inteiro maior que zero, ou deixe em branco.'}
            />
          </div>

          {save.isError && (
            <p className="m-0 rounded-sm border border-danger bg-danger-soft p-2 text-12 text-danger">
              {describeError(save.error)}
            </p>
          )}

          {initiative.data && (
            <section className="border-t border-border pt-4">
              <h3 className="text-12 font-semibold text-text-subtle">Status</h3>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <StatusLozenge status={initiative.data.status} />
                {manualTransitions(initiative.data.status).map((status) => (
                  <Button
                    key={status}
                    disabled={changeStatus.isPending}
                    onClick={() => changeStatus.mutate(status)}
                  >
                    {INITIATIVE_STATUS_LABEL[status]}
                  </Button>
                ))}
              </div>
              <p className="mt-2 mb-0 text-11 text-text-subtle">
                {manualTransitions(initiative.data.status).length === 0
                  ? 'Status terminal: não há transição de saída.'
                  : 'Planejada e backlog são automáticos, pela alocação. Nada volta para o backlog depois de ter começado — o caminho de parada é despriorizar.'}
              </p>
              {changeStatus.isError && (
                <p className="mt-2 mb-0 text-12 text-danger">
                  {describeError(changeStatus.error)}
                </p>
              )}
            </section>
          )}

          {isEditing && (
            <section className="border-t border-border pt-4">
              {confirmingDelete ? (
                <div className="flex flex-col gap-2">
                  <p className="m-0 text-12">
                    A exclusão é recusada se houver alocação ou se esta for a última
                    iniciativa do projeto. Nesses casos o caminho é cancelar.
                  </p>
                  {remove.isError && (
                    <p className="m-0 text-12 text-danger">{describeError(remove.error)}</p>
                  )}
                  <div className="flex gap-2">
                    <Button onClick={() => setConfirmingDelete(false)}>Cancelar</Button>
                    <Button
                      variant="danger"
                      disabled={remove.isPending}
                      onClick={() => remove.mutate()}
                    >
                      {remove.isPending ? 'Excluindo…' : 'Confirmar exclusão'}
                    </Button>
                  </div>
                </div>
              ) : (
                <Button variant="ghost" onClick={() => setConfirmingDelete(true)}>
                  Excluir iniciativa
                </Button>
              )}
            </section>
          )}
        </div>
      )}
    </Drawer>
  );
}
