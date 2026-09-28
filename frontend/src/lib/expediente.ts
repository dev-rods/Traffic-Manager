import { timeToMinutes } from '@/utils/dateHelpers'
import type { Appointment, AvailabilityRule } from '@/types'

/**
 * A janela que a GRADE desenha - o eixo vertical do desktop, fixo.
 *
 * Mora aqui, e não em cada tela, porque a grade e a lista do celular precisam
 * concordar. Não confundir com o horário de funcionamento: para dizer até que
 * horas a clínica atende, use `janelaDoDia`.
 */
export const PRIMEIRA_HORA = 7
export const ULTIMA_HORA = 22

/** Granularidade visual da grade do desktop: as linhas de :15, :30 e :45. */
export const MINUTOS_DO_SLOT = 15

/**
 * O menor vão que vale mostrar.
 *
 * NÃO é `MINUTOS_DO_SLOT`. Confundir os dois foi o defeito: a grade se divide
 * de 15 em 15 minutos, mas a clínica marca sessão de duração livre, e um piso
 * de 15 escondia buraco onde cabe atendimento.
 *
 * Medido na Essência, sobre os atendimentos reais:
 *
 *      5 min ...  13 atendimentos
 *     10 min ...  34
 *     12 min ...   2
 *     15 min ... 454
 *
 * Cinco minutos é a menor sessão que a clínica de fato marca, então é o menor
 * vão que representa horário aproveitável. Abaixo disso não há o que caiba -
 * seria ruído entre duas linhas.
 */
export const MENOR_VAO = 5

export interface Vao {
  /** Minutos desde a meia-noite. */
  inicio: number
  fim: number
}

/**
 * O horário em que a clínica realmente atende naquele dia.
 *
 * Sai das MESMAS regras que fazem o dia aparecer na agenda. A `AgendaPage`
 * monta a lista de dias a partir das regras com `rule_date` preenchido; usar
 * outra fonte aqui poderia mostrar um dia cuja janela viesse de outro lugar.
 *
 * Só regras de data específica, de propósito. É também o que o servidor faz:
 * em `availability_engine`, `fixed_rules` substituem as recorrentes quando
 * existem para a data. Como a agenda só exibe dias que têm regra fixa, seguir
 * apenas elas reproduz a prioridade do servidor por construção, sem copiar a
 * resolução de `day_of_week` - que tem a sutileza de 0=domingo e já aparece
 * duplicada duas vezes no backend.
 *
 * Várias regras no mesmo dia são vários profissionais. A janela é a união:
 * a agenda mostra todos, então ela abre com o primeiro e fecha com o último.
 *
 * Sem regra para o dia, devolve `null` - e quem chama decide. Não inventa um
 * horário: dizer "livre até 22:00" numa clínica que fecha às 19h é pior do que
 * não dizer nada.
 */
export function janelaDoDia(
  rules: AvailabilityRule[],
  dia: string,
): { inicio: number; fim: number } | null {
  const doDia = rules.filter((r) => r.active && r.rule_date === dia)
  if (doDia.length === 0) return null

  const inicio = Math.min(...doDia.map((r) => timeToMinutes(r.start_time)))
  const fim = Math.max(...doDia.map((r) => timeToMinutes(r.end_time)))

  return fim > inicio ? { inicio, fim } : null
}

/**
 * Os buracos livres de um dia, em ordem.
 *
 * Quem olha a agenda no celular quer saber quando cabe alguém. A lista de
 * atendimentos responde "o que tem marcado"; sem os vãos, descobrir que das
 * 10h às 14h não há nada exige subtrair horários de cabeça, linha a linha.
 *
 * Duas decisões que o caso simples esconde:
 *
 * O cursor anda com o MAIOR fim visto até agora, não com o fim do atendimento
 * anterior. Dois atendimentos simultâneos existem (a grade do desktop tem
 * `distribuiEmColunas` justamente para isso), e um contido dentro do outro -
 * 14h-15h e 14h30-14h45 - abriria um vão fantasma das 14h45 às 15h se o cursor
 * seguisse o último da lista.
 *
 * Atendimento que começa antes da janela, ou termina depois, empurra o cursor
 * do mesmo jeito. O que ele ocupa não está livre só porque cai fora do que a
 * tela desenha.
 */
export function vaosLivres(
  appointments: Appointment[],
  { inicio, fim, minimo = MENOR_VAO }: { inicio: number; fim: number; minimo?: number },
): Vao[] {
  const ocupados = appointments
    .filter((a) => a.status !== 'CANCELLED')
    .map((a) => ({ inicio: timeToMinutes(a.start_time), fim: timeToMinutes(a.end_time) }))
    .sort((a, b) => a.inicio - b.inicio)

  const vaos: Vao[] = []
  let cursor = inicio

  for (const o of ocupados) {
    // O vão termina no atendimento OU no fechamento, o que vier primeiro. Um
    // encaixe às 19h30 numa clínica que fecha às 19h faria o vão anterior ir
    // até 19h30 - oferecendo meia hora depois de a clínica ter fechado.
    const fimDoVao = Math.min(o.inicio, fim)
    if (fimDoVao - cursor >= minimo) {
      vaos.push({ inicio: cursor, fim: fimDoVao })
    }
    cursor = Math.max(cursor, o.fim)
  }

  if (fim - cursor >= minimo) {
    vaos.push({ inicio: cursor, fim })
  }

  return vaos
}

/** "07:00", a partir de minutos desde a meia-noite. */
export function comoHora(minutos: number): string {
  const h = Math.floor(minutos / 60)
  const m = minutos % 60
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

/** "1h30", "45 min", "2h" - o tamanho do vão, dito como se fala. */
export function duracaoPorExtenso(minutos: number): string {
  const h = Math.floor(minutos / 60)
  const m = minutos % 60
  if (h === 0) return `${m} min`
  if (m === 0) return `${h}h`
  return `${h}h${String(m).padStart(2, '0')}`
}
