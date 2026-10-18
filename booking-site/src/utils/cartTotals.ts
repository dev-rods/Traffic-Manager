import type { CartItem, CartPayload, ServiceArea, ServiceAreaPair } from '@/types'

export function getAreasForService(serviceAreas: ServiceArea[], serviceId: string): ServiceArea[] {
  return serviceAreas.filter((sa) => sa.service_id === serviceId)
}

export function cartHasAreas(items: CartItem[], serviceAreas: ServiceArea[]): boolean {
  return items.some((item) => getAreasForService(serviceAreas, item.service.id).length > 0)
}

/** Serviços do carrinho que têm áreas cadastradas mas nenhuma selecionada ainda. */
export function cartPendingAreaSelection(
  items: CartItem[],
  serviceAreas: ServiceArea[]
): CartItem[] {
  return items.filter((item) => {
    const areas = getAreasForService(serviceAreas, item.service.id)
    return areas.length > 0 && item.areaIds.length === 0
  })
}

export function buildServiceAreaPairs(
  items: CartItem[],
  serviceAreas: ServiceArea[]
): ServiceAreaPair[] {
  const pairs: ServiceAreaPair[] = []
  for (const item of items) {
    const areas = getAreasForService(serviceAreas, item.service.id)
    if (areas.length > 0) {
      for (const areaId of item.areaIds) {
        pairs.push({ serviceId: item.service.id, areaId })
      }
    }
  }
  return pairs
}

/**
 * O carrinho no formato que o backend recebe. Duração, preço e desconto não
 * são calculados aqui: o backend os deriva disto com as mesmas funções do bot
 * de WhatsApp (combos, regras de duração, política de desconto).
 */
export function toCartPayload(items: CartItem[], serviceAreas: ServiceArea[]): CartPayload {
  return {
    serviceIds: items.map((i) => i.service.id),
    serviceAreaPairs: buildServiceAreaPairs(items, serviceAreas),
  }
}
