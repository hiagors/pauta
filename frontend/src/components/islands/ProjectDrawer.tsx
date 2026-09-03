import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api, type ProjectOut, type Schemas } from '../../lib/api';
import { DEFAULT_PROJECT_COLOR, INITIATIVE_STATUS_LABEL, pluralize } from '../../lib/format';
import { isHexColor, sortInitiatives } from '../../lib/initiatives';
import { Button } from '../ui/Button';
import { Checkbox } from '../ui/Checkbox';
import { Drawer } from '../ui/Drawer';
import { Field, TextArea } from '../ui/Field';
import { StatusLozenge } from '../ui/Lozenge';
import { ErrorState, Skeleton, describeError } from '../ui/States';
import { useToast } from '../ui/Toast';

/**
 * O drawer de projeto (§10.3): criar e editar em painel lateral, não em página
 * nova.
 *
 * Criar um projeto cria junto a primeira iniciativa, com o mesmo nome (RN-I1).
 * Quem tem uma frente única nunca precisa pensar em iniciativa — e por isso o
 * formulário de criação não pergunta nada sobre ela.
 *
 * Na edição o drawer lista as iniciativas do projeto e oferece adicionar, que
 * é o que o §10.3 pede.
 */
export interface ProjectDrawerProps {
  /** `null` cria; um id edita. */
  readonly projectId: string | null;
  readonly onClose: () => void;
  /** Abre o drawer de iniciativa já apontado para este projeto. */
  readonly onAddInitiative: (project: ProjectOut) => void;
  readonly onEditInitiative: (project: ProjectOut, initiativeId: string) => void;
}

interface ProjectForm {
  name: string;
  description: string;
  color: string;
  useDefaultColor: boolean;
  isCapacityReserve: boolean;
  isActive: boolean;
}

const BLANK: ProjectForm = {
  name: '',
  description: '',
  color: DEFAULT_PROJECT_COLOR,
  useDefaultColor: true,
  isCapacityReserve: false,
  isActive: true,
};

function toForm(project: ProjectOut): ProjectForm {
  return {
    name: project.name,
    description: project.description,
    // Cor gravada fora do formato `#RRGGBB` (CLI, snapshot antigo) não pode
    // travar o `<input type="color">`, que só sabe falar esse formato.
    color: project.color && isHexColor(project.color) ? project.color : DEFAULT_PROJECT_COLOR,
    useDefaultColor: project.color === null,
    isCapacityReserve: project.is_capacity_reserve,
    isActive: project.is_active,
  };
}

/**
 * Só o que mudou entra no `PATCH`.
 *
 * Campo ausente e campo nulo são coisas diferentes no §8: `color: null` limpa
 * a cor, e a ausência de `color` não mexe no que está gravado. Mandar o
 * formulário inteiro apagaria essa distinção.
 */
function projectPatch(
  original: ProjectOut,
  form: ProjectForm,
): Schemas['ProjectPatchIn'] {
  const patch: Schemas['ProjectPatchIn'] = {};
  const color = form.useDefaultColor ? null : form.color;
  if (form.name !== original.name) patch.name = form.name.trim();
  if (form.description !== original.description) patch.description = form.description;
  if (color !== original.color) patch.color = color;
  if (form.isCapacityReserve !== original.is_capacity_reserve) {
    patch.is_capacity_reserve = form.isCapacityReserve;
  }
  if (form.isActive !== original.is_active) patch.is_active = form.isActive;
  return patch;
}

