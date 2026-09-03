import { useEffect, useRef, type ReactNode } from 'react';
import { cx } from './cx';

/**
 * Popover ancorado no elemento que o abriu.
 *
 * É o menu que a barra da grade abre (§10.3: "Mover", "Estender até",
 * "Remover"). Flutua, então tem sombra — e é o único motivo de ter (§10.1).
 *
 * Fecha no `Esc` e no clique fora. Não é modal: o `Esc` volta o foco para o
 * gatilho, que é quem continua na ordem de tabulação.
 */
export interface PopoverProps {
  readonly open: boolean;
  readonly onClose: () => void;
  /** Rótulo do menu para quem navega por leitor de tela. */
  readonly label: string;
  readonly children: ReactNode;
  readonly className?: string;
}

export function Popover({ open, onClose, label, children, className }: PopoverProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose();
    }
    // `pointerdown` e não `click`: fechar no começo do gesto evita que o
    // clique que fecha o popover acione o que estiver embaixo dele.
    function onPointerDown(event: PointerEvent) {
      const element = ref.current;
      if (element && !element.contains(event.target as Node)) onClose();
    }
    document.addEventListener('keydown', onKeyDown);
    document.addEventListener('pointerdown', onPointerDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.removeEventListener('pointerdown', onPointerDown);
    };
  }, [open, onClose]);

  useEffect(() => {
    if (open) ref.current?.querySelector('button')?.focus();
  }, [open]);

  if (!open) return null;

  return (
    <div
      ref={ref}
      role="menu"
      aria-label={label}
      className={cx(
        'absolute top-full left-0 z-30 mt-1 min-w-[180px] rounded-md border border-border',
        'bg-surface p-1 shadow-overlay',
        className,
      )}
    >
      {children}
    </div>
  );
}

/** Item do menu. Largura cheia e alinhado à esquerda, como todo menu. */
export function PopoverItem({
  children,
  onClick,
  danger = false,
}: {
  readonly children: ReactNode;
  readonly onClick: () => void;
  readonly danger?: boolean;
}) {
  return (
    <button
      type="button"
      role="menuitem"
      onClick={onClick}
      className={cx(
        'flex h-8 w-full items-center rounded-sm px-2 text-left text-14',
        danger ? 'text-danger hover:bg-danger-soft' : 'text-text hover:bg-neutral-soft',
      )}
    >
      {children}
    </button>
  );
}
