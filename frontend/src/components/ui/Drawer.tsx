import { useEffect, useId, useRef, type ReactNode } from 'react';
import { Button } from './Button';
import { cx } from './cx';

/**
 * Painel lateral.
 *
 * O §10.3 pede drawer para criar e editar projeto, iniciativa, membro e squad
 * — "não página nova" — e é também onde o painel de alertas mora.
 *
 * Por baixo é o mesmo `<dialog>` do `Modal`: a armadilha de foco, o `Esc` e o
 * `inert` no resto da página vêm do navegador. O que muda é só a posição: em
 * vez do `margin: auto` que centraliza, ele é preso à direita e ocupa a altura
 * inteira.
 *
 * O conteúdo rola sozinho, entre um cabeçalho e um rodapé fixos: um formulário
 * comprido não pode empurrar o botão de salvar para fora da tela.
 */
export interface DrawerProps {
  readonly open: boolean;
  readonly title: string;
  readonly onClose: () => void;
  /** Linha de apoio abaixo do título — o contexto do que está sendo editado. */
  readonly subtitle?: ReactNode;
  readonly children: ReactNode;
  readonly footer?: ReactNode;
  readonly width?: number;
}

export function Drawer({
  open,
  title,
  onClose,
  subtitle,
  children,
  footer,
  width = 460,
}: DrawerProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      aria-labelledby={titleId}
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
      style={{ width }}
      className={cx(
        'fixed inset-y-0 right-0 left-auto m-0 h-dvh max-h-dvh max-w-[calc(100vw-32px)]',
        'flex-col bg-surface p-0 text-text shadow-overlay',
        'backdrop:bg-[rgba(9,30,66,0.54)]',
        // `<dialog>` fechado é `display: none` pela folha do navegador, e um
        // `flex` fixo na classe venceria essa regra — o painel apareceria
        // fechado. `open:flex` só liga o flex quando ele está aberto.
        'open:flex',
      )}
    >
      <header className="flex shrink-0 items-start justify-between gap-4 border-b border-border px-5 py-4">
        <div className="min-w-0">
          <h2 id={titleId} className="truncate text-16 font-semibold">
            {title}
          </h2>
          {subtitle && <p className="mt-1 mb-0 text-12 text-text-subtle">{subtitle}</p>}
        </div>
        <Button variant="ghost" aria-label="Fechar" onClick={onClose} className="px-2">
          ✕
        </Button>
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4 text-14">{children}</div>

      {footer && (
        <footer className="flex shrink-0 items-center justify-end gap-2 border-t border-border px-5 py-4">
          {footer}
        </footer>
      )}
    </dialog>
  );
}
