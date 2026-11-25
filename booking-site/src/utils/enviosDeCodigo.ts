/** Quanto tempo um código recém-enviado vale como "já mandei": nem a montagem
 * automática do formulário nem o "Reenviar" mandam outro antes disso. */
export const ESPERA_REENVIO_MS = 30_000

// Último envio por clínica+celular, fora de qualquer componente: sobrevive a
// toda remontagem do formulário (StrictMode, troca de etapa e volta, re-render
// do pai), que em 24/11 mandou dois códigos seguidos para a mesma pessoa.
const ultimoEnvio = new Map<string, number>()

function chave(clinicId: string, phone: string) {
  return `${clinicId}|${phone}`
}

export function registraEnvioDeCodigo(clinicId: string, phone: string, agora = Date.now()) {
  ultimoEnvio.set(chave(clinicId, phone), agora)
}

/** Segundos até poder mandar outro código para este celular (0 = pode agora). */
export function segundosAteReenviar(clinicId: string, phone: string, agora = Date.now()): number {
  const em = ultimoEnvio.get(chave(clinicId, phone))
  if (em === undefined) return 0
  return Math.max(0, Math.ceil((em + ESPERA_REENVIO_MS - agora) / 1000))
}

/** Só para testes: esquece os envios recentes. */
export function limpaEnviosRecentes() {
  ultimoEnvio.clear()
}
