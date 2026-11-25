import { beforeEach, describe, expect, it } from 'vitest'
import {
  guardaSessaoVerificada,
  leSessaoVerificada,
  limpaSessaoVerificada,
  sessaoValeParaOCelular,
} from './sessaoVerificada'

describe('sessaoVerificada (PRD 061)', () => {
  beforeEach(() => limpaSessaoVerificada())

  it('guarda e lê o par celular+token com prazo de 29 min', () => {
    const agora = 1_700_000_000_000
    guardaSessaoVerificada('5511987654321', 'tok', agora)
    expect(leSessaoVerificada(agora)).toEqual({
      phone: '5511987654321',
      token: 'tok',
      expiraEm: agora + 29 * 60 * 1000,
    })
  })

  it('vencida não volta e é apagada', () => {
    const agora = 1_700_000_000_000
    guardaSessaoVerificada('5511987654321', 'tok', agora)
    expect(leSessaoVerificada(agora + 29 * 60 * 1000 + 1)).toBeNull()
    expect(leSessaoVerificada(agora)).toBeNull()
  })

  it('lixo no storage não quebra', () => {
    sessionStorage.setItem('booking:verificada', '{nope')
    expect(leSessaoVerificada()).toBeNull()
    sessionStorage.setItem('booking:verificada', JSON.stringify({ phone: 1 }))
    expect(leSessaoVerificada()).toBeNull()
  })

  it('vale só para o mesmo celular', () => {
    const agora = 1_700_000_000_000
    const sessao = guardaSessaoVerificada('5511987654321', 'tok', agora)
    expect(sessaoValeParaOCelular(sessao, '5511987654321', agora)).toBe(true)
    expect(sessaoValeParaOCelular(sessao, '5511900000000', agora)).toBe(false)
    expect(sessaoValeParaOCelular(null, '5511987654321', agora)).toBe(false)
    expect(sessaoValeParaOCelular(sessao, '5511987654321', sessao.expiraEm + 1)).toBe(false)
  })

  it('usa sessionStorage, nunca localStorage', () => {
    guardaSessaoVerificada('5511987654321', 'tok')
    expect(sessionStorage.getItem('booking:verificada')).not.toBeNull()
    expect(localStorage.getItem('booking:verificada')).toBeNull()
  })
})
