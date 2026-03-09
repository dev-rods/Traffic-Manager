import { useQuery } from '@tanstack/react-query'
import { reportsService } from '@/services/reports.service'
import type { ReportPeriod } from '@/services/reports.service'
import { useAuth } from './useAuth'

export const reportKeys = {
  all: ['reports'] as const,
  byPeriod: (clinicId: string, period: ReportPeriod) =>
    [...reportKeys.all, clinicId, period] as const,
}

export function useReports(period: ReportPeriod) {
  const { clinicId } = useAuth()

  return useQuery({
    queryKey: reportKeys.byPeriod(clinicId!, period),
    queryFn: () => reportsService.get(clinicId!, period),
    enabled: !!clinicId,
  })
}
