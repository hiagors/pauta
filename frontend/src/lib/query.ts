/* Estado de servidor: TanStack Query, em todas as ilhas, sem mistura (§4.2).
 *
 * Cada ilha do Astro é uma raiz React separada, então cada uma precisa do seu
 * `QueryClientProvider`. O `QueryClient`, porém, é um só por página: as ilhas
 * compartilham o módulo, e é isso que faz o sino da topbar e a tela abaixo dela
 * lerem o mesmo cache de `/alerts` em vez de baterem duas vezes na API.
 */
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { createElement, type ComponentType, type ReactElement } from 'react';

let client: QueryClient | undefined;

/** Preguiçoso de propósito: no build o módulo é importado, mas nenhuma query
 * roda, e criar o cliente aí seria trabalho jogado fora. */
export function getQueryClient(): QueryClient {
  client ??= new QueryClient({
    defaultOptions: {
      queries: {
        // A API é local: refazer a chamada a cada foco de janela custa mais
        // ruído do que dado fresco.
        refetchOnWindowFocus: false,
        // Uma tentativa a mais cobre o reload da API em `--reload`; além disso
        // é esconder do usuário que o servidor caiu.
        retry: 1,
        staleTime: 30_000,
      },
      mutations: {
        retry: 0,
      },
    },
  });
  return client;
}

/**
 * Embrulha o componente raiz de uma ilha no provider.
 *
 * Sem JSX porque este arquivo é `.ts` (é a estrutura do §5) — `createElement`
 * faz o mesmo. O que importa é a ilha exportar `withQuery(Componente)` e não
 * repetir o provider em cada arquivo.
 */
export function withQuery<P extends object>(
  Component: ComponentType<P>,
): (props: P) => ReactElement {
  function WithQuery(props: P): ReactElement {
    return createElement(
      QueryClientProvider,
      { client: getQueryClient() },
      createElement(Component, props),
    );
  }
  WithQuery.displayName = `withQuery(${Component.displayName ?? Component.name ?? 'Anônimo'})`;
  return WithQuery;
}
