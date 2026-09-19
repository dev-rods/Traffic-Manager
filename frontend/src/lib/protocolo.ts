import type { MetodoLaser, ParametroDoProtocolo, SkinType } from '@/types'

/**
 * Quais campos cada método do laser usa.
 *
 * Espelha METODOS em scheduler/src/services/protocolo_laser.py. Os dois
 * precisam concordar: divergindo, a tela desenha um campo que o backend
 * descarta, e a profissional digita um parâmetro que não é gravado.
 *
 * Os rótulos são os dos PDFs da clínica — `Fluência (J)`, `Energia (kJ)`. É o
 * que ela lê no material dela, e prontuário não é lugar de inventar unidade.
 */
export const CAMPOS_POR_METODO: Record<MetodoLaser, readonly string[]> = {
  SHR: ['fluence_j', 'energy_kj'],
  SHR_STACKING: ['fluence_j', 'stacks', 'passes'],
  HR: ['fluence_j', 'energy_kj'],
} as const

export const ROTULO_DO_METODO: Record<MetodoLaser, string> = {
  SHR: 'SHR',
  SHR_STACKING: 'SHR Stacking',
  HR: 'HR',
}

export const ROTULO_DO_CAMPO: Record<string, string> = {
  fluence_j: 'Fluência (J)',
  energy_kj: 'Energia (kJ)',
  stacks: 'Stacks',
  passes: 'Passadas',
}

/** Stacks são lidos como bolinhas no material: 3 stacks = ●●●. */
export function bolinhas(stacks: number | null): string {
  if (!stacks || stacks < 1) return ''
  return '●'.repeat(stacks)
}

export function usaCampo(metodo: MetodoLaser | null, campo: string): boolean {
  if (!metodo) return false
  return CAMPOS_POR_METODO[metodo]?.includes(campo) ?? false
}

/**
 * O parâmetro inicial desta área, neste método, nesta pele.
 *
 * `null` quando não há linha — e isso é resposta VÁLIDA: a tela mostra "sem
 * parâmetro sugerido" e a profissional digita. Nunca cai em outro tipo de pele
 * nem em outro método: sugerir a fluência de outra área é o erro que o módulo
 * do backend inteiro existe para não cometer, e a tela não pode reintroduzi-lo.
 */
export function sugestao(
  parametros: ParametroDoProtocolo[],
  protocolAreaKey: string | null,
  metodo: MetodoLaser | null,
  skinType: SkinType | null,
): ParametroDoProtocolo | null {
  if (!protocolAreaKey || !metodo || !skinType) return null
  return (
    parametros.find(
      (p) =>
        p.protocol_area_key === protocolAreaKey &&
        p.method === metodo &&
        p.skin_type === skinType,
    ) ?? null
  )
}

/** Os métodos que o protocolo tem para esta área, na ordem de CAMPOS_POR_METODO. */
export function metodosDaArea(
  parametros: ParametroDoProtocolo[],
  protocolAreaKey: string | null,
): MetodoLaser[] {
  if (!protocolAreaKey) return []
  const ordem = Object.keys(CAMPOS_POR_METODO) as MetodoLaser[]
  return ordem.filter((m) =>
    parametros.some((p) => p.protocol_area_key === protocolAreaKey && p.method === m),
  )
}

/** Textos dos documentos, palavra por palavra. Ver protocolo_laser.py. */
export const AVISO_BRONZEADA =
  'Pele bronzeada: reduza a fluência. No SHR Stacking, reduza também os stacks ' +
  'e/ou as passadas. Nunca utilize o método HR, independentemente do fototipo.'
export const AVISO_HR_PELE_NEGRA =
  'Utilize somente nas tonalidades mais claras de pele negra, fototipos IV e V, ' +
  'após avaliação criteriosa. Não utilize o método HR no fototipo VI.'
export const AVISO_HR_GERAL =
  'É um método mais agressivo, mais eficiente e mais dolorido, com maior risco ' +
  'de queimaduras.'

export function avisos(
  metodo: MetodoLaser | null,
  skinType: SkinType | null,
  bronzeada: boolean,
): string[] {
  const saida: string[] = []
  if (bronzeada) saida.push(AVISO_BRONZEADA)
  if (metodo === 'HR') {
    saida.push(AVISO_HR_GERAL)
    if (skinType === 'NEGRA') saida.push(AVISO_HR_PELE_NEGRA)
  }
  return saida
}

/**
 * O HR sai das sugestões em pele bronzeada — o documento é categórico.
 *
 * Sair da sugestão não é bloquear: quem decide conduta é quem aplica, e
 * software que impede acaba contornado por fora, sem registro nenhum.
 */
export function hrDesaconselhado(bronzeada: boolean): boolean {
  return bronzeada
}
