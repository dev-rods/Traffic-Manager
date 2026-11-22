import { describe, expect, it } from 'vitest'
import { ESTAGIOS, ESTAGIOS_DA_AGENDA, ESTAGIOS_EDITAVEIS, ORDEM_DA_FILA, rotuloDaOrigem } from './estagios'

/**
 * Paridade com `estagio_do_lead.py` (PRD 057). O backend decide; esta lista so
 * evita oferecer no popover uma opcao que voltaria 400.
 */
describe('estagios', () => {
  it('a fila tem 9 e nao inclui NAO_E_LEAD', () => {
    expect(ORDEM_DA_FILA).toHaveLength(9)
    expect(ORDEM_DA_FILA).not.toContain('NAO_E_LEAD')
  })

  it('editaveis e agenda nao se cruzam e juntos cobrem os 10', () => {
    for (const s of ESTAGIOS_DA_AGENDA) expect(ESTAGIOS_EDITAVEIS).not.toContain(s)
    expect(new Set([...ESTAGIOS_EDITAVEIS, ...ESTAGIOS_DA_AGENDA]).size).toBe(10)
  })

  it('todo estagio tem rotulo', () => {
    expect(Object.keys(ESTAGIOS)).toHaveLength(10)
    for (const info of Object.values(ESTAGIOS)) expect(info.label.length).toBeGreaterThan(0)
  })

  it('origem desconhecida volta como veio', () => {
    expect(rotuloDaOrigem('landing-page')).toBe('Site')
    expect(rotuloDaOrigem('instagram')).toBe('instagram')
  })
})
