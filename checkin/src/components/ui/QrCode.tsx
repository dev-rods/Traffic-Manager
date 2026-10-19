import { useEffect, useState } from 'react'
import QRCode from 'qrcode'

/**
 * QR gerado no próprio iPad a partir do texto (Pix "copia e cola" ou link da
 * fatura). Não depende de imagem vinda do provedor: o provedor simulado de
 * dev não tem uma, e o Asaas a devolveria em base64 pesado a cada consulta.
 */
export function QrCode({ value, label }: { value: string; label: string }) {
  const [src, setSrc] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    QRCode.toDataURL(value, { width: 560, margin: 1, errorCorrectionLevel: 'M' })
      .then((url) => active && setSrc(url))
      .catch(() => active && setSrc(null))
    return () => {
      active = false
    }
  }, [value])

  return (
    <div className="flex h-72 w-72 items-center justify-center rounded-3xl bg-surface p-4 shadow-card">
      {src ? (
        <img src={src} alt={label} className="h-full w-full" />
      ) : (
        <span className="h-full w-full animate-pulse rounded-2xl bg-ink-100" />
      )}
    </div>
  )
}
