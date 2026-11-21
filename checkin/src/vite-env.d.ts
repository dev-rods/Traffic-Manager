/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Só o Vite lê (vite.config.ts): alvo do proxy /api em npm run dev. */
  readonly VITE_API_PROXY_TARGET?: string
  readonly VITE_BOOKING_API_KEY: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
