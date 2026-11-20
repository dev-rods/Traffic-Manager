import { describe, expect, it } from 'vitest'
import type { AplicacaoDeSessao, ParametroDoProtocolo } from '@/types'
import {
  adicionaMetodo,
  agrupaPorArea,
  chaveDaArea,
  chaveDaPendencia,
  normaliza,
  pendenciasDoRegistro,
  removeArea,
  removeLinha,
  resumoDasPendencias,
} from './aplicacoes'
import { resumoDoBloco } from './prontuario'

const ap = (
  area_name: string,
  protocol_area_key: string | null,
  extra: Partial<AplicacaoDeSessao> = {}
): AplicacaoDeSessao => ({
  area_id: null,
  area_name,
  protocol_area_key,
  method: null,
  fluence_j: null,
  energy_kj: null,
  stacks: null,
  passes: null,
  display_order: 0,
  ...extra,
})

const P = (
  method: 'SHR' | 'SHR_STACKING' | 'HR',
  protocol_area_key: string,
  fluence_j: number,
  energy_kj: number | null = null
): ParametroDoProtocolo => ({
  skin_type: 'BRANCA',
  method,
  protocol_area_key,
  protocol_area_name: protocol_area_key,
  fluence_j,
  energy_kj,
  stacks: null,
  passes: null,
  source: 'PDF',
})

const TABELA = [P('SHR', 'axilas', 8, 8), P('HR', 'axilas', 20, 1), P('SHR', 'buco', 6, 2)]

describe('agrupaPorArea', () => {
  it('junta os métodos da mesma área num bloco, na ordem da primeira ocorrência', () => {
    const blocos = agrupaPorArea([
      ap('Axilas', 'axilas', { method: 'SHR' }),
      ap('Buço', 'buco'),
      ap('Axilas', 'axilas', { method: 'HR' }),
    ])
    expect(blocos.map((b) => b.area_name)).toEqual(['Axilas', 'Buço'])
    expect(blocos[0].linhas.map((l) => l.method)).toEqual(['SHR', 'HR'])
  })

  it('mesmo nome com chave de protocolo diferente são áreas diferentes', () => {
    expect(agrupaPorArea([ap('Virilha', 'virilha_completa'), ap('Virilha', null)])).toHaveLength(2)
  })
})

describe('normaliza', () => {
  it('deixa contíguo por área e renumera display_order', () => {
    const r = normaliza([ap('A', null), ap('B', null), ap('A', null, { method: 'HR' })])
    expect(r.map((a) => a.area_name)).toEqual(['A', 'A', 'B'])
    expect(r.map((a) => a.display_order)).toEqual([0, 1, 2])
  })
})

describe('adicionaMetodo', () => {
  it('pré-escolhe o único método com sugestão que ainda não foi usado', () => {
    const axilas = ap('Axilas', 'axilas', { method: 'SHR', fluence_j: 8, energy_kj: 8 })
    const r = adicionaMetodo([axilas], chaveDaArea(axilas), TABELA, 'BRANCA')
    expect(r).toHaveLength(2)
    expect(r[1]).toMatchObject({ area_name: 'Axilas', method: 'HR', fluence_j: 20, energy_kj: 1 })
  })

  it('com mais de um método possível, deixa em branco', () => {
    const axilas = ap('Axilas', 'axilas')
    const r = adicionaMetodo([axilas], chaveDaArea(axilas), TABELA, 'BRANCA')
    expect(r[1]).toMatchObject({ method: null, fluence_j: null })
  })

  it('insere a linha logo depois da área, não no fim da lista', () => {
    const axilas = ap('Axilas', 'axilas', { method: 'SHR' })
    const r = adicionaMetodo([axilas, ap('Buço', 'buco')], chaveDaArea(axilas), TABELA, 'BRANCA')
    expect(r.map((a) => a.area_name)).toEqual(['Axilas', 'Axilas', 'Buço'])
    expect(r.map((a) => a.display_order)).toEqual([0, 1, 2])
  })
})

