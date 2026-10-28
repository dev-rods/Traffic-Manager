import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { templatesService } from '@/services/templates.service'
import { useAuth } from './useAuth'

export const templateKeys = {
  all: ['templates'] as const,
  byKey: (clinicId: string, templateKey: string) => [...templateKeys.all, clinicId, templateKey] as const,
}

/** O template de UMA chave da clinica, ou null quando ela usa o default. */
export function useTemplate(templateKey: string) {
  const { clinicId } = useAuth()
  return useQuery({
    queryKey: templateKeys.byKey(clinicId!, templateKey),
    queryFn: () => templatesService.list(clinicId!, templateKey).then((lista) => lista[0] ?? null),
    enabled: !!clinicId,
  })
}

/** Cria ou atualiza o template da chave. Quem decide e a existencia da linha. */
export function useSalvaTemplate(templateKey: string) {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ templateId, content }: { templateId: string | null; content: string }) =>
      templateId
        ? templatesService.update(templateId, content)
        : templatesService.create(clinicId!, templateKey, content),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: templateKeys.all }),
  })
}
