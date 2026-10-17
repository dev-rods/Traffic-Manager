import { describe, expect, it } from 'vitest'
import { buildServiceAreaPairs, cartHasAreas, cartPendingAreaSelection, toCartPayload } from './cartTotals'
import type { CartItem, ServiceArea } from '@/types'

const serviceNoAreas = { id: 'svc-1', name: 'Limpeza de pele', duration_minutes: 60, price_cents: 10000, description: null }
const serviceWithAreas = { id: 'svc-2', name: 'Depilação a laser', duration_minutes: 20, price_cents: 15000, description: null }

const serviceAreas: ServiceArea[] = [
  { service_area_id: 'sa-1', service_id: 'svc-2', area_id: 'area-1', area_name: 'Axilas', display_order: 1, duration_minutes: 5, price_cents: 9500 },
  { service_area_id: 'sa-2', service_id: 'svc-2', area_id: 'area-2', area_name: 'Buço', display_order: 2, duration_minutes: 2, price_cents: 6500 },
]

describe('cartHasAreas / cartPendingAreaSelection', () => {
  it('detecta que o carrinho tem um serviço com áreas configuradas', () => {
    const items: CartItem[] = [{ service: serviceWithAreas, areaIds: [] }]
    expect(cartHasAreas(items, serviceAreas)).toBe(true)
    expect(cartPendingAreaSelection(items, serviceAreas)).toHaveLength(1)
  })

  it('não pende seleção depois que uma área é escolhida', () => {
    const items: CartItem[] = [{ service: serviceWithAreas, areaIds: ['area-1'] }]
    expect(cartPendingAreaSelection(items, serviceAreas)).toHaveLength(0)
  })

  it('serviço sem áreas nunca fica pendente', () => {
    const items: CartItem[] = [{ service: serviceNoAreas, areaIds: [] }]
    expect(cartHasAreas(items, serviceAreas)).toBe(false)
    expect(cartPendingAreaSelection(items, serviceAreas)).toHaveLength(0)
  })
})

describe('buildServiceAreaPairs', () => {
  it('não gera pares quando nenhum serviço do carrinho tem áreas', () => {
    const items: CartItem[] = [{ service: serviceNoAreas, areaIds: [] }]
    expect(buildServiceAreaPairs(items, serviceAreas)).toEqual([])
  })

  it('gera um par por área selecionada', () => {
    const items: CartItem[] = [{ service: serviceWithAreas, areaIds: ['area-1', 'area-2'] }]
    expect(buildServiceAreaPairs(items, serviceAreas)).toEqual([
      { serviceId: 'svc-2', areaId: 'area-1' },
      { serviceId: 'svc-2', areaId: 'area-2' },
    ])
  })
})

describe('toCartPayload', () => {
  it('manda serviços na ordem do carrinho e só os pares escolhidos — duração e preço são do backend', () => {
    const items: CartItem[] = [
      { service: serviceNoAreas, areaIds: [] },
      { service: serviceWithAreas, areaIds: ['area-2'] },
    ]
    expect(toCartPayload(items, serviceAreas)).toEqual({
      serviceIds: ['svc-1', 'svc-2'],
      serviceAreaPairs: [{ serviceId: 'svc-2', areaId: 'area-2' }],
    })
  })
})
