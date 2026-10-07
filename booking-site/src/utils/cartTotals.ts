import type { CartItem, ServiceArea } from '@/types'

export function getAreasForService(serviceAreas: ServiceArea[], serviceId: string): ServiceArea[] {
  return serviceAreas.filter((sa) => sa.service_id === serviceId)
}

export function cartHasAreas(items: CartItem[], serviceAreas: ServiceArea[]): boolean {
  return items.some((item) => getAreasForService(serviceAreas, item.service.id).length > 0)
}

export function computeCartTotals(items: CartItem[], serviceAreas: ServiceArea[]) {
  let durationMinutes = 0
  let priceCents = 0

  for (const item of items) {
    const areas = getAreasForService(serviceAreas, item.service.id)
    if (areas.length > 0 && item.areaIds.length > 0) {
      for (const areaId of item.areaIds) {
        const match = areas.find((a) => a.area_id === areaId)
        if (match) {
          durationMinutes += match.duration_minutes
          priceCents += match.price_cents ?? 0
        }
      }
    } else {
      durationMinutes += item.service.duration_minutes
      priceCents += item.service.price_cents ?? 0
    }
  }

  return { durationMinutes, priceCents }
}

/** Serviços do carrinho que têm áreas cadastradas mas nenhuma selecionada ainda. */
export function cartPendingAreaSelection(items: CartItem[], serviceAreas: ServiceArea[]): CartItem[] {
  return items.filter((item) => {
    const areas = getAreasForService(serviceAreas, item.service.id)
    return areas.length > 0 && item.areaIds.length === 0
  })
}

export function buildServiceAreaPairs(
  items: CartItem[],
  serviceAreas: ServiceArea[]
): { serviceId: string; areaId: string }[] {
  const pairs: { serviceId: string; areaId: string }[] = []
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
