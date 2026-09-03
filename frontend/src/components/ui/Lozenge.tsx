import type { ReactNode } from 'react';
import type { Schemas } from '../../lib/api';
import { INITIATIVE_STATUS_LABEL, PRIORITY_LABEL } from '../../lib/format';
import { cx } from './cx';

/**
 * Lozenge: a pílula de status do §10.1.
 *
 * Retângulo de raio pequeno, 11px, peso 600, fundo tonal. Sem `uppercase`
 * (§10.2) — o rótulo em português já é curto o bastante para caber.
 */
export type LozengeTone =
  | 'neutral'
  | 'muted'
  | 'primary'
  | 'success'
  | 'warning'
  | 'danger';

const TONE: Record<LozengeTone, string> = {
  neutral: 'bg-neutral-soft text-text-subtle',
  muted: 'bg-neutral-soft text-text-disabled',
  primary: 'bg-primary-soft text-primary',
  success: 'bg-success-soft text-success',
  warning: 'bg-warning-soft text-warning',
  danger: 'bg-danger-soft text-danger',
};

export interface LozengeProps {
  readonly tone?: LozengeTone;
  readonly title?: string;
  readonly children: ReactNode;
}

export function Lozenge({ tone = 'neutral', title, children }: LozengeProps) {
  return (
    <span
      title={title}
      className={cx(
        'inline-block max-w-full truncate rounded-sm px-1 py-px align-middle',
        'text-11 leading-4 font-semibold',
        TONE[tone],
      )}
    >
      {children}
    </span>
  );
}

/** Uma cor por status (§10.1: "um por status"). */
const STATUS_TONE: Record<Schemas['InitiativeStatus'], LozengeTone> = {
  BACKLOG: 'neutral',
  PLANNED: 'primary',
  IN_PROGRESS: 'warning',
  DEPRIORITIZED: 'muted',
  DONE: 'success',
  CANCELLED: 'danger',
};

export function StatusLozenge({ status }: { readonly status: Schemas['InitiativeStatus'] }) {
  return <Lozenge tone={STATUS_TONE[status]}>{INITIATIVE_STATUS_LABEL[status]}</Lozenge>;
}

/** Uma cor por prioridade (§10.1: "um por prioridade"). */
const PRIORITY_TONE: Record<Schemas['Priority'], LozengeTone> = {
  HIGH: 'danger',
  MEDIUM: 'warning',
  LOW: 'neutral',
};

export function PriorityLozenge({ priority }: { readonly priority: Schemas['Priority'] }) {
  return <Lozenge tone={PRIORITY_TONE[priority]}>{PRIORITY_LABEL[priority]}</Lozenge>;
}
