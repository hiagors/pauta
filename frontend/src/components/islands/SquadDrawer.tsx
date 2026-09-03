import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api, type MemberOut, type Schemas, type SquadOut } from '../../lib/api';
import { Button } from '../ui/Button';
import { Checkbox } from '../ui/Checkbox';
import { Drawer } from '../ui/Drawer';
import { Field } from '../ui/Field';
import { Select } from '../ui/Select';
import { describeError } from '../ui/States';
import { useToast } from '../ui/Toast';

/**
 * O drawer de squad (§10.3, bloco 2 da tela de time): nome, representante,
 * ativo. Nada de lista de membros.
 *
 * Quem está na squad é a composição **por sprint** (D11), que é a matriz do
 * terceiro bloco. Um seletor de membros aqui inventaria a lista estática que o
 * modelo justamente removeu.
 *
 * O representante é uma ponte, não necessariamente quem executa: por RN-S1 ele
 * só precisa existir e estar ativo, e não é validado contra a composição.
 */
export interface SquadDrawerProps {
  /** `null` cria; uma squad edita. */
  readonly squad: SquadOut | null;
  readonly members: readonly MemberOut[];
  readonly onClose: () => void;
}

interface SquadForm {
  name: string;
  representativeId: string;
  isActive: boolean;
}

const BLANK: SquadForm = { name: '', representativeId: '', isActive: true };

function toForm(squad: SquadOut): SquadForm {
  return {
    name: squad.name,
    representativeId: squad.representative_member_id ?? '',
    isActive: squad.is_active,
  };
}

function squadPatch(original: SquadOut, form: SquadForm): Schemas['SquadPatchIn'] {
  const patch: Schemas['SquadPatchIn'] = {};
  const representative = form.representativeId === '' ? null : form.representativeId;
  if (form.name.trim() !== original.name) patch.name = form.name.trim();
  if (representative !== original.representative_member_id) {
    patch.representative_member_id = representative;
  }
  if (form.isActive !== original.is_active) patch.is_active = form.isActive;
  return patch;
}

export function SquadDrawer({ squad, members, onClose }: SquadDrawerProps) {
  const client = useQueryClient();
  const { notify } = useToast();
  const [form, setForm] = useState<SquadForm>(squad ? toForm(squad) : BLANK);

  useEffect(() => {
    setForm(squad ? toForm(squad) : BLANK);
  }, [squad]);

  const save = useMutation({
    mutationFn: () => {
      if (squad) return api.updateSquad(squad.id, squadPatch(squad, form));
      return api.createSquad({
        name: form.name.trim(),
        representative_member_id: form.representativeId === '' ? null : form.representativeId,
      });
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['squads'] });
      void client.invalidateQueries({ queryKey: ['alerts'] });
      void client.invalidateQueries({ queryKey: ['planning'] });
      notify(squad ? `Squad ${form.name.trim()} salva.` : `Squad ${form.name.trim()} criada.`, 'success');
      onClose();
    },
  });

  const nameIsValid = form.name.trim() !== '';

  return (
    <Drawer
      open
      onClose={onClose}
      title={squad ? 'Editar squad' : 'Nova squad'}
      subtitle="Quem está na squad é definido sprint a sprint, na matriz de composição."
      footer={
        <>
          <Button onClick={onClose}>Cancelar</Button>
          <Button
            variant="primary"
            disabled={!nameIsValid || save.isPending}
            onClick={() => save.mutate()}
          >
            {save.isPending ? 'Salvando…' : 'Salvar'}
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-4">
        <Field
          label="Nome"
          value={form.name}
          autoFocus
          onChange={(event) => setForm({ ...form, name: event.target.value })}
          error={nameIsValid ? undefined : 'O nome é obrigatório.'}
        />
        <Select
          label="Representante"
          placeholder="Sem representante"
          value={form.representativeId}
          onChange={(event) => setForm({ ...form, representativeId: event.target.value })}
          options={members.map((member) => ({ value: member.id, label: member.name }))}
        />
        <p className="m-0 text-11 text-text-subtle">
          Quem faz a ponte com a squad. Não precisa estar na composição — se não
          estiver na sprint atual, a matriz avisa, sem impedir nada.
        </p>
        {squad && (
          <Checkbox
            label="Squad ativa"
            checked={form.isActive}
            onChange={(event) => setForm({ ...form, isActive: event.target.checked })}
            hint="Inativa some dos seletores de alocação e dos alertas. As alocações já feitas continuam."
          />
        )}
        {save.isError && (
          <p className="m-0 rounded-sm border border-danger bg-danger-soft p-2 text-12 text-danger">
            {describeError(save.error)}
          </p>
        )}
      </div>
    </Drawer>
  );
}
