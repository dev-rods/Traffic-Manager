import { api } from './api'
import type { AssetUploadUrlResponse, Clinic, ClinicAssetKind, UpdateClinicPayload } from '@/types'

interface GetClinicResponse {
  status: string
  clinic: Clinic
}

interface UpdateClinicResponse extends GetClinicResponse {
  domainWarning?: string
}

export const clinicService = {
  get(clinicId: string) {
    return api
      .get<GetClinicResponse>(`/clinics/${clinicId}`)
      .then((r) => r.data.clinic)
  },

  update(clinicId: string, payload: UpdateClinicPayload) {
    return api
      .put<UpdateClinicResponse>(`/clinics/${clinicId}`, payload)
      .then((r) => ({ clinic: r.data.clinic, domainWarning: r.data.domainWarning }))
  },

  getAssetUploadUrl(clinicId: string, kind: ClinicAssetKind, contentType: string) {
    return api
      .post<AssetUploadUrlResponse>(`/clinics/${clinicId}/assets/upload-url`, { kind, contentType })
      .then((r) => r.data)
  },
}
