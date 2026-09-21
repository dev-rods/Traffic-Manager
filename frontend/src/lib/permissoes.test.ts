import { describe, it, expect } from 'vitest'
import { podeVer, rotaInicial, ROTAS_DO_STAFF } from './permissoes'

/**
 * Esta lista não é segurança - o servidor é quem nega, e nega por padrão. O que
 * ela evita é oferecer ao funcionário uma tela que responderia 403.
 *
 * O teste existe porque a falha aqui é silenciosa: um item novo no menu que
 * ninguém lembrou de filtrar não quebra nada, só leva a recepção a uma tela de
 * erro sem explicação.
 */
describe('podeVer', () => {
  it('o admin alcança tudo', () => {
    for (const rota of ['/dashboard', '/relatorios', '/usuarios', '/configuracoes', '/bot']) {
      expect(podeVer('ADMIN', rota)).toBe(true)
    }
  })

  it('o funcionário alcança agenda e pacientes', () => {
    expect(podeVer('STAFF', '/agenda')).toBe(true)
    expect(podeVer('STAFF', '/pacientes')).toBe(true)
  })

  it('o prontuário entra junto com pacientes', () => {
    // É rota filha: /pacientes/:id/documentos. Sem o casamento por prefixo, a
    // funcionária abriria a lista e não conseguiria registrar a sessão.
    expect(podeVer('STAFF', '/pacientes/abc-123/documentos')).toBe(true)
  })

  it('os três itens que o André nomeou ficam de fora', () => {
    expect(podeVer('STAFF', '/relatorios')).toBe(false)   // financeiro
    expect(podeVer('STAFF', '/configuracoes')).toBe(false) // configuração
    expect(podeVer('STAFF', '/bot')).toBe(false)           // whatsapp
  })

  it('e o resto do que não pode vazar junto', () => {
    for (const rota of ['/dashboard', '/leads', '/faq', '/descontos', '/duracao',
                        '/servicos', '/areas', '/servicos-areas', '/horarios',
                        '/usuarios']) {
      expect(podeVer('STAFF', rota), rota).toBe(false)
    }
  })

  it('prefixo parecido não abre a porta', () => {
    // `/agenda-financeira` começa com `/agenda` como texto, mas não é rota
    // filha. Um `startsWith` cru liberaria.
    expect(podeVer('STAFF', '/agendamentos-relatorio')).toBe(false)
    expect(podeVer('STAFF', '/pacientes-export')).toBe(false)
  })
})

describe('rotaInicial', () => {
  it('o admin começa no dashboard', () => {
    expect(rotaInicial('ADMIN')).toBe('/dashboard')
  })

  it('o funcionário começa na agenda, porque não tem dashboard', () => {
    expect(rotaInicial('STAFF')).toBe('/agenda')
  })

  it('a rota inicial do funcionário é uma que ele alcança', () => {
    // Senão o login jogaria a pessoa num laço de redirecionamento.
    expect(podeVer('STAFF', rotaInicial('STAFF'))).toBe(true)
    expect(ROTAS_DO_STAFF).toContain(rotaInicial('STAFF'))
  })
})