export function ProjectDrawer({
  projectId,
  onClose,
  onAddInitiative,
  onEditInitiative,
}: ProjectDrawerProps) {
  const client = useQueryClient();
  const { notify } = useToast();
  const [form, setForm] = useState<ProjectForm>(BLANK);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const detail = useQuery({
    queryKey: ['projects', 'detail', projectId],
    queryFn: ({ signal }) => api.getProject(projectId ?? '', signal),
    enabled: projectId !== null,
  });

  useEffect(() => {
    setConfirmingDelete(false);
    setForm(detail.data ? toForm(detail.data.project) : BLANK);
  }, [detail.data, projectId]);

  function invalidate() {
    void client.invalidateQueries({ queryKey: ['projects'] });
    void client.invalidateQueries({ queryKey: ['initiatives'] });
    void client.invalidateQueries({ queryKey: ['planning'] });
    void client.invalidateQueries({ queryKey: ['alerts'] });
  }

  const save = useMutation({
    // O retorno é descartado — a tela relê pelo cache invalidado —, e os dois
    // caminhos devolvem coisas diferentes: `POST` traz o detalhe com a
    // iniciativa criada junto (RN-I1), `PATCH` traz só o projeto.
    mutationFn: async (): Promise<void> => {
      if (detail.data) {
        await api.updateProject(
          detail.data.project.id,
          projectPatch(detail.data.project, form),
        );
        return;
      }
      await api.createProject({
        name: form.name.trim(),
        description: form.description,
        color: form.useDefaultColor ? null : form.color,
        is_capacity_reserve: form.isCapacityReserve,
      });
    },
    onSuccess: () => {
      invalidate();
      notify(
        detail.data
          ? `Projeto ${form.name.trim()} salvo.`
          : `Projeto ${form.name.trim()} criado com a primeira iniciativa.`,
        'success',
      );
      onClose();
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteProject(projectId ?? ''),
    onSuccess: () => {
      invalidate();
      notify(`Projeto ${form.name.trim()} excluído.`, 'success');
      onClose();
    },
  });

  const isEditing = projectId !== null;
  const loading = isEditing && detail.isPending;
  const nameIsValid = form.name.trim() !== '';

  return (
    <Drawer
      open
      onClose={onClose}
      title={isEditing ? 'Editar projeto' : 'Novo projeto'}
      subtitle={
        isEditing
          ? 'Projeto agrupa; a unidade de trabalho é a iniciativa.'
          : 'A primeira iniciativa é criada junto, com o mesmo nome (RN-I1).'
      }
      footer={
        <>
          <Button onClick={onClose}>Cancelar</Button>
          <Button
            variant="primary"
            disabled={!nameIsValid || loading || save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending ? 'Salvando…' : 'Salvar'}
          </Button>
        </>
      }
    >
      {loading ? (
        <Skeleton lines={4} />
      ) : detail.isError ? (
        <ErrorState
          what="este projeto"
          error={detail.error}
          onRetry={() => void detail.refetch()}
        />
      ) : (
        <div className="flex flex-col gap-4">
          <Field
            label="Nome"
            value={form.name}
            autoFocus
            onChange={(event) => setForm({ ...form, name: event.target.value })}
            error={nameIsValid ? undefined : 'O nome é obrigatório.'}
          />
          <TextArea
            label="Descrição"
            value={form.description}
            onChange={(event) => setForm({ ...form, description: event.target.value })}
          />

          <div className="flex flex-col gap-2">
            <span className="text-12 text-text-subtle">Cor</span>
            <div className="flex items-center gap-3">
              <input
                type="color"
                aria-label="Cor do projeto"
                value={form.color}
                disabled={form.useDefaultColor}
                onChange={(event) => setForm({ ...form, color: event.target.value })}
                className="h-8 w-12 rounded-sm border border-border-strong bg-surface disabled:opacity-50"
              />
              <Checkbox
                label="Usar a cor padrão"
                checked={form.useDefaultColor}
                onChange={(event) =>
                  setForm({ ...form, useDefaultColor: event.target.checked })
                }
              />
            </div>
            <p className="m-0 text-11 text-text-subtle">
              É a cor das barras da grade: uma por projeto, para a leitura vertical
              agrupar. Sem cor escolhida, a barra usa {DEFAULT_PROJECT_COLOR}.
            </p>
          </div>

          <Checkbox
            label="Reserva de capacidade"
            checked={form.isCapacityReserve}
            onChange={(event) =>
              setForm({ ...form, isCapacityReserve: event.target.checked })
            }
            hint="Sustentação sob demanda: as iniciativas deste projeto não contam para sobrecarga de squad nem para conflito de pessoa, e não aparecem no backlog."
          />

          {isEditing && (
            <Checkbox
              label="Projeto ativo"
              checked={form.isActive}
              onChange={(event) => setForm({ ...form, isActive: event.target.checked })}
              hint="Inativo continua no histórico e nas alocações já feitas."
            />
          )}

          {save.isError && (
            <p className="m-0 rounded-sm border border-danger bg-danger-soft p-2 text-12 text-danger">
              {describeError(save.error)}
            </p>
          )}

          {detail.data && (
            <section className="border-t border-border pt-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-12 font-semibold text-text-subtle">
                  {pluralize(
                    detail.data.initiatives.length,
                    'iniciativa',
                    'iniciativas',
                    'Nenhuma iniciativa',
                  )}
                </h3>
                <Button onClick={() => onAddInitiative(detail.data.project)}>
                  Adicionar iniciativa
                </Button>
              </div>
              <ul className="m-0 mt-2 flex list-none flex-col gap-1 p-0">
                {sortInitiatives(detail.data.initiatives).map((initiative) => (
                  <li key={initiative.id}>
                    <button
                      type="button"
                      onClick={() => onEditInitiative(detail.data.project, initiative.id)}
                      className="flex w-full items-center gap-2 rounded-sm px-2 py-1 text-left hover:bg-neutral-soft"
                    >
                      <span className="min-w-0 flex-1 truncate text-14">
                        {initiative.name}
                      </span>
                      <StatusLozenge status={initiative.status} />
                    </button>
                  </li>
                ))}
              </ul>
              <p className="mt-2 mb-0 text-11 text-text-subtle">
                Um projeto não pode ficar sem iniciativa (RN-I2): excluir a última é
                recusado, e o caminho é marcar a iniciativa como{' '}
                {INITIATIVE_STATUS_LABEL.CANCELLED.toLowerCase()}.
              </p>
            </section>
          )}

          {isEditing && (
            <section className="border-t border-border pt-4">
              {confirmingDelete ? (
                <div className="flex flex-col gap-2">
                  <p className="m-0 text-12">
                    Excluir apaga o projeto e as iniciativas dele. Se alguma tiver
                    alocação, a exclusão é recusada.
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
                  Excluir projeto
                </Button>
              )}
            </section>
          )}
        </div>
      )}
    </Drawer>
  );
}
