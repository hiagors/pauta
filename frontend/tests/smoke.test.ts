import { describe, expect, it } from 'vitest';

// Teste-fumaça do front. Existe para a task `mise run test` ter o que rodar antes
// da Fase 6 (§13, Fase 0) e para provar que o vitest está configurado.
describe('ambiente do front', () => {
  it('roda o vitest com a configuração do projeto', () => {
    expect(1 + 1).toBe(2);
  });
});
