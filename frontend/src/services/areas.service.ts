import { api } from './api'
import type { ClinicArea, CreateAreaPayload } from '@/types'

export interface ServiceArea {
  service_area_id: string
  service_id: string
  area_id: string
  name: string
  display_order: number
  duration_minutes: number | null
  service_duration_minutes: number
  effective_duration_minutes: number
  price_cents: number | null
  service_price_cents: number | null
  effective_price_cents: number
  pre_session_instructions: string | null
  active: boolean
}

interface ListServiceAreasResponse {
  status: string
  areas: ServiceArea[]
}

interface ListClinicAreasResponse {
  status: string
  areas: ClinicArea[]
}

interface AreaResponse {
  status: string
  area: ClinicArea
}

interface ServiceAreaResponse {
  status: string
  service_area: Record<string, unknown>
}

export interface CreateServiceAreaPayload {
  area_id: string
  duration_minutes?: number | null
  price_cents?: number | null
}

export const areasService = {
  // Clinic-level areas (global catalog)
  listClinicAreas(clinicId: string) {
    return api
      .get<ListClinicAreasResponse>(`/clinics/${clinicId}/areas`)
      .then((r) => r.data.areas)
  },

  createArea(clinicId: string, payload: CreateAreaPayload) {
    return api
      .post<{ status: string; areas: ClinicArea[] }>(`/clinics/${clinicId}/areas`, payload)
      .then((r) => r.data.areas[0])
  },

  updateArea(areaId: string, payload: Partial<CreateAreaPayload> & { active?: boolean }) {
    return api
      .put<AreaResponse>(`/areas/${areaId}`, payload)
      .then((r) => r.data.area)
  },

  deleteArea(areaId: string) {
    return api.delete(`/areas/${areaId}`).then((r) => r.data)
  },

  // Service-level areas (mappings)
  listByService(serviceId: string) {
    return api
      .get<ListServiceAreasResponse>(`/services/${serviceId}/areas`)
      .then((r) => r.data.areas)
  },

  createServiceArea(serviceId: string, payload: CreateServiceAreaPayload) {
    return api
      .post<ServiceAreaResponse>(`/services/${serviceId}/areas`, payload)
      .then((r) => r.data)
  },

  updateServiceArea(serviceId: string, areaId: string, payload: { duration_minutes?: number | null; price_cents?: number | null; pre_session_instructions?: string | null }) {
    return api
      .put<ServiceAreaResponse>(`/services/${serviceId}/areas/${areaId}`, payload)
      .then((r) => r.data)
  },

  deleteServiceArea(serviceId: string, areaId: string) {
    return api.delete(`/services/${serviceId}/areas/${areaId}`).then((r) => r.data)
  },
}
