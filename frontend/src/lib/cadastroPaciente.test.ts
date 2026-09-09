import { describe, it, expect } from 'vitest'
import { z } from 'zod'
import { cadastroSchema, formataCpf } from './cadastroPaciente'

const schema = z.object(cadastroSchema)

describe('formataCpf', () => {
  it('formata quando está completo', () => {
    expect(formataCpf('07903984519')).toBe('079.039.845-19')
  })

  it('deixa incompleto como está, sem pontuação pela metade', () => {
    expect(formataCpf('0790398')).toBe('0790398')
  })

  it('ignora o que já vem pontuado', () => {
    expect(formataCpf('079.039.845-19')).toBe('079.039.845-19')
  })

  it('corta o que passa de 11 dígitos', () => {
    expect(formataCpf('079039845199999')).toBe('079.039.845-19')
  })
})

describe('cadastroSchema', () => {
  // Opcionais porque o cadastro completo raramente existe no primeiro contato.
  it('aceita tudo vazio', () => {
    expect(schema.safeParse({}).success).toBe(true)
    expect(schema.safeParse({ cpf: '', birth_date: '', email: '' }).success).toBe(true)
  })

  it('aceita CPF com e sem pontuação', () => {
    for (const cpf of ['07903984519', '079.039.845-19']) {
      expect(schema.safeParse({ cpf }).success).toBe(true)
    }
  })

  it('recusa CPF com tamanho errado', () => {
    for (const cpf of ['123', '0790398451', '079039845199']) {
      expect(schema.safeParse({ cpf }).success).toBe(false)
    }
  })

  // Decisão consciente, igual à do backend: recusar um CPF ditado errado no
  // WhatsApp travaria o agendamento por algo que a recepção corrige depois.
  it('não valida dígito verificador', () => {
    expect(schema.safeParse({ cpf: '11111111111' }).success).toBe(true)
  })

  it('recusa e-mail malformado', () => {
    expect(schema.safeParse({ email: 'nao-e-email' }).success).toBe(false)
    expect(schema.safeParse({ email: 'a@b.co' }).success).toBe(true)
  })
})
