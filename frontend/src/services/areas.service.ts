import { api } from './api'

export interface ServiceArea {
  service_area_id: string
  service_id: string
  area_id: string
  name: string
  display_order: number
  effective_duration_minutes: number
  effective_price_cents: number
  active: boolean
}

interface ListServiceAreasResponse {
  status: string
  areas: ServiceArea[]
}

export const areasService = {
  listByService(serviceId: string) {
    return api
      .get<ListServiceAreasResponse>(`/services/${serviceId}/areas`)
      .then((r) => r.data.areas)
  },
}
