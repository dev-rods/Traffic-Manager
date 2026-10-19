import { describe, expect, it } from 'vitest'
import { aplicaDatas, mensagemDoDisparo, MENSAGEM_PADRAO } from './buildDefaultMessage'

describe('mensagemDoDisparo', () => {
  it('sem texto da clínica, usa o padrão com as datas MARCADAS', () => {
    const texto = mensagemDoDisparo(null, ['2026-10-21', '2026-10-28'])
    expect(texto).toContain('*21/10, 28/10*')
    expect(texto).not.toContain('{datas}')
  })

  it('texto da clínica com {datas} recebe as datas no lugar do marcador', () => {
    const texto = mensagemDoDisparo('Oi {nome}, temos {datas}. Vem?', ['2026-11-03'])
    expect(texto).toBe('Oi {nome}, temos 03/11. Vem?')
  })

  it('texto da clínica sem marcador sai como foi escrito', () => {
    expect(mensagemDoDisparo('Oi {nome}, bora agendar?', ['2026-11-03'])).toBe(
      'Oi {nome}, bora agendar?'
    )
  })

  it('texto da clínica só com espaços conta como vazio', () => {
    expect(mensagemDoDisparo('   ', [])).toBe(aplicaDatas(MENSAGEM_PADRAO, []))
  })

  it('sem data marcada diz "em breve" em vez de deixar o marcador', () => {
    expect(mensagemDoDisparo(null, [])).toContain('*em breve*')
  })
})
