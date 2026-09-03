import type { ReactNode, ThHTMLAttributes, TdHTMLAttributes } from 'react';
import { cx } from './cx';

/**
 * Tabela densa do §10.1: linha de 40px, cabeçalho fixo, zebra desligada, hover
 * sutil.
 *
 * São primitivos, não uma tabela com dados: ordenação e filtro são de quem usa.
 * O `sticky` do cabeçalho depende de o contêiner ter altura e rolagem próprias
 * — quem monta a tela decide isso, por isso `Table` não cria o contêiner.
 */
export function Table({ children, className }: { readonly children: ReactNode; readonly className?: string }) {
  return (
    <table className={cx('w-full border-collapse text-14', className)}>{children}</table>
  );
}

export function THead({ children }: { readonly children: ReactNode }) {
  return (
    <thead className="sticky top-0 z-10 bg-surface">
      {children}
    </thead>
  );
}

export function TBody({ children }: { readonly children: ReactNode }) {
  return <tbody>{children}</tbody>;
}

export interface TrProps {
  readonly children: ReactNode;
  readonly onClick?: () => void;
}

export function Tr({ children, onClick }: TrProps) {
  return (
    <tr
      onClick={onClick}
      className={cx(
        'h-row border-b border-border',
        onClick && 'cursor-pointer',
        'hover:bg-neutral-soft',
      )}
    >
      {children}
    </tr>
  );
}

export function Th({ children, className, ...props }: ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      scope="col"
      {...props}
      className={cx(
        'h-row border-b border-border px-3 text-left align-middle',
        'text-12 font-semibold text-text-subtle',
        className,
      )}
    >
      {children}
    </th>
  );
}

export function Td({ children, className, ...props }: TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td {...props} className={cx('px-3 align-middle', className)}>
      {children}
    </td>
  );
}
