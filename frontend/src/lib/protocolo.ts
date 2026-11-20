import type { AplicacaoDeSessao, MetodoLaser, ParametroDoProtocolo, SkinType } from '@/types'

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

/**
 * Os três métodos, na ordem em que o material os apresenta.
 *
 * A profissional pode escolher QUALQUER um em QUALQUER área. O protocolo diz
 * qual começar, não qual é permitido - decisão do André em 19/09/2026, depois
 * de não conseguir escolher Stacking numa axila, que no material só tem SHR e
 * HR. Área sem sugestão continua editável; ela informa o que usou.
 */
export const TODOS_OS_METODOS: MetodoLaser[] = ['SHR', 'SHR_STACKING', 'HR']

/**
 * Áreas que a tela sempre sugere ao registrar a sessão, fora do catálogo.
 *
 * "Grandes lábios" não é vendida — não pode ser área da clínica, senão
 * aparece no agendamento e no site. Mas é aplicada com parâmetro próprio (mais
 * baixo que o da virilha), e o protocolo já tem a linha dela. Entrar como texto
 * livre perderia a sugestão e espalharia grafias diferentes pelo histórico.
 * Ver PRD 030; chamava-se "Interno de Virilha" até o PRD 052.
 */
export const AREAS_PADRAO: readonly { nome: string; protocol_area_key: string }[] = [
  { nome: 'Grandes lábios', protocol_area_key: 'interno_virilha' },
]

/**
 * Energia do HR: 1,0 kJ do início ao fim do tratamento (PDF). Ao escolher HR a
 * tela pré-preenche com isto SEMPRE, mesmo sem pele ou sem linha para a área;
 * o campo segue editável e o backend não força (decisão do André, 19/11/2026).
 */
export const ENERGIA_DO_HR = 1

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

/**
 * Com o que uma linha começa ao receber um método: a sugestão do protocolo e,
 * no HR, a energia fixa. É a única porta para isso (PRD 052): escolher o
 * método, adicionar área e adicionar método passam todos por aqui.
 */
export function parametrosIniciais(
  parametros: ParametroDoProtocolo[],
  protocolAreaKey: string | null,
  metodo: MetodoLaser | null,
  skinType: SkinType | null,
): Pick<AplicacaoDeSessao, 'fluence_j' | 'energy_kj' | 'stacks' | 'passes'> {
  const s = sugestao(parametros, protocolAreaKey, metodo, skinType)
  return {
    fluence_j: s?.fluence_j ?? null,
    energy_kj: metodo === 'HR' ? (s?.energy_kj ?? ENERGIA_DO_HR) : (s?.energy_kj ?? null),
    stacks: s?.stacks ?? null,
    passes: s?.passes ?? null,
  }
}

/**
 * Os métodos para os quais o protocolo TEM sugestão nesta área.
 *
 * Não é a lista do que ela pode escolher - isso é TODOS_OS_METODOS. Serve para
 * dois usos: pré-selecionar quando há exatamente um, e marcar na tela os que
 * vão entrar sem parâmetro preenchido.
 */
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
