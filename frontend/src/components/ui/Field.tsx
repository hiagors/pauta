import { useId, type InputHTMLAttributes, type ReactNode } from 'react';
import { cx } from './cx';

/**
 * Campo de texto ou de número com rótulo e mensagem de apoio.
 *
 * Nativo, como o `Select`: validação, teclado numérico e leitor de tela já vêm
 * prontos. O `hint` fica abaixo e é ligado por `aria-describedby`, para o aviso
 * de intervalo ser lido junto com o campo, e não ficar só na tela.
 */
export interface FieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> {
  readonly label: string;
  readonly hint?: ReactNode;
  /** Marca o campo como inválido e substitui o `hint` pela mensagem. */
  readonly error?: string;
  readonly className?: string;
}

export function Field({ label, hint, error, className, ...props }: FieldProps) {
  const id = useId();
  const hintId = `${id}-apoio`;
  return (
    <div className={cx('flex flex-col gap-1', className)}>
      <label htmlFor={id} className="text-12 text-text-subtle">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error || hint ? hintId : undefined}
        {...props}
        className={cx(
          'h-8 rounded-sm border bg-surface px-2 text-14 text-text',
          'hover:border-primary focus:border-primary disabled:text-text-disabled',
          error ? 'border-danger' : 'border-border-strong',
        )}
      />
      {(error || hint) && (
        <p id={hintId} className={cx('m-0 text-11', error ? 'text-danger' : 'text-text-subtle')}>
          {error ?? hint}
        </p>
      )}
    </div>
  );
}
