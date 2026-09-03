import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useEffect, useState } from 'react';
import { api, type MemberOut, type Schemas } from '../../lib/api';
import { Button } from '../ui/Button';
import { Checkbox } from '../ui/Checkbox';
import { Drawer } from '../ui/Drawer';
import { Field } from '../ui/Field';
import { describeError } from '../ui/States';
import { useToast } from '../ui/Toast';

/**
 * O drawer de pessoa (§10.3, bloco 1 da tela de time).
 *
 * Não existe excluir: membro nunca é apagado (§6.4). Apagar reescreveria
 * alocações passadas. O que existe é a caixa "Pessoa ativa" — inativo some dos
 * seletores e continua no histórico. Ela é um `PATCH`, e não o `DELETE` do §8,
 * porque o `DELETE` só sabe desativar: reativar alguém precisa do caminho de
 * volta.
 */
export interface MemberDrawerProps {
  /** `null` cria; um membro edita. */
  readonly member: MemberOut | null;
  readonly onClose: () => void;
}

interface MemberForm {
  name: string;
  shortName: string;
  role: string;
  isActive: boolean;
}

const BLANK: MemberForm = { name: '', shortName: '', role: '', isActive: true };

function toForm(member: MemberOut): MemberForm {
  return {
    name: member.name,
    shortName: member.short_name,
    role: member.role,
    isActive: member.is_active,
  };
}

function memberPatch(original: MemberOut, form: MemberForm): Schemas['MemberPatchIn'] {
  const patch: Schemas['MemberPatchIn'] = {};
  if (form.name.trim() !== original.name) patch.name = form.name.trim();
  if (form.shortName.trim() !== original.short_name) patch.short_name = form.shortName.trim();
  if (form.role !== original.role) patch.role = form.role;
  if (form.isActive !== original.is_active) patch.is_active = form.isActive;
  return patch;
}

export function MemberDrawer({ member, onClose }: MemberDrawerProps) {
  const client = useQueryClient();
  const { notify } = useToast();
  const [form, setForm] = useState<MemberForm>(member ? toForm(member) : BLANK);

  useEffect(() => {
    setForm(member ? toForm(member) : BLANK);
  }, [member]);

  const save = useMutation({
    mutationFn: () => {
      if (member) return api.updateMember(member.id, memberPatch(member, form));
      return api.createMember({
        name: form.name.trim(),
        short_name: form.shortName.trim(),
        role: form.role,
      });
    },
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: ['members'] });
      void client.invalidateQueries({ queryKey: ['squads'] });
      void client.invalidateQueries({ queryKey: ['alerts'] });
      notify(member ? `${form.name.trim()} salvo.` : `${form.name.trim()} cadastrado.`, 'success');
      onClose();
    },
  });

  const nameIsValid = form.name.trim() !== '';
  const shortNameIsValid = form.shortName.trim() !== '';

  return (
    <Drawer
      open
      onClose={onClose}
      title={member ? 'Editar pessoa' : 'Nova pessoa'}
      subtitle="Pessoa nunca é apagada; quem sai do time fica inativo."
      footer={
        <>
          <Button onClick={onClose}>Cancelar</Button>
          <Button
            variant="primary"
            disabled={!nameIsValid || !shortNameIsValid || save.isPending}
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
        <Field
          label="Nome curto"
          value={form.shortName}
          onChange={(event) => setForm({ ...form, shortName: event.target.value })}
          hint="É o que aparece nas barras da grade e nos seletores."
          error={shortNameIsValid ? undefined : 'O nome curto é obrigatório.'}
        />
        <Field
          label="Papel"
          value={form.role}
          onChange={(event) => setForm({ ...form, role: event.target.value })}
          hint="Texto livre, opcional."
        />
        {member && (
          <Checkbox
            label="Pessoa ativa"
            checked={form.isActive}
            onChange={(event) => setForm({ ...form, isActive: event.target.checked })}
            hint="Inativa some dos seletores e dos alertas. A composição de squad já gravada fica como histórico."
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
