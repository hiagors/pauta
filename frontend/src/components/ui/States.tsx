import type { ReactNode } from 'react';
import { ApiError } from '../../lib/api';
import { Button } from './Button';
import { cx } from './cx';

/**
 * Os quatro estados que toda tela precisa desenhar (§10.5).
 *
 * Ficam num módulo só porque a grade, a lista e o backlog contam a mesma
 * história com palavras diferentes: se cada tela reescrevesse o próprio bloco
 * de erro, três telas teriam três formas de dizer "não deu".
 */

/** Cartão: raio de 4px e nenhuma sombra — sombra é só para o que flutua (§10.1). */
export function Card({
  children,
  className,
}: {
  readonly children: ReactNode;
  readonly className?: string;
}) {
  return (
    <section className={cx('rounded-md border border-border bg-surface', className)}>
      {children}
    </section>
  );
}

/** Esqueleto, nunca spinner centralizado (§10.5). */
export function Skeleton({ lines = 3 }: { readonly lines?: number }) {
  const widths = ['w-40', 'w-64', 'w-52', 'w-72', 'w-48'];
  return (
    <div className="flex flex-col gap-2 p-4">
      {Array.from({ length: lines }, (_, index) => (
        <div
          key={index}
          aria-hidden
          className={cx('h-4 animate-pulse rounded-sm bg-neutral-soft', widths[index % widths.length])}
        />
      ))}
      <span className="sr-only">Carregando…</span>
    </div>
  );
}

/** Vazio é convite: diz o que não há e qual ação resolve (§10.5). */
export function EmptyState({
  message,
  action,
}: {
  readonly message: string;
  readonly action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-start gap-3 p-4">
      <p className="m-0 text-14">{message}</p>
      {action}
    </div>
  );
}

/** Extrai a frase que a API mandou; o resto é fallback para o inesperado. */
export function describeError(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return String(error);
}

/** Erro não pede desculpa e não é vago: diz o que falhou e como tentar de novo. */
export function ErrorState({
  what,
  error,
  onRetry,
}: {
  /** Completa "Não foi possível carregar …". */
  readonly what: string;
  readonly error: unknown;
  readonly onRetry?: () => void;
}) {
  return (
    <div className="p-4">
      <p className="m-0 text-14 font-semibold">Não foi possível carregar {what}.</p>
      <p className="mt-1 mb-3 text-12 text-text-subtle">{describeError(error)}</p>
      {onRetry && (
        <Button variant="primary" onClick={onRetry}>
          Tentar de novo
        </Button>
      )}
    </div>
  );
}
