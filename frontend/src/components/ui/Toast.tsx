import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { cx } from './cx';

/**
 * Aviso efêmero de resultado de ação.
 *
 * Vive dentro da ilha, não no shell: cada ilha do Astro é uma raiz React
 * própria, e um provider global só existiria se a página inteira fosse React —
 * que é justamente o que a arquitetura de ilhas evita.
 *
 * `aria-live="polite"` porque toast é confirmação, não interrupção. O erro que
 * bloqueia a tela é estado de tela (§10.5), não toast.
 */
export type ToastTone = 'success' | 'danger' | 'neutral';

interface Toast {
  readonly id: number;
  readonly message: string;
  readonly tone: ToastTone;
}

interface ToastApi {
  readonly notify: (message: string, tone?: ToastTone) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

/** Milissegundos até sumir. Tempo de ler uma frase curta sem atrapalhar. */
const DISMISS_AFTER_MS = 5000;

const TONE: Record<ToastTone, string> = {
  success: 'border-success bg-success-soft text-success',
  danger: 'border-danger bg-danger-soft text-danger',
  neutral: 'border-border-strong bg-surface text-text',
};

export function ToastProvider({ children }: { readonly children: ReactNode }) {
  const [toasts, setToasts] = useState<readonly Toast[]>([]);
  const nextId = useRef(0);

  const notify = useCallback((message: string, tone: ToastTone = 'neutral') => {
    nextId.current += 1;
    const id = nextId.current;
    setToasts((current) => [...current, { id, message, tone }]);
    globalThis.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, DISMISS_AFTER_MS);
  }, []);

  const api = useMemo<ToastApi>(() => ({ notify }), [notify]);

  return (
    <ToastContext value={api}>
      {children}
      <div
        aria-live="polite"
        className="pointer-events-none fixed right-4 bottom-4 z-50 flex flex-col gap-2"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={cx(
              'pointer-events-auto max-w-[360px] rounded-md border px-3 py-2',
              'text-14 shadow-overlay',
              TONE[toast.tone],
            )}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext>
  );
}

/** Falha alto se a ilha esqueceu o provider — silêncio aqui vira aviso perdido. */
export function useToast(): ToastApi {
  const api = useContext(ToastContext);
  if (!api) throw new Error('useToast exige um <ToastProvider> acima na árvore.');
  return api;
}
