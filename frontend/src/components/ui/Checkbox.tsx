import { useId, type InputHTMLAttributes, type ReactNode } from 'react';
import { cx } from './cx';

/**
 * Caixa de seleção com rótulo.
 *
 * Nativa, pelo mesmo motivo do `Select`: teclado, leitor de tela e o estado
 * indeterminado já vêm prontos. O `hint` é ligado por `aria-describedby`, para
 * que "inativo some dos seletores" seja lido junto com o campo — e não fique
 * só na tela para quem enxerga.
 */
export interface CheckboxProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id' | 'type'> {
  readonly label: ReactNode;
  readonly hint?: ReactNode;
}

export function Checkbox({ label, hint, className, ...props }: CheckboxProps) {
  const id = useId();
  const hintId = `${id}-apoio`;
  return (
    <div className={cx('flex flex-col gap-1', className)}>
      <span className="flex items-center gap-2">
        <input
          id={id}
          type="checkbox"
          aria-describedby={hint ? hintId : undefined}
          {...props}
          className="size-4 shrink-0 accent-primary disabled:cursor-not-allowed"
        />
        <label htmlFor={id} className="text-14">
          {label}
        </label>
      </span>
      {hint && (
        <p id={hintId} className="m-0 pl-6 text-11 text-text-subtle">
          {hint}
        </p>
      )}
    </div>
  );
}
