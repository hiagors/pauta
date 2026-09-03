import type { ButtonHTMLAttributes, ReactNode } from 'react';
import { cx } from './cx';

/**
 * Botão.
 *
 * `primary` é azul e é **uma por tela** (§10.1) — o resto da tela usa `subtle`
 * ou `ghost`. Raio de 3px, como todo controle.
 */
export type ButtonVariant = 'primary' | 'subtle' | 'ghost' | 'danger';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: ButtonVariant;
  readonly children?: ReactNode;
}

const VARIANT: Record<ButtonVariant, string> = {
  primary: 'bg-primary text-white hover:bg-primary-hover',
  subtle: 'bg-neutral-soft text-text hover:bg-border',
  ghost: 'bg-transparent text-text-subtle hover:bg-neutral-soft hover:text-text',
  danger: 'bg-danger text-white hover:opacity-90',
};

export function Button({ variant = 'subtle', className, ...props }: ButtonProps) {
  return (
    <button
      type="button"
      {...props}
      className={cx(
        'inline-flex h-8 items-center gap-2 rounded-sm px-3 text-12 font-semibold',
        'transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        VARIANT[variant],
        className,
      )}
    />
  );
}
