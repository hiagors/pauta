import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { api, ApiError } from '../../lib/api';
import { warningCount } from '../../lib/alerts';
import { pluralize } from '../../lib/format';
import { withQuery } from '../../lib/query';
import { cx } from '../ui/cx';
import { AlertPanel } from './AlertPanel';

/**
 * O sino da topbar (§10.3).
 *
 * Só `WARNING` **não silenciado** alimenta o contador: `INFO` é informação, e
 * inflar o número tira o sentido dele.
 *
 * A chamada, porém, vai com `include_muted=true`. É uma requisição só para as
 * duas leituras: o contador filtra o que interessa a ele, e o painel precisa
 * dos silenciados com `mute_id` e `mute_reason` para oferecer "Reativar".
 *
 * A janela é a default do §8 — da sprint atual (RN12) até a última cadastrada.
 * Quem decide isso é o backend, não o front.
 */
const ALERTS_QUERY = { include_muted: true } as const;

function AlertBell() {
  const [open, setOpen] = useState(false);
  const alerts = useQuery({
    queryKey: ['alerts', ALERTS_QUERY],
    queryFn: ({ signal }) => api.listAlerts(ALERTS_QUERY, signal),
  });

  if (alerts.isPending) {
    // Esqueleto, não spinner (§10.5). No tamanho final, para a topbar não pular.
    return <span aria-hidden className="size-8 animate-pulse rounded-sm bg-neutral-soft" />;
  }

  const failed = alerts.isError;
  const count = failed ? 0 : warningCount(alerts.data.items);
  const label = failed
    ? `Não foi possível carregar os alertas. ${
        alerts.error instanceof ApiError ? alerts.error.message : 'Erro desconhecido.'
      }`
    : count === 0
      ? 'Nenhum aviso aberto'
      : pluralize(count, 'aviso aberto', 'avisos abertos');

  return (
    <>
      <button
        type="button"
        title={label}
        aria-label={label}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={() => setOpen(true)}
        className={cx(
          'relative inline-flex size-8 items-center justify-center rounded-sm',
          'hover:bg-neutral-soft',
          failed ? 'text-danger' : 'text-text-subtle hover:text-text',
        )}
      >
        <svg className="icon size-4" aria-hidden focusable="false">
          <use href={failed ? '#icon-warning' : '#icon-bell'} />
        </svg>
        {count > 0 && (
          <span
            aria-hidden
            className={cx(
              'absolute top-0.5 right-0.5 inline-flex min-w-4 justify-center rounded-full',
              'bg-danger px-1 text-11 leading-4 font-semibold text-white',
            )}
          >
            {count}
          </span>
        )}
      </button>

      <AlertPanel
        open={open}
        onClose={() => setOpen(false)}
        error={alerts.isError ? alerts.error : null}
        data={alerts.data}
        onRetry={() => void alerts.refetch()}
      />
    </>
  );
}

export default withQuery(AlertBell);