describe('remover', () => {
  const lista = normaliza([
    ap('Axilas', 'axilas', { method: 'SHR' }),
    ap('Axilas', 'axilas', { method: 'HR' }),
    ap('Buço', 'buco'),
  ])

  it('removeLinha tira só aquele método', () => {
    const r = removeLinha(lista, 1)
    expect(r.map((a) => [a.area_name, a.method])).toEqual([
      ['Axilas', 'SHR'],
      ['Buço', null],
    ])
  })

  it('removeArea tira todos os métodos da área', () => {
    expect(removeArea(lista, chaveDaArea(lista[0])).map((a) => a.area_name)).toEqual(['Buço'])
  })
})

describe('resumoDoBloco', () => {
  it('lê como a clínica escreve: área uma vez, métodos separados', () => {
    const [bloco] = agrupaPorArea([
      ap('Axilas', 'axilas', { method: 'SHR', fluence_j: 8, energy_kj: 8 }),
      ap('Axilas', 'axilas', { method: 'HR', fluence_j: 20, energy_kj: 1 }),
    ])
    expect(resumoDoBloco(bloco)).toBe('SHR · 8 J · 8 kJ / HR · 20 J · 1 kJ')
  })

  it('linha vazia diz que não tem parâmetro', () => {
    expect(resumoDoBloco(agrupaPorArea([ap('Axilas', null)])[0])).toBe('sem parâmetro registrado')
  })
})

/** Espelho de `valida_aplicacoes` (PRD 051): mesmas mensagens que o backend. */
describe('pendenciasDoRegistro', () => {
  it('registro vazio é uma pendência geral', () => {
    expect(pendenciasDoRegistro([])).toEqual([
      { indice: -1, area_name: '', campo: 'method', mensagem: 'Informe ao menos uma área aplicada.' },
    ])
  })

  it('sem método, pede o método e não olha os campos', () => {
    expect(pendenciasDoRegistro([ap('Costeleta', 'costeleta', { fluence_j: 6 })])).toEqual([
      { indice: 0, area_name: 'Costeleta', campo: 'method', mensagem: 'Costeleta: escolha o método.' },
    ])
  })

  it('SHR sem energia: o caso do relato', () => {
    const p = pendenciasDoRegistro([ap('Axilas', 'axilas', { method: 'SHR', fluence_j: 8 })])
    expect(p).toEqual([
      { indice: 0, area_name: 'Axilas', campo: 'energy_kj', mensagem: 'Axilas: informe Energia (kJ).' },
    ])
    expect(chaveDaPendencia(p[0])).toBe('0|energy_kj')
  })

  it('Stacking exige fluência, stacks e passadas; zero também acusa', () => {
    const p = pendenciasDoRegistro([ap('Buço', 'buco', { method: 'SHR_STACKING', fluence_j: 0, stacks: 3 })])
    expect(p.map((x) => x.mensagem)).toEqual([
      'Buço: Fluência (J) precisa ser maior que zero.',
      'Buço: informe Passadas.',
    ])
  })

  it('índices seguem a lista normalizada', () => {
    const p = pendenciasDoRegistro(
      normaliza([
        ap('Axilas', 'axilas', { method: 'SHR', fluence_j: 8, energy_kj: 8 }),
        ap('Buço', 'buco', { method: 'HR', fluence_j: 17 }),
      ]),
    )
    expect(p).toEqual([{ indice: 1, area_name: 'Buço', campo: 'energy_kj', mensagem: 'Buço: informe Energia (kJ).' }])
  })

  it('completo não tem pendência', () => {
    expect(pendenciasDoRegistro([ap('Axilas', 'axilas', { method: 'SHR', fluence_j: 8, energy_kj: 8 })])).toEqual([])
  })

  it('resumo: uma vira a própria mensagem, várias viram contagem', () => {
    const uma = [{ indice: 0, area_name: 'A', campo: 'method', mensagem: 'A: escolha o método.' }]
    expect(resumoDasPendencias(uma)).toBe('A: escolha o método.')
    expect(resumoDasPendencias([...uma, ...uma])).toBe(
      'Faltam 2 campos. Preencha os destacados ou remova a área que não foi aplicada.',
    )
  })
})
