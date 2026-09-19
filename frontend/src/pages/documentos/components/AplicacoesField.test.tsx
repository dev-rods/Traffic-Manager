import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { AplicacaoDeSessao, ParametroDoProtocolo } from '@/types'
import { AplicacoesField } from './AplicacoesField'

/**
 * O protocolo diz qual método COMEÇAR, não qual é permitido.
 *
 * Em 19/09/2026 o André foi registrar uma sessão de axilas e só conseguiu
 * escolher SHR e HR, porque é o que o material traz para aquela área. Stacking
 * ficou de fora da lista - a tela tinha transformado "sem sugestão" em
 * "proibido".
 *
 * Quem decide conduta é quem aplica. A tela sugere e avisa; não impede.
 */

const P = (
  skin_type: 'BRANCA' | 'NEGRA',
  method: 'SHR' | 'SHR_STACKING' | 'HR',
  protocol_area_key: string,
  fluence_j: number,
  extra: Partial<ParametroDoProtocolo> = {},
): ParametroDoProtocolo => ({
  skin_type,
  method,
  protocol_area_key,
  protocol_area_name: protocol_area_key,
  fluence_j,
  energy_kj: null,
  stacks: null,
  passes: null,
  source: 'PDF',
  ...extra,
})

// Axilas tem SHR e HR no material, e NÃO tem Stacking. É o caso do relato.
const TABELA: ParametroDoProtocolo[] = [
  P('BRANCA', 'SHR', 'axilas', 7, { energy_kj: 8 }),
  P('BRANCA', 'HR', 'axilas', 17, { energy_kj: 1 }),
  P('BRANCA', 'SHR', 'lombar', 7, { energy_kj: 8 }),
]

const AXILAS: AplicacaoDeSessao = {
  area_id: 'a1',
  area_name: 'Axilas',
  protocol_area_key: 'axilas',
  method: null,
  fluence_j: null,
  energy_kj: null,
  stacks: null,
  passes: null,
  display_order: 0,
}

function monta(aplicacoes: AplicacaoDeSessao[], extra: Partial<Parameters<typeof AplicacoesField>[0]> = {}) {
  const onChange = vi.fn()
  render(
    <AplicacoesField
      aplicacoes={aplicacoes}
      onChange={onChange}
      parametros={TABELA}
      areas={[{ id: 'a1', clinic_id: 'c', name: 'Axilas', display_order: 0, active: true }]}
      mapaDeAreas={new Map([['a1', 'axilas']])}
      skinType="BRANCA"
      bronzeada={false}
      {...extra}
    />,
  )
  return onChange
}

describe('os três métodos estão sempre disponíveis', () => {
  it('axilas oferece Stacking, mesmo sem sugestão no material', () => {
    monta([AXILAS])

    const opcoes = screen.getAllByRole('option').map((o) => o.textContent)
    expect(opcoes.some((t) => t?.startsWith('SHR Stacking'))).toBe(true)
    expect(opcoes.some((t) => t?.startsWith('SHR') && !t.includes('Stacking'))).toBe(true)
    expect(opcoes.some((t) => t?.startsWith('HR'))).toBe(true)
  })

  it('e o que não tem sugestão é marcado, não escondido', () => {
    monta([AXILAS])

    const stacking = screen
      .getAllByRole('option')
      .find((o) => o.textContent?.startsWith('SHR Stacking'))
    expect(stacking?.textContent).toContain('sem sugestão para esta área')
  })

  it('nenhuma opção fica desabilitada', () => {
    monta([AXILAS])

    for (const o of screen.getAllByRole('option')) {
      expect(o).not.toBeDisabled()
    }
  })

  it('escolher um método sem sugestão deixa os campos prontos para digitar', async () => {
    const onChange = monta([AXILAS])

    await userEvent.selectOptions(screen.getByRole('combobox'), 'SHR_STACKING')

    // Método guardado, parâmetros vazios: ela informa o que usou.
    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({
        method: 'SHR_STACKING',
        fluence_j: null,
        stacks: null,
        passes: null,
      }),
    ])
  })

  it('escolher um método COM sugestão preenche do protocolo', async () => {
    const onChange = monta([AXILAS])

    await userEvent.selectOptions(screen.getByRole('combobox'), 'SHR')

    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ method: 'SHR', fluence_j: 7, energy_kj: 8 }),
    ])
  })
})

describe('área que o protocolo não conhece', () => {
  const LIVRE: AplicacaoDeSessao = { ...AXILAS, area_name: 'Área nova', protocol_area_key: null }

  it('continua editável — antes a tela não mostrava campo nenhum', () => {
    monta([LIVRE])

    expect(screen.getByRole('combobox')).toBeInTheDocument()
    expect(screen.getAllByRole('option').length).toBe(4) // "Escolher…" + 3
  })

  it('e aceita método e parâmetros', async () => {
    const onChange = monta([LIVRE])

    await userEvent.selectOptions(screen.getByRole('combobox'), 'HR')

    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ method: 'HR', fluence_j: null }),
    ])
  })
})

describe('pele bronzeada avisa e não impede', () => {
  it('o HR fica marcado mas continua escolhível', async () => {
    const onChange = monta([AXILAS], { bronzeada: true })

    const hr = screen.getAllByRole('option').find((o) => o.textContent?.startsWith('HR'))
    expect(hr?.textContent).toContain('não indicado em pele bronzeada')
    expect(hr).not.toBeDisabled()

    await userEvent.selectOptions(screen.getByRole('combobox'), 'HR')
    expect(onChange).toHaveBeenCalled()
  })
})

describe('remover aplicação', () => {
  it('tira a linha da lista', async () => {
    const onChange = monta([AXILAS])

    await userEvent.click(screen.getByRole('button', { name: 'Remover Axilas' }))

    expect(onChange).toHaveBeenCalledWith([])
  })
})
