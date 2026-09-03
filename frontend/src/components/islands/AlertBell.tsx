import { useQuery } from '@tanstack/react-query';
import { api, ApiError } from '../../lib/api';
import { withQuery } from '../../lib/query';
import { pluralize } from '../../lib/format';
import { cx } from '../ui/cx';

/**
 * O sino da topbar (§10.3).
 *
 * Só `WARNING` **não silenciado** alimenta o contador — por isso a chamada vai
 * com o default `include_muted=false` e ainda filtra por severidade: `INFO` é
 * informação, não aviso, e inflar o número tira o sentido dele.
 *
 * A janela também é a default do §8: da sprint atual (RN12) até a última
 * cadastrada. Quem decide isso é o backend, não o front.
 */
function AlertBell() {
  const alerts = useQuery({
    queryKey: ['alerts', { include_muted: false }],
    queryFn: ({ signal }) => api.listAlerts(undefined, signal),
  });

  if (alerts.isPending) {
    // Esqueleto, não spinner (§10.5). No tamanho final, para a topbar não pular.
    return <span aria-hidden className="size-8 animate-pulse rounded-sm bg-neutral-soft" />;
  }

  if (alerts.isError) {
    const reason =
      alerts.error instanceof ApiError ? alerts.error.message : 'Erro desconhecido.';
    return (
      <span
        role="status"
        title={`Não foi possível carregar os alertas. ${reason}`}
        className="inline-flex size-8 items-center justify-center rounded-sm text-danger"
      >
        <svg className="icon size-4" aria-hidden focusable="false">
          <use href="#icon-warning" />
        </svg>
        <span className="sr-only">Não foi possível carregar os alertas.</span>
      </span>
    );
  }

  const warnings = alerts.data.items.filter((alert) => alert.severity === 'WARNING');
  const label =
    warnings.length === 0
      ? 'Nenhum aviso aberto'
      : pluralize(warnings.length, 'aviso aberto', 'avisos abertos');

  return (
    <span
      role="status"
      title={label}
      className="relative inline-flex size-8 items-center justify-center rounded-sm text-text-subtle"
    >
      <svg className="icon size-4" aria-hidden focusable="false">
        <use href="#icon-bell" />
      </svg>
      {warnings.length > 0 && (
        <span
          aria-hidden
          className={cx(
            'absolute top-0.5 right-0.5 inline-flex min-w-4 justify-center rounded-full',
            'bg-danger px-1 text-11 leading-4 font-semibold text-white',
          )}
        >
          {warnings.length}
        </span>
      )}
      <span className="sr-only">{label}</span>
    </span>
  );
}

export default withQuery(AlertBell);
