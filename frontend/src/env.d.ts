/// <reference types="astro/client" />

/** A base da API vem do ambiente (§10.5); o `mise.toml` é quem a define. O
 * prefixo `PUBLIC_` é o que faz o Astro expor a variável ao navegador. */
interface ImportMetaEnv {
  readonly PUBLIC_API_URL?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
