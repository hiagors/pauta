import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { api, type AlertOut, type AlertsOut } from '../../lib/api';
import { alertContext, groupBySprint, mutedAlerts, openAlerts } from '../../lib/alerts';
import { ALERT_TYPE_LABEL, pluralize } from '../../lib/format';
import { Button } from '../ui/Button';
import { Drawer } from '../ui/Drawer';
import { Lozenge } from '../ui/Lozenge';
import { EmptyState, ErrorState, Skeleton, describeError } from '../ui/States';
import { cx } from '../ui/cx';

/**
 * O painel lateral de alertas (§10.3).
 *
 * Abre pelo sino da topbar e mostra os alertas agrupados por sprint, cada um
 * com a frase específica que o domínio escreveu (§7.3), o link para a tela
 * onde ele se resolve e a ação de silenciar.
 *
 * Os silenciados não somem: ficam atrás de um contador expansível, com o
 * motivo à vista e o botão de reativar — que usa o `mute_id` que veio no
 * próprio alerta. Silenciamento sem caminho de volta é silenciamento perdido.
 *
 * A chamada vai com `include_muted=true` de propósito: uma requisição só
 * alimenta as duas listas e o contador do sino, que filtra `WARNING` não
 * silenciado do mesmo dado.
 */
export interface AlertPanelProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly error: unknown;
  /** Ausente enquanto a primeira carga não terminou. */
  readonly data: AlertsOut | undefined;
  readonly onRetry: () => void;
}

export function AlertPanel({ open, onClose, error, data, onRetry }: AlertPanelProps) {
  const [showMuted, setShowMuted] = useState(false);
  const items = data?.items ?? [];
  const visible = openAlerts(items);
  const muted = mutedAlerts(items);

  return (
    <Drawer
      open={open}
      onClose={onClose}
      title="Alertas"
      subtitle="Da sprint atual até a última cadastrada. Aviso, nunca bloqueio."
      width={480}
    >
      {error ? (
        <ErrorState what="os alertas" error={error} onRetry={onRetry} />
      ) : !data ? (
        <Skeleton lines={4} />
      ) : items.length === 0 ? (
        <EmptyState message="Nenhum alerta na janela. Squads e pessoas estão sem conflito e sem ociosidade nas sprints cadastradas." />
      ) : (
        <div className="flex flex-col gap-5">
          {visible.length === 0 ? (
            <p className="m-0 text-14 text-text-subtle">
              Nenhum alerta aberto — os {muted.length} existentes estão silenciados.
            </p>
          ) : (
            groupBySprint(visible).map((group) => (
              <section key={group.sprintNumber} className="flex flex-col gap-2">
                <h3 className="text-12 font-semibold text-text-subtle">
                  Sprint {group.sprintNumber}
                </h3>
                {group.alerts.map((alert) => (
                  <AlertCard key={alert.fingerprint} alert={alert} />
                ))}
              </section>
            ))
          )}

          {muted.length > 0 && (
            <section className="border-t border-border pt-4">
              <button
                type="button"
                aria-expanded={showMuted}
                onClick={() => setShowMuted((current) => !current)}
                className="flex h-8 w-full items-center gap-2 rounded-sm px-2 text-left text-12 font-semibold text-text-subtle hover:bg-neutral-soft hover:text-text"
              >
                <span aria-hidden>{showMuted ? '▾' : '▸'}</span>
                {pluralize(muted.length, 'alerta silenciado', 'alertas silenciados')}
              </button>
              {showMuted && (
                <div className="mt-2 flex flex-col gap-2">
                  {groupBySprint(muted).map((group) =>
                    group.alerts.map((alert) => (
                      <AlertCard key={alert.fingerprint} alert={alert} />
                    )),
                  )}
                </div>
              )}
            </section>
          )}
        </div>
      )}
    </Drawer>
  );
}

/** Tudo que lê alerta relê depois de silenciar ou reativar. */
function useInvalidateAlerts() {
  const client = useQueryClient();
  return () => {
    void client.invalidateQueries({ queryKey: ['alerts'] });
  };
}

