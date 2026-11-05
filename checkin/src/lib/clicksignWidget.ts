/**
 * Widget embedded da ClickSign (PRD 036). Carrega o script oficial uma vez e
 * monta/desmonta o widget num container. A assinatura (token no WhatsApp e
 * manuscrita) acontece dentro do iframe; o iPad só espera o `signed` e, de
 * qualquer jeito, confirma pelo backend (polling), nunca pelo evento.
 */
const SCRIPT = 'https://cdn-public-library.clicksign.com/embedded/embedded.min-2.1.0.js'
const LOAD_TIMEOUT_MS = 15_000

type WidgetEvent = 'loaded' | 'signed' | 'resized'

export interface ClicksignWidget {
  endpoint: string
  origin: string
  mount(containerId: string): void
  unmount(): void
  on(event: WidgetEvent, callback: (ev: { data?: { height?: number } }) => void): void
}

declare global {
  interface Window {
    Clicksign?: new (signerKey: string) => ClicksignWidget
  }
}

let loading: Promise<void> | null = null

export function loadClicksign(): Promise<void> {
  if (window.Clicksign) return Promise.resolve()
  if (loading) return loading
  loading = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = SCRIPT
    script.async = true
    const timer = window.setTimeout(() => fail(new Error('timeout')), LOAD_TIMEOUT_MS)
    function fail(error: Error) {
      window.clearTimeout(timer)
      script.remove()
      loading = null
      reject(error)
    }
    script.onload = () => {
      window.clearTimeout(timer)
      if (window.Clicksign) resolve()
      else fail(new Error('Clicksign ausente após o carregamento'))
    }
    script.onerror = () => fail(new Error('falha ao carregar o script da ClickSign'))
    document.head.appendChild(script)
  })
  return loading
}

/**
 * Monta o widget e devolve o `unmount`. `origin` é a nossa origem, não `*`:
 * o iframe só conversa com esta página.
 */
export function mountClicksign(
  signerKey: string,
  endpoint: string,
  containerId: string,
  onSigned: () => void,
  onResized: (height: number) => void
): () => void {
  const Ctor = window.Clicksign
  if (!Ctor) throw new Error('script da ClickSign não carregado')
  const widget = new Ctor(signerKey)
  widget.endpoint = endpoint
  widget.origin = window.location.origin
  widget.on('signed', onSigned)
  widget.on('resized', (ev) => {
    if (ev.data?.height) onResized(ev.data.height)
  })
  widget.mount(containerId)
  return () => {
    try {
      widget.unmount()
    } catch {
      // Já desmontado pelo próprio widget: nada a fazer.
    }
  }
}
