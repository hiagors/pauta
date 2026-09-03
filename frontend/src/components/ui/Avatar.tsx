import { initials } from '../../lib/format';
import { cx } from './cx';

/**
 * Avatar circular de 24px com iniciais (§10.1).
 *
 * Não há upload de foto no v1, então a inicial **é** o avatar. A cor sai de um
 * hash do nome para que a mesma pessoa tenha sempre o mesmo disco — reconhecer
 * pela cor é metade da utilidade de um avatar de iniciais.
 */
const PALETTE = [
  'bg-primary-soft text-primary',
  'bg-success-soft text-success',
  'bg-warning-soft text-warning',
  'bg-danger-soft text-danger',
  'bg-neutral-soft text-text-subtle',
] as const;

function paletteIndex(seed: string): number {
  let hash = 0;
  for (let i = 0; i < seed.length; i += 1) {
    hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  }
  return Math.abs(hash) % PALETTE.length;
}

export interface AvatarProps {
  readonly name: string;
  /** Some da árvore de acessibilidade quando o nome já está escrito ao lado. */
  readonly decorative?: boolean;
  readonly className?: string;
}

export function Avatar({ name, decorative = false, className }: AvatarProps) {
  return (
    <span
      title={name}
      aria-hidden={decorative || undefined}
      aria-label={decorative ? undefined : name}
      role={decorative ? undefined : 'img'}
      className={cx(
        'inline-flex size-6 shrink-0 items-center justify-center rounded-full',
        'text-11 leading-none font-semibold select-none',
        PALETTE[paletteIndex(name)],
        className,
      )}
    >
      {initials(name)}
    </span>
  );
}

export interface AvatarStackProps {
  readonly names: readonly string[];
  /** Acima disso vira "+N": uma pilha de dez discos não informa nada. */
  readonly max?: number;
}

/** Empilhados com sobreposição negativa quando forem vários (§10.1). */
export function AvatarStack({ names, max = 4 }: AvatarStackProps) {
  const shown = names.slice(0, max);
  const hidden = names.slice(max);
  return (
    <span className="inline-flex items-center" aria-label={names.join(', ')} role="img">
      {shown.map((name) => (
        <Avatar
          key={name}
          name={name}
          decorative
          className="-ml-1 ring-2 ring-surface first:ml-0"
        />
      ))}
      {hidden.length > 0 && (
        <span
          title={hidden.join(', ')}
          aria-hidden
          className={cx(
            '-ml-1 inline-flex size-6 items-center justify-center rounded-full',
            'bg-neutral-soft text-11 font-semibold text-text-subtle ring-2 ring-surface',
          )}
        >
          +{hidden.length}
        </span>
      )}
    </span>
  );
}
