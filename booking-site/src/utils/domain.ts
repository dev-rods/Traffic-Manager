// Domínios onde o clinicId SEMPRE vem do path (/:clinicId): o próprio deploy
// da Vercel e ambiente local de dev. Qualquer outro host é domínio próprio de
// alguma clínica (ver CustomDomainField no painel) e o clinicId é resolvido
// pelo hostname via /public/resolve-domain.
export function isDefaultDomain(hostname: string): boolean {
  return (
    hostname === 'localhost' ||
    hostname === '127.0.0.1' ||
    hostname.endsWith('.vercel.app')
  )
}
