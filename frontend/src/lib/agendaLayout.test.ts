import { describe, expect, it } from 'vitest'
import { distribuiEmColunas } from './agendaLayout'

/**
 * O que a agenda precisa garantir: nada desenhado por cima de nada.
 *
 * O caso do relato (19/09/2026) é o primeiro bloco: sessões próximas que se
 * sobrepunham. A causa era a altura mínima de 30 minutos, corrigida no
 * WeekGrid; este módulo resolve a outra metade, que é a sobreposição de
 * verdade - duas sessões no mesmo horário.
 */

type Sessao = { nome: string; inicio: number; fim: number }

const faixa = (s: Sessao) => ({ inicio: s.inicio, fim: s.fim })

function layout(sessoes: Sessao[]) {
  return distribuiEmColunas(sessoes, faixa)
    .map((p) => `${p.item.nome}@${p.coluna}/${p.colunas}`)
    .sort()
}

describe('quem não se toca fica com a largura inteira', () => {
  it('sessões em sequência', () => {
    expect(
      layout([
        { nome: 'A', inicio: 540, fim: 550 },
        { nome: 'B', inicio: 550, fim: 560 },
        { nome: 'C', inicio: 600, fim: 630 },
      ]),
    ).toEqual(['A@0/1', 'B@0/1', 'C@0/1'])
  })

  it('encostar não é sobrepor: uma acaba onde a outra começa', () => {
    expect(
      layout([
        { nome: 'A', inicio: 540, fim: 555 },
        { nome: 'B', inicio: 555, fim: 570 },
      ]),
    ).toEqual(['A@0/1', 'B@0/1'])
  })

  it('lista vazia', () => {
    expect(distribuiEmColunas([], faixa)).toEqual([])
  })
})

describe('quem se sobrepõe divide a largura', () => {
  it('duas no mesmo horário ficam lado a lado', () => {
    expect(
      layout([
        { nome: 'A', inicio: 540, fim: 570 },
        { nome: 'B', inicio: 540, fim: 570 },
      ]),
    ).toEqual(['A@0/2', 'B@1/2'])
  })

  it('sobreposição parcial também divide', () => {
    expect(
      layout([
        { nome: 'A', inicio: 540, fim: 570 },
        { nome: 'B', inicio: 555, fim: 585 },
      ]),
    ).toEqual(['A@0/2', 'B@1/2'])
  })

  it('três ao mesmo tempo, três colunas', () => {
    expect(
      layout([
        { nome: 'A', inicio: 540, fim: 600 },
        { nome: 'B', inicio: 540, fim: 600 },
        { nome: 'C', inicio: 540, fim: 600 },
      ]),
    ).toEqual(['A@0/3', 'B@1/3', 'C@2/3'])
  })

  it('a coluna é reaproveitada quando a anterior já acabou', () => {
    // A e B começam juntas; B é mais longa, então fica na coluna 0 e A na 1.
    // C começa depois de A terminar (570 <= 580) e herda a coluna dela.
    expect(
      layout([
        { nome: 'A', inicio: 540, fim: 570 },
        { nome: 'B', inicio: 540, fim: 620 },
        { nome: 'C', inicio: 580, fim: 610 },
      ]),
    ).toEqual(['A@1/2', 'B@0/2', 'C@1/2'])
  })

  it('no empate de início, a mais longa fica à esquerda', () => {
    // A leitura desce da esquerda para a direita: a sessão que ocupa a sala
    // por mais tempo é a que ancora a coluna.
    expect(
      layout([
        { nome: 'curta', inicio: 540, fim: 550 },
        { nome: 'longa', inicio: 540, fim: 620 },
      ]),
    ).toEqual(['curta@1/2', 'longa@0/2'])
  })
})

describe('o grupo é a cadeia de quem se toca', () => {
  it('A-B e B-C colidem, e os três dividem — senão B não caberia', () => {
    expect(
      layout([
        { nome: 'A', inicio: 540, fim: 570 },
        { nome: 'B', inicio: 560, fim: 590 },
        { nome: 'C', inicio: 580, fim: 610 },
      ]),
    ).toEqual(['A@0/2', 'B@1/2', 'C@0/2'])
  })

  it('dois pares em horas diferentes não estreitam um ao outro', () => {
    // Sem separar os grupos, os quatro virariam 1/4 de largura cada e o dia
    // inteiro ficaria magro por causa de duas colisões isoladas.
    const r = distribuiEmColunas(
      [
        { nome: 'A', inicio: 540, fim: 570 },
        { nome: 'B', inicio: 540, fim: 570 },
        { nome: 'C', inicio: 720, fim: 750 },
        { nome: 'D', inicio: 720, fim: 750 },
      ],
      faixa,
    )
    for (const p of r) expect(p.colunas).toBe(2)
  })

  it('uma colisão não estreita quem vem sozinho depois', () => {
    const r = distribuiEmColunas(
      [
        { nome: 'A', inicio: 540, fim: 570 },
        { nome: 'B', inicio: 540, fim: 570 },
        { nome: 'C', inicio: 600, fim: 630 },
      ],
      faixa,
    )
    const c = r.find((p) => p.item.nome === 'C')!
    expect(c.colunas).toBe(1)
  })
})

describe('nada se sobrepõe no resultado', () => {
  it('em 200 sessões aleatórias, mesma coluna nunca colide no tempo', () => {
    const sessoes: Sessao[] = Array.from({ length: 200 }, (_, i) => {
      const inicio = 420 + Math.floor(Math.random() * 800)
      return { nome: `s${i}`, inicio, fim: inicio + 5 + Math.floor(Math.random() * 90) }
    })

    const r = distribuiEmColunas(sessoes, faixa)

    for (const a of r) {
      for (const b of r) {
        if (a === b || a.coluna !== b.coluna) continue
        const colide = a.item.inicio < b.item.fim && b.item.inicio < a.item.fim
        expect(colide, `${a.item.nome} e ${b.item.nome} na coluna ${a.coluna}`).toBe(false)
      }
    }
  })

  it('e a coluna nunca passa do total do grupo', () => {
    const sessoes: Sessao[] = Array.from({ length: 100 }, (_, i) => {
      const inicio = 420 + Math.floor(Math.random() * 400)
      return { nome: `s${i}`, inicio, fim: inicio + 10 + Math.floor(Math.random() * 60) }
    })

    for (const p of distribuiEmColunas(sessoes, faixa)) {
      expect(p.coluna).toBeLessThan(p.colunas)
    }
  })
})
