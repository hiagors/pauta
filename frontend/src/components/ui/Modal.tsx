import { useEffect, useId, useRef, type ReactNode } from 'react';
import { Button } from './Button';

/**
 * Diálogo modal.
 *
 * Usa o `<dialog>` nativo com `showModal()` de propósito: a armadilha de foco,
 * o `Esc` e o `inert` no resto da página vêm do navegador, e não de uma
 * reimplementação em JavaScript que erra no primeiro caso de borda. O §10.5
 * pede navegação por teclado no diálogo de alocação (Fase 7) — é este.
 *
 * Sombra só aqui e nos outros elementos que flutuam (§10.1).
 */
export interface ModalProps {
  readonly open: boolean;
  readonly title: string;
  readonly onClose: () => void;
  readonly children: ReactNode;
  /** Rodapé com as ações; a primária é azul e é uma só. */
  readonly footer?: ReactNode;
}

export function Modal({ open, title, onClose, children, footer }: ModalProps) {
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
      // O `Esc` dispara `cancel`; sem isto o navegador fecharia o elemento e o
      // React continuaria achando que está aberto.
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      // Clique no backdrop tem o próprio `<dialog>` como alvo — o conteúdo
      // fica num filho, então esta comparação distingue os dois.
      onClick={(event) => {
        if (event.target === ref.current) onClose();
      }}
      className="m-auto w-[480px] max-w-[calc(100vw-32px)] rounded-md bg-surface p-0 text-text shadow-overlay backdrop:bg-[rgba(9,30,66,0.54)]"
    >
      <div className="flex items-start justify-between gap-4 px-5 pt-5">
        <h2 id={titleId} className="text-16 font-semibold">
          {title}
        </h2>
        <Button variant="ghost" aria-label="Fechar" onClick={onClose} className="px-2">
          ✕
        </Button>
      </div>
      <div className="px-5 py-4 text-14">{children}</div>
      {footer && <div className="flex justify-end gap-2 px-5 pb-5">{footer}</div>}
    </dialog>
  );
}
