import { describe, expect, it } from 'vitest';
import { readParams, writeParams } from '../src/lib/url-state';

const DEFAULTS = { view: 'grid', squad: '', sort: 'project', dir: 'asc' };

describe('readParams', () => {
  it('lê o que está na URL e completa o resto com o default', () => {
    expect(readParams('?view=list&squad=abc', DEFAULTS)).toEqual({
      view: 'list',
      squad: 'abc',
      sort: 'project',
      dir: 'asc',
    });
  });

  it('ignora parâmetro que o estado não conhece', () => {
    expect(readParams('?intruso=1', DEFAULTS)).toEqual(DEFAULTS);
  });

  it('trata valor vazio como ausente', () => {
    expect(readParams('?view=', DEFAULTS).view).toBe('grid');
  });

  it('aceita a busca sem a interrogação', () => {
    expect(readParams('view=list', DEFAULTS).view).toBe('list');
  });

  it('decodifica o valor', () => {
    expect(readParams('?squad=Dados%20A', DEFAULTS).squad).toBe('Dados A');
  });
});

describe('writeParams', () => {
  it('omite quem está no default: a URL mostra o que foi escolhido', () => {
    expect(writeParams(DEFAULTS, DEFAULTS)).toBe('');
  });

  it('escreve só o que difere', () => {
    expect(writeParams({ ...DEFAULTS, view: 'list' }, DEFAULTS)).toBe('?view=list');
  });

  it('mantém ordem estável para a URL não mudar sozinha entre renders', () => {
    const state = { ...DEFAULTS, view: 'list', squad: 'abc', dir: 'desc' };
    expect(writeParams(state, DEFAULTS)).toBe(writeParams({ ...state }, DEFAULTS));
    expect(writeParams(state, DEFAULTS)).toBe('?dir=desc&squad=abc&view=list');
  });

  it('escapa o valor', () => {
    expect(writeParams({ ...DEFAULTS, squad: 'a b' }, DEFAULTS)).toBe('?squad=a+b');
  });

  it('volta ao começo: ler o que foi escrito devolve o mesmo estado', () => {
    const state = { ...DEFAULTS, view: 'list', squad: 'x1', dir: 'desc' };
    expect(readParams(writeParams(state, DEFAULTS), DEFAULTS)).toEqual(state);
  });
});
