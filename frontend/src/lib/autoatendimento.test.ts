import { describe, expect, it } from 'vitest'
import { linkDeMeusAgendamentos, linkDoSite } from './autoatendimento'

describe('autoatendimento (PRD 060)', () => {
  it('a raiz do domínio é o link para marcar', () => {
    expect(linkDoSite('agendar.x.com.br')).toBe('https://agendar.x.com.br/')
    expect(linkDoSite('https://agendar.x.com.br/')).toBe('https://agendar.x.com.br/')
  })

  it('?meus=1 abre "Meus agendamentos" direto', () => {
    expect(linkDeMeusAgendamentos('agendar.x.com.br')).toBe('https://agendar.x.com.br/?meus=1')
  })

  it('sem domínio não há link', () => {
    expect(linkDoSite(null)).toBeNull()
    expect(linkDoSite('  ')).toBeNull()
    expect(linkDeMeusAgendamentos(undefined)).toBeNull()
  })
})
