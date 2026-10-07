import { describe, it, expect } from 'vitest'
import { podeVer, rotaInicial, ROTAS_DO_STAFF } from './permissoes'
import type { AcessoDoUsuario } from './permissoes'

/**
 * Esta lista não é segurança - o servidor é quem nega, e nega por padrão. O que
 * ela evita é oferecer ao funcionário uma tela que responderia 403.
 *
 * O teste existe porque a falha aqui é silenciosa: um item novo no menu que
 * ninguém lembrou de filtrar não quebra nada, só leva a recepção a uma tela de
 * erro sem explicação.
 */

const ADMIN: AcessoDoUsuario = {
  papel: 'ADMIN',
  permissoes: { see_prices: true, see_patient_list: true },
}

const RECEPCAO: AcessoDoUsuario = {
  papel: 'STAFF',
  permissoes: { see_prices: false, see_patient_list: true },
}

const SEM_LISTA: AcessoDoUsuario = {
  papel: 'STAFF',
  permissoes: { see_prices: false, see_patient_list: false },
}

describe('podeVer', () => {
  it('o admin alcança tudo', () => {
    for (const rota of ['/dashboard', '/relatorios', '/usuarios', '/configuracoes', '/bot']) {
      expect(podeVer(ADMIN, rota)).toBe(true)
    }
  })

  it('o funcionário alcança agenda e pacientes', () => {
    expect(podeVer(RECEPCAO, '/agenda')).toBe(true)
    expect(podeVer(RECEPCAO, '/pacientes')).toBe(true)
  })

  it('o prontuário entra junto com pacientes', () => {
    // É rota filha: /pacientes/:id/documentos. Sem o casamento por prefixo, a
    // funcionária abriria a lista e não conseguiria registrar a sessão.
    expect(podeVer(RECEPCAO, '/pacientes/abc-123/documentos')).toBe(true)
  })

  it('os três itens que o André nomeou ficam de fora', () => {
    expect(podeVer(RECEPCAO, '/relatorios')).toBe(false)   // financeiro
    expect(podeVer(RECEPCAO, '/configuracoes')).toBe(false) // configuração
    expect(podeVer(RECEPCAO, '/bot')).toBe(false)           // whatsapp
  })

  it('e o resto do que não pode vazar junto', () => {
    for (const rota of ['/dashboard', '/leads', '/faq', '/descontos', '/duracao',
                        '/servicos', '/areas', '/servicos-areas', '/horarios',
                        '/usuarios']) {
      expect(podeVer(RECEPCAO, rota), rota).toBe(false)
    }
  })

  it('prefixo parecido não abre a porta', () => {
    // `/agendamentos-relatorio` começa com `/agenda` como texto, mas não é
    // rota filha. Um `startsWith` cru liberaria.
    expect(podeVer(RECEPCAO, '/agendamentos-relatorio')).toBe(false)
    expect(podeVer(RECEPCAO, '/pacientes-export')).toBe(false)
  })
})

describe('o interruptor da lista de pacientes', () => {
  it('desligado, a lista some', () => {
    expect(podeVer(SEM_LISTA, '/pacientes')).toBe(false)
  })

  it('mas o PRONTUÁRIO continua aberto', () => {
    // Ela chega nele pelo atalho da agenda, e precisa dele para registrar a
    // sessão. Fechar a rota filha junto com a lista trancaria a funcionária
    // fora do proprio trabalho - e o erro so apareceria no fim do atendimento.
    expect(podeVer(SEM_LISTA, '/pacientes/abc-123/documentos')).toBe(true)
  })

  it('e a agenda não é afetada', () => {
    expect(podeVer(SEM_LISTA, '/agenda')).toBe(true)
  })

  it('o interruptor não vale para o admin', () => {
    const adminSemLista: AcessoDoUsuario = {
      papel: 'ADMIN',
      permissoes: { see_prices: false, see_patient_list: false },
    }

    expect(podeVer(adminSemLista, '/pacientes')).toBe(true)
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
    // Senão o login jogaria a pessoa num laço de redirecionamento - inclusive
    // com a lista de pacientes desligada.
    expect(podeVer(RECEPCAO, rotaInicial('STAFF'))).toBe(true)
    expect(podeVer(SEM_LISTA, rotaInicial('STAFF'))).toBe(true)
    expect(ROTAS_DO_STAFF).toContain(rotaInicial('STAFF'))
  })
})
