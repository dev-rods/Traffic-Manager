import { useQuery } from '@tanstack/react-query'
import { reportsService } from '@/services/reports.service'
import { useAuth } from './useAuth'

export const dashboardKeys = {
  all: ['dashboard'] as const,
  data: (clinicId: string) => [...dashboardKeys.all, clinicId] as const,
}

export function useDashboard() {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: dashboardKeys.data(clinicId!),
    queryFn: () => reportsService.dashboard(clinicId!),
    enabled: !!clinicId,
    staleTime: 2 * 60 * 1000, // 2 min — dashboard data is near-realtime but not critical
    refetchInterval: 5 * 60 * 1000, // auto-refresh every 5 min
  })
}
