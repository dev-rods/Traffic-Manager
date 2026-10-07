import { useQuery } from '@tanstack/react-query'
import { sessionRecordsService } from '@/services/sessionRecords.service'
import { useAuth } from './useAuth'

export const protocoloKeys = {
  all: ['laser-protocol'] as const,
  detail: (clinicId: string) => [...protocoloKeys.all, clinicId] as const,
}

/**
 * O protocolo inteiro, cacheado.
 *
 * São 80 linhas de referência que quase nunca mudam. Sem o cache, sugerir um
 * parâmetro custaria uma chamada por linha de aplicação enquanto a profissional
 * digita — com a paciente esperando.
 */
export function useProtocoloLaser() {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: protocoloKeys.detail(clinicId!),
    queryFn: () => sessionRecordsService.protocol(clinicId!),
    enabled: !!clinicId,
    staleTime: 1000 * 60 * 30,
  })
}
