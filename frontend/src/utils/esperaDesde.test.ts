import { describe, expect, it } from 'vitest'
import { esperaDemais, esperaDesde, LIMITE_DE_ESPERA_MINUTOS } from './esperaDesde'

/** 04/10/2026 15:00 em milissegundos, para as contas não dependerem do relógio. */
const AGORA = new Date('2026-10-04T15:00:00Z').getTime()
const minutosAtras = (m: number) => Math.floor((AGORA - m * 60_000) / 1000)

describe('esperaDesde', () => {
  it('conta em minutos abaixo de uma hora', () => {
    expect(esperaDesde(minutosAtras(1), AGORA)).toBe('1 min')
    expect(esperaDesde(minutosAtras(42), AGORA)).toBe('42 min')
    expect(esperaDesde(minutosAtras(59), AGORA)).toBe('59 min')
  })

  it('vira horas na virada, sem casa decimal', () => {
    expect(esperaDesde(minutosAtras(60), AGORA)).toBe('1h')
    expect(esperaDesde(minutosAtras(199), AGORA)).toBe('3h')
    expect(esperaDesde(minutosAtras(60 * 23), AGORA)).toBe('23h')
  })

  it('vira dias, e o singular não sai como "1 dias"', () => {
    expect(esperaDesde(minutosAtras(60 * 24), AGORA)).toBe('1 dia')
    expect(esperaDesde(minutosAtras(60 * 50), AGORA)).toBe('2 dias')
  })

  it('não mostra nada sem data', () => {
    // Conversa entregue antes desta mudança não tem o campo. Texto vazio faz a
    // tela esconder o selo, em vez de mostrar "NaN min".
    expect(esperaDesde(null, AGORA)).toBe('')
    expect(esperaDesde(undefined, AGORA)).toBe('')
    expect(esperaDesde(0, AGORA)).toBe('')
  })

  it('relógio do servidor adiantado não produz tempo negativo', () => {
    // O epoch vem do servidor e o "agora" do navegador; eles divergem em
    // segundos. "-2 min" na tela pareceria defeito.
    expect(esperaDesde(minutosAtras(-5), AGORA)).toBe('agora mesmo')
  })

  it('espera em segundos, nunca em milissegundos', () => {
    // Passar milissegundos aqui daria uma data no ano 57000 e "agora mesmo"
    // para tudo, calado - a fila inteira pareceria recém-criada.
    expect(esperaDesde(AGORA, AGORA)).toBe('agora mesmo')
    expect(esperaDesde(Math.floor(AGORA / 1000) - 7200, AGORA)).toBe('2h')
  })
})

describe('esperaDemais', () => {
  it('uma hora é o corte', () => {
    expect(esperaDemais(minutosAtras(LIMITE_DE_ESPERA_MINUTOS - 1), AGORA)).toBe(false)
    expect(esperaDemais(minutosAtras(LIMITE_DE_ESPERA_MINUTOS), AGORA)).toBe(true)
  })

  it('sem data, não está atrasada', () => {
    // Conversa antiga sem o campo não pode acender o alerta vermelho da fila
    // inteira: alarme que soa sempre a recepção aprende a ignorar.
    expect(esperaDemais(null, AGORA)).toBe(false)
    expect(esperaDemais(undefined, AGORA)).toBe(false)
  })
})
