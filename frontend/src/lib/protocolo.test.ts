import { describe, expect, it } from 'vitest'
import type { ParametroDoProtocolo } from '@/types'
import {
  CAMPOS_POR_METODO,
  avisos,
  bolinhas,
  hrDesaconselhado,
  metodosDaArea,
  sugestao,
  usaCampo,
} from './protocolo'

/**
 * O espelho do protocolo no frontend.
 *
 * Este arquivo espelha scheduler/src/services/protocolo_laser.py. Os dois
 * precisam concordar: divergindo, a tela desenha um campo que o backend
 * descarta, e a profissional digita um parâmetro que não é gravado.
 *
 * O caso que mais importa aqui é o negativo — a tela NUNCA pode aproximar uma
 * sugestão. Sugerir a fluência de outra área num equipamento que queima pele é
 * o erro que o módulo inteiro existe para não cometer.
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

const TABELA: ParametroDoProtocolo[] = [
  P('BRANCA', 'SHR', 'axilas', 7, { energy_kj: 8 }),
  P('NEGRA', 'SHR', 'axilas', 5, { energy_kj: 7 }),
  P('BRANCA', 'HR', 'axilas', 17, { energy_kj: 1 }),
  P('BRANCA', 'SHR_STACKING', 'buco', 6, { stacks: 3, passes: 2 }),
  P('BRANCA', 'HR', 'buco', 17, { energy_kj: 1 }),
  // Só pele branca, como no protocolo real.
  P('BRANCA', 'SHR', 'meio_gluteo', 8, { energy_kj: 7, source: 'CLINICA' }),
]

describe('campos por método', () => {
  it('cada método tem a sua forma', () => {
    expect(CAMPOS_POR_METODO.SHR).toEqual(['fluence_j', 'energy_kj'])
    expect(CAMPOS_POR_METODO.SHR_STACKING).toEqual(['fluence_j', 'stacks', 'passes'])
    expect(CAMPOS_POR_METODO.HR).toEqual(['fluence_j', 'energy_kj'])
  })

  it('o SHR não usa stacks', () => {
    expect(usaCampo('SHR', 'stacks')).toBe(false)
    expect(usaCampo('SHR_STACKING', 'stacks')).toBe(true)
  })

  it('sem método, nenhum campo', () => {
    expect(usaCampo(null, 'fluence_j')).toBe(false)
  })
})

describe('sugestão', () => {
  it('traz o parâmetro da pele certa', () => {
    expect(sugestao(TABELA, 'axilas', 'SHR', 'BRANCA')?.fluence_j).toBe(7)
    expect(sugestao(TABELA, 'axilas', 'SHR', 'NEGRA')?.fluence_j).toBe(5)
  })

  it('não cai no outro tipo de pele', () => {
    // meio_gluteo só existe na branca. Cair para ela sugeriria 8 J numa pele
    // cujo glúteo inteiro é 7.
    expect(sugestao(TABELA, 'meio_gluteo', 'SHR', 'NEGRA')).toBeNull()
  })

  it('não cai no outro método', () => {
    expect(sugestao(TABELA, 'buco', 'SHR', 'BRANCA')).toBeNull()
    expect(sugestao(TABELA, 'buco', 'SHR_STACKING', 'BRANCA')?.fluence_j).toBe(6)
  })

  it('sem tipo de pele não sugere nada', () => {
    expect(sugestao(TABELA, 'axilas', 'SHR', null)).toBeNull()
  })

  it('área sem protocolo não sugere nada', () => {
    expect(sugestao(TABELA, 'nariz', 'SHR', 'BRANCA')).toBeNull()
    expect(sugestao(TABELA, null, 'SHR', 'BRANCA')).toBeNull()
  })
})

describe('métodos da área', () => {
  it('área de um método só', () => {
    expect(metodosDaArea(TABELA, 'meio_gluteo')).toEqual(['SHR'])
  })

  it('área de mais de um método, na ordem do protocolo', () => {
    expect(metodosDaArea(TABELA, 'axilas')).toEqual(['SHR', 'HR'])
    expect(metodosDaArea(TABELA, 'buco')).toEqual(['SHR_STACKING', 'HR'])
  })

  it('área fora do protocolo', () => {
    expect(metodosDaArea(TABELA, 'nariz')).toEqual([])
    expect(metodosDaArea(TABELA, null)).toEqual([])
  })
})

describe('avisos', () => {
  it('pele bronzeada traz a proibição do HR, palavra por palavra', () => {
    const texto = avisos('SHR', 'BRANCA', true).join(' ')
    expect(texto).toContain('Nunca utilize o método HR')
  })

  it('HR em pele negra traz o aviso do fototipo VI', () => {
    expect(avisos('HR', 'NEGRA', false).join(' ')).toContain('fototipo VI')
  })

  it('HR sempre avisa do risco de queimadura', () => {
    expect(avisos('HR', 'BRANCA', false).join(' ')).toContain('queimaduras')
  })

  it('SHR em pele clara não avisa nada', () => {
    expect(avisos('SHR', 'BRANCA', false)).toEqual([])
  })
})

describe('HR desaconselhado', () => {
  it('só em pele bronzeada — e desaconselhar não é bloquear', () => {
    expect(hrDesaconselhado(true)).toBe(true)
    expect(hrDesaconselhado(false)).toBe(false)
  })
})

describe('bolinhas', () => {
  it('é como o material da clínica escreve stacks', () => {
    expect(bolinhas(3)).toBe('●●●')
    expect(bolinhas(2)).toBe('●●')
  })

  it('sem stacks, nada', () => {
    expect(bolinhas(null)).toBe('')
    expect(bolinhas(0)).toBe('')
  })
})
