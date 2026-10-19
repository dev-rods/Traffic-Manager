import { describe, expect, it } from 'vitest'
import { descreveFalha } from './useMessages'

describe('descreveFalha', () => {
  it('traduz o motivo do 409 para a recepção', () => {
    const err = { response: { data: { status: 'ERROR', motivo: 'janela_de_silencio' } } }
    expect(descreveFalha(err)).toBe('fora do horário de atendimento')
  })

  it('motivo desconhecido sai como veio, para não esconder', () => {
    expect(descreveFalha({ response: { data: { motivo: 'xyz' } } })).toBe('xyz')
  })

  it('sem motivo, usa a mensagem do backend', () => {
    expect(descreveFalha({ response: { data: { message: 'Clinica nao encontrada' } } })).toBe(
      'Clinica nao encontrada'
    )
  })

  it('erro de rede usa a mensagem do Error', () => {
    expect(descreveFalha(new Error('Network Error'))).toBe('Network Error')
  })
})
