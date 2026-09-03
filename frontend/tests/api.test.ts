import { describe, expect, it } from 'vitest';
import { ApiError, createApiClient, NETWORK_ERROR_CODE, UNEXPECTED_ERROR_CODE } from '../src/lib/api';

/** `fetch` de mentira: registra a chamada e devolve o que o teste mandar. */
function stubFetch(response: Response | (() => never)) {
  const calls: Array<{ url: string; init: RequestInit }> = [];
  const impl = (async (input: RequestInfo | URL, init?: RequestInit) => {
    calls.push({ url: String(input), init: init ?? {} });
    if (typeof response === 'function') response();
    return response;
  }) as typeof fetch;
  return { calls, impl };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'content-type': 'application/json' },
  });
}

function clientWith(response: Response | (() => never)) {
  const { calls, impl } = stubFetch(response);
  return {
    calls,
    api: createApiClient({ baseUrl: 'http://api.local/', fetchImpl: impl }),
  };
}

describe('montagem da URL', () => {
  it('junta a base com o caminho do §8 sem duplicar a barra', async () => {
    const { api, calls } = clientWith(json([]));
    await api.listProjects();
    expect(calls[0]!.url).toBe('http://api.local/api/v1/projects');
  });

  it('serializa os filtros que vieram', async () => {
    const { api, calls } = clientWith(json([]));
    await api.listProjects({ active: true, q: 'catálogo' });
    expect(calls[0]!.url).toBe(
      'http://api.local/api/v1/projects?active=true&q=cat%C3%A1logo',
    );
  });

  it('omite filtro nulo ou ausente: para a API, ausência é "sem filtro"', async () => {
    const { api, calls } = clientWith(json([]));
    await api.listProjects({ active: null, q: undefined });
    expect(calls[0]!.url).toBe('http://api.local/api/v1/projects');
  });

  it('usa os nomes do §8 na query de sprints, inclusive `from`', async () => {
    const { api, calls } = clientWith(json([]));
    await api.listSprints({ from: 18, to: 22 });
    expect(calls[0]!.url).toBe('http://api.local/api/v1/sprints?from=18&to=22');
  });

  it('a importação de snapshot manda `confirm=true`, que é obrigatório', async () => {
    const { api, calls } = clientWith(json({ path: 'x', mode: 'replace', counts: {} }));
    await api.importSnapshot({ path: '/tmp/x.json', mode: 'replace' });
    expect(calls[0]!.url).toBe('http://api.local/api/v1/snapshots/import?confirm=true');
  });
});

describe('corpo e método', () => {
  it('manda JSON no POST com o content-type certo', async () => {
    const { api, calls } = clientWith(json({}, 201));
    await api.muteAlert({
      fingerprint: 'abc',
      alert_type: 'MEMBER_CONFLICT',
      reason: 'combinado com a squad',
    });
    const call = calls[0]!;
    expect(call.init.method).toBe('POST');
    expect(call.init.body).toBe(
      JSON.stringify({
        fingerprint: 'abc',
        alert_type: 'MEMBER_CONFLICT',
        reason: 'combinado com a squad',
      }),
    );
    expect((call.init.headers as Record<string, string>)['content-type']).toBe(
      'application/json',
    );
  });

  it('o DELETE de intervalo leva o corpo, como o §8 pede', async () => {
    const { api, calls } = clientWith(json({ removed: [] }));
    await api.deallocateRange({
      initiative_id: 'i1',
      from_sprint_number: 18,
      to_sprint_number: 22,
    });
    expect(calls[0]!.init.method).toBe('DELETE');
    expect(calls[0]!.init.body).toContain('"from_sprint_number":18');
  });

  it('204 vira `undefined`, e não uma tentativa de ler JSON vazio', async () => {
    const { api } = clientWith(new Response(null, { status: 204 }));
    await expect(api.deleteProject('p1')).resolves.toBeUndefined();
  });
});

describe('erro', () => {
  it('traduz o envelope do §8 em ApiError com code, message e details', async () => {
    const { api } = clientWith(
      json(
        {
          error: {
            code: 'SPRINT_NOT_FOUND',
            message: 'Sprint 25 não existe.',
            details: { sprint_number: 25 },
          },
        },
        422,
      ),
    );
    const error = await api.listProjects().catch((caught: unknown) => caught);
    expect(error).toBeInstanceOf(ApiError);
    const apiError = error as ApiError;
    expect(apiError.status).toBe(422);
    expect(apiError.code).toBe('SPRINT_NOT_FOUND');
    expect(apiError.message).toBe('Sprint 25 não existe.');
    expect(apiError.details).toEqual({ sprint_number: 25 });
  });

  it('resposta de erro fora do envelope não vira `undefined` silencioso', async () => {
    const { api } = clientWith(json({ detail: 'qualquer coisa' }, 500));
    const error = (await api.listProjects().catch((caught: unknown) => caught)) as ApiError;
    expect(error.code).toBe(UNEXPECTED_ERROR_CODE);
    expect(error.status).toBe(500);
  });

  it('API fora do ar vira erro com código próprio e a base na mensagem', async () => {
    const { api } = clientWith(() => {
      throw new TypeError('fetch failed');
    });
    const error = (await api.listProjects().catch((caught: unknown) => caught)) as ApiError;
    expect(error.code).toBe(NETWORK_ERROR_CODE);
    expect(error.status).toBe(0);
    expect(error.message).toContain('http://api.local');
  });
});
