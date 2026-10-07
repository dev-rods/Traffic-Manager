import { useQuery } from '@tanstack/react-query'
import { agendaSummaryService, reportsService } from '@/services/reports.service'
import { useAuth } from './useAuth'

export const dashboardKeys = {
  all: ['dashboard'] as const,
  data: (clinicId: string, date?: string) => [...dashboardKeys.all, clinicId, date] as const,
}

export function useDashboard(date?: string) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: dashboardKeys.data(clinicId!, date),
    queryFn: () => reportsService.dashboard(clinicId!, date),
    enabled: !!clinicId,
    staleTime: 2 * 60 * 1000,
    refetchInterval: 5 * 60 * 1000,
  })
}

export const agendaSummaryKeys = {
  all: ['agenda-summary'] as const,
  range: (clinicId: string, start?: string, end?: string) =>
    [...agendaSummaryKeys.all, clinicId, start, end] as const,
}

/**
 * Resumo da agenda dia a dia.
 *
 * `staleTime` curto de proposito: a gerencia olha esta tela justamente quando
 * acabou de acontecer alguma coisa - um cancelamento, um encaixe - e um cache
 * de cinco minutos mostraria o numero de antes.
 */
export function useAgendaSummary(params?: { start?: string; end?: string }) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: agendaSummaryKeys.range(clinicId!, params?.start, params?.end),
    queryFn: () => agendaSummaryService.get(clinicId!, params),
    enabled: !!clinicId,
    staleTime: 30 * 1000,
  })
}
