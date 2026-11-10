import { api } from './api'
import type { ConsentWaiveReason, ListConsentsResponse, PatientConsent } from '@/types'

export interface UrlAssinada {
  url: string
  expiresInSeconds: number
}

export interface DispensaDoTermo {
  id: string
  consent_waived_at: string
  consent_waived_by: string
  consent_waived_reason: ConsentWaiveReason
  consent_waived_note: string | null
}

/** Termo de consentimento no painel (PRD 036). Rotas em `clinics/{clinicId}/consents/*`. */
export const consentsService = {
  listByPatient: (clinicId: string, patientId: string) =>
    api
      .get<ListConsentsResponse>(`/clinics/${clinicId}/consents/patients/${patientId}`)
      .then((r) => r.data),

  /** A recepção dispensa o termo NESTA sessão; a próxima pede de novo. */
  waive: (clinicId: string, appointmentId: string, reason: ConsentWaiveReason, note?: string) =>
    api
      .post<{ appointment: DispensaDoTermo }>(
        `/clinics/${clinicId}/consents/appointments/${appointmentId}/waive`,
        note ? { reason, note } : { reason }
      )
      .then((r) => r.data.appointment),

  /**
   * Assinado em papel na recepção: vale como vigente, sem PDF.
   * `created` é false quando a pessoa já tinha termo vigente: o servidor
   * devolve o que havia (200) sem gravar nada (PRD 047, lote).
   */
  registerPaper: (clinicId: string, patientId: string, signedAt: string) =>
    api
      .post<{ consent: PatientConsent }>(
        `/clinics/${clinicId}/consents/patients/${patientId}/paper`,
        { signedAt }
      )
      .then((r) => ({ consent: r.data.consent, created: r.status === 201 })),

  /** "Pedir nova assinatura" (PRD 038): o documento vigente vira REVOKED e o próximo check-in pede tudo de novo. */
  renew: (clinicId: string, consentId: string) =>
    api
      .post<{ consent: PatientConsent }>(`/clinics/${clinicId}/consents/${consentId}/renew`)
      .then((r) => r.data.consent),

  /** URL assinada do S3, válida por 5 min: pedir na hora de abrir, nunca guardar. */
  pdfUrl: (clinicId: string, consentId: string) =>
    api.get<UrlAssinada>(`/clinics/${clinicId}/consents/${consentId}/pdf-url`).then((r) => r.data),

  zipUrl: (clinicId: string, consentId: string) =>
    api.get<UrlAssinada>(`/clinics/${clinicId}/consents/${consentId}/zip-url`).then((r) => r.data),
}
