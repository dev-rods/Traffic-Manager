import { describe, expect, it } from 'vitest'
import { isDefaultDomain } from './domain'

describe('isDefaultDomain', () => {
  it('reconhece localhost e 127.0.0.1', () => {
    expect(isDefaultDomain('localhost')).toBe(true)
    expect(isDefaultDomain('127.0.0.1')).toBe(true)
  })

  it('reconhece qualquer subdomínio *.vercel.app', () => {
    expect(isDefaultDomain('booking-site-neon.vercel.app')).toBe(true)
    expect(isDefaultDomain('booking-site-dev.vercel.app')).toBe(true)
  })

  it('não reconhece um domínio próprio de clínica', () => {
    expect(isDefaultDomain('agendar.suaempresa.com')).toBe(false)
    expect(isDefaultDomain('suaempresa.com.br')).toBe(false)
  })

  it('não deixa um domínio terminado em vercel.app sem ser subdomínio enganar', () => {
    expect(isDefaultDomain('totallyvercel.app')).toBe(false)
  })
})