function AlertCard({ alert }: { readonly alert: AlertOut }) {
  const [muting, setMuting] = useState(false);
  const context = alertContext(alert);

  return (
    <article
      className={cx(
        'rounded-md border p-3',
        alert.is_muted
          ? 'border-border bg-neutral-soft'
          : alert.severity === 'WARNING'
            ? 'border-danger bg-danger-soft'
            : 'border-border bg-surface',
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Lozenge tone={alert.severity === 'WARNING' ? 'danger' : 'neutral'}>
          {ALERT_TYPE_LABEL[alert.type]}
        </Lozenge>
        <span className="text-11 text-text-subtle">Sprint {alert.sprint_number}</span>
      </div>

      <p className="mt-2 mb-0 text-14">{alert.message}</p>

      {alert.entity_refs.length > 0 && (
        <p className="mt-1 mb-0 text-11 text-text-subtle">
          {alert.entity_refs.map((ref) => ref.name).join(' · ')}
        </p>
      )}

      {alert.is_muted && alert.mute_reason && (
        <p className="mt-2 mb-0 text-12 text-text-subtle">
          <span className="font-semibold">Silenciado:</span> {alert.mute_reason}
        </p>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <a
          href={context.href}
          className="text-12 font-semibold text-primary underline underline-offset-2"
        >
          {context.label}
        </a>
        <span className="ml-auto flex items-center gap-2">
          {alert.is_muted ? (
            <UnmuteButton alert={alert} />
          ) : (
            !muting && <Button onClick={() => setMuting(true)}>Silenciar</Button>
          )}
        </span>
      </div>

      {muting && !alert.is_muted && (
        <MuteForm alert={alert} onDone={() => setMuting(false)} />
      )}
    </article>
  );
}

/**
 * O motivo é obrigatório (§6.9) e fica em texto livre.
 *
 * Pedir o motivo num formulário embutido, e não num segundo diálogo por cima
 * do painel, mantém à vista a frase que está sendo silenciada — que é
 * exatamente o que a pessoa precisa reler antes de decidir.
 */
function MuteForm({
  alert,
  onDone,
}: {
  readonly alert: AlertOut;
  readonly onDone: () => void;
}) {
  const invalidate = useInvalidateAlerts();
  const [reason, setReason] = useState('');
  const mutation = useMutation({
    mutationFn: () =>
      api.muteAlert({
        fingerprint: alert.fingerprint,
        alert_type: alert.type,
        reason: reason.trim(),
      }),
    onSuccess: () => {
      invalidate();
      onDone();
    },
  });

  return (
    <div className="mt-3 flex flex-col gap-2 border-t border-border pt-3">
      <label className="text-12 text-text-subtle" htmlFor={`motivo-${alert.fingerprint}`}>
        Motivo do silenciamento
      </label>
      <textarea
        id={`motivo-${alert.fingerprint}`}
        rows={2}
        autoFocus
        value={reason}
        onChange={(event) => setReason(event.target.value)}
        placeholder="Ex.: combinado com o time; a segunda frente é acompanhamento."
        className="rounded-sm border border-border-strong bg-surface px-2 py-1 text-14 text-text hover:border-primary focus:border-primary"
      />
      {mutation.isError && (
        <p className="m-0 text-12 text-danger">{describeError(mutation.error)}</p>
      )}
      <div className="flex justify-end gap-2">
        <Button onClick={onDone}>Cancelar</Button>
        <Button
          variant="primary"
          disabled={reason.trim() === '' || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? 'Silenciando…' : 'Silenciar'}
        </Button>
      </div>
    </div>
  );
}

function UnmuteButton({ alert }: { readonly alert: AlertOut }) {
  const invalidate = useInvalidateAlerts();
  const mutation = useMutation({
    mutationFn: () => api.unmuteAlert(alert.mute_id ?? ''),
    onSuccess: invalidate,
  });

  // Sem `mute_id` não há como reativar: o botão some em vez de prometer uma
  // ação que só sabe falhar.
  if (!alert.mute_id) return null;

  return (
    <span className="flex items-center gap-2">
      {mutation.isError && (
        <span className="text-11 text-danger">{describeError(mutation.error)}</span>
      )}
      <Button onClick={() => mutation.mutate()} disabled={mutation.isPending}>
        {mutation.isPending ? 'Reativando…' : 'Reativar'}
      </Button>
    </span>
  );
}
