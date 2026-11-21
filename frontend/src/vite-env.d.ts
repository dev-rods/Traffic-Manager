/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Só o Vite lê (vite.config.ts): alvo do proxy /api em npm run dev. */
  readonly VITE_API_PROXY_TARGET?: string
  readonly VITE_APP_NAME: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
