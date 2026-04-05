import { useEffect } from 'react'

/**
 * Sets dynamic favicon (SVG with clinic initial) and page title.
 */
export function useBranding(clinicName: string | undefined) {
  useEffect(() => {
    if (!clinicName) return

    // Dynamic title
    document.title = `${clinicName} — Painel`

    // Dynamic SVG favicon with clinic initial
    const initial = clinicName[0]?.toUpperCase() ?? 'C'
    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
      <rect width="32" height="32" rx="8" fill="#3b6cf0"/>
      <text x="16" y="23" font-family="DM Sans,system-ui,sans-serif" font-size="18" font-weight="700" fill="#fff" text-anchor="middle">${initial}</text>
    </svg>`

    const blob = new Blob([svg], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)

    let link = document.querySelector<HTMLLinkElement>('link[rel="icon"]')
    if (!link) {
      link = document.createElement('link')
      link.rel = 'icon'
      document.head.appendChild(link)
    }
    link.type = 'image/svg+xml'
    link.href = url

    return () => URL.revokeObjectURL(url)
  }, [clinicName])
}
