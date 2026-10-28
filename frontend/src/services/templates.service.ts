import { api } from './api'
import type { MessageTemplate } from '@/types'

interface TemplatesResponse {
  status: string
  data: MessageTemplate[]
}

interface TemplateResponse {
  status: string
  data: MessageTemplate
}

/** Os textos que a clinica sobrescreve (`message_templates`). Sem linha, vale o
 *  default do backend - a tela mostra o default como placeholder. */
export const templatesService = {
  list(clinicId: string, templateKey?: string) {
    return api
      .get<TemplatesResponse>(`/clinics/${clinicId}/templates`, {
        params: templateKey ? { template_key: templateKey } : undefined,
      })
      .then((r) => r.data.data)
  },

  create(clinicId: string, templateKey: string, content: string) {
    return api
      .post<TemplateResponse>(`/clinics/${clinicId}/templates`, { template_key: templateKey, content })
      .then((r) => r.data.data)
  },

  update(templateId: string, content: string) {
    return api
      .put<TemplateResponse>(`/templates/${templateId}`, { content })
      .then((r) => r.data.data)
  },
}
