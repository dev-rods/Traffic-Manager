import { useQuery } from '@tanstack/react-query'
import { reportsService } from '@/services/reports.service'
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
