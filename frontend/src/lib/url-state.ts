/* Filtro persistido na URL (§10.3).
 *
 * A URL é o estado: recarregar a página, voltar no histórico ou mandar o link
 * para alguém tem que reproduzir a mesma tela. Por isso o filtro não mora em
 * `useState` — mora aqui, e o `useState` só espelha.
 *
 * As funções puras são separadas do hook de propósito: elas são o que os
 * testes exercitam, sem DOM e sem React.
 */
import { useCallback, useEffect, useState } from 'react';

/** Só string: o que vai para a URL volta como string, e converter num lugar só
 * evita `Number(undefined)` espalhado pelos componentes. */
export type UrlState = Record<string, string>;

/** Lê os parâmetros conhecidos; o que não está na URL fica com o default. */
export function readParams<T extends UrlState>(search: string, defaults: T): T {
  const params = new URLSearchParams(search);
  const result = { ...defaults };
  for (const key of Object.keys(defaults) as Array<keyof T & string>) {
    const value = params.get(key);
    if (value !== null && value !== '') result[key] = value as T[keyof T & string];
  }
  return result;
}

/**
 * Serializa de volta, omitindo quem está no default.
 *
 * Omitir o default é o que mantém a URL legível: `/planning` em vez de
 * `/planning?view=grid&sort=project&dir=asc&squad=&member=`. O que está lá é o
 * que foi escolhido.
 */
export function writeParams<T extends UrlState>(state: T, defaults: T): string {
  const params = new URLSearchParams();
  for (const key of Object.keys(defaults).sort() as Array<keyof T & string>) {
    const value = state[key];
    if (value && value !== defaults[key]) params.set(key, value);
  }
  const serialized = params.toString();
  return serialized ? `?${serialized}` : '';
}

/**
 * O estado do filtro, sincronizado com a barra de endereços.
 *
 * O terceiro item do retorno é `mounted`, e existe por causa do SSR: o Astro
 * renderiza a ilha no build, onde não há `location`. Renderizar os controles
 * antes de ler a URL faria o HTML do build divergir do primeiro render do
 * cliente — que é exatamente o erro de hidratação que o React reclama. Quem
 * chama segura o esqueleto até `mounted` virar `true`.
 *
 * A escrita é `replaceState`, não `pushState`: mexer num filtro não é navegar,
 * e encher o histórico faria o botão "voltar" percorrer combinações de filtro
 * em vez de sair da tela.
 */
export function useUrlState<T extends UrlState>(
  defaults: T,
): [T, (patch: Partial<T>) => void, boolean] {
  const [state, setState] = useState<T>(defaults);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setState(readParams(window.location.search, defaults));
    setMounted(true);
    // `defaults` é literal de módulo em todo uso: ler uma vez, na montagem.
  }, []);

  useEffect(() => {
    function onPopState() {
      setState(readParams(window.location.search, defaults));
    }
    window.addEventListener('popstate', onPopState);
    return () => window.removeEventListener('popstate', onPopState);
  }, []);

  const patch = useCallback(
    (changes: Partial<T>) => {
      setState((current) => {
        const next = { ...current, ...changes };
        const search = writeParams(next, defaults);
        window.history.replaceState(null, '', `${window.location.pathname}${search}`);
        return next;
      });
    },
    [],
  );

  return [state, patch, mounted];
}
