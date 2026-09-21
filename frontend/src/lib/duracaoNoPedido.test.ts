import { describe, it, expect } from 'vitest'
import { precisaMandarDuracao } from './duracaoNoPedido'

/**
 * O caso que o André relatou em 21/09/2026, passo a passo.
 *
 * Ele fixou a duração, salvou, depois removeu uma área, redigitou o MESMO
 * número - e o sistema passou a recusar por conflito. A tela mostrava 10 e o
 * servidor gravava a duração recalculada.
 */
describe('precisaMandarDuracao', () => {
  it('o caso relatado: mesma duração, mas a área mudou', () => {
    // A sessão tinha 10 min fixados. Ela removeu uma área e redigitou 10.
    expect(
      precisaMandarDuracao({
        manualNaTela: 10,
        manualNoServidor: 10,
        mudouAreaOuServico: true,
      }),
    ).toBe(true)
  })

  it('sem mexer na área, valor igual não precisa viajar', () => {
    // Aqui o servidor não vai descartar nada, então calar é seguro - e evita
    // uma escrita à toa.
    expect(
      precisaMandarDuracao({
        manualNaTela: 10,
        manualNoServidor: 10,
        mudouAreaOuServico: false,
      }),
    ).toBe(false)
  })

  it('valor diferente sempre viaja', () => {
    for (const mudouAreaOuServico of [true, false]) {
      expect(
        precisaMandarDuracao({
          manualNaTela: 25,
          manualNoServidor: 10,
          mudouAreaOuServico,
        }),
      ).toBe(true)
    }
  })

  it('soltar o override viaja: `null` é o que manda voltar ao cálculo', () => {
    expect(
      precisaMandarDuracao({
        manualNaTela: null,
        manualNoServidor: 10,
        mudouAreaOuServico: false,
      }),
    ).toBe(true)
  })

  it('fixar pela primeira vez viaja', () => {
    expect(
      precisaMandarDuracao({
        manualNaTela: 30,
        manualNoServidor: null,
        mudouAreaOuServico: false,
      }),
    ).toBe(true)
  })

  it('sem override dos dois lados, trocar a área não inventa um pedido', () => {
    // Mandar `null` aqui seria pedir para soltar o que não existe. A troca de
    // área sozinha já basta, e o servidor calcula.
    expect(
      precisaMandarDuracao({
        manualNaTela: null,
        manualNoServidor: null,
        mudouAreaOuServico: true,
      }),
    ).toBe(false)
  })

  it('a paciente que some o override AO trocar a área continua sendo atendida', () => {
    // Tinha 75 fixados, removeu área e deixou o campo no automático: isso é um
    // pedido explícito de soltar, e precisa viajar.
    expect(
      precisaMandarDuracao({
        manualNaTela: null,
        manualNoServidor: 75,
        mudouAreaOuServico: true,
      }),
    ).toBe(true)
  })
})
