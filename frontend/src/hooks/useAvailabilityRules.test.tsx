import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import {
  availabilityRuleKeys,
  exceptionKeys,
  useDeleteAvailabilityRule,
  useDeleteAvailabilityException,
} from './useAvailabilityRules'
import { availabilityService } from '@/services/availability.service'
import type { AvailabilityRule, AvailabilityException } from '@/types'

const CLINIC_ID = 'clinica-teste-abc123'

vi.mock('@/services/availability.service', () => ({
  availabilityService: {
    deleteRule: vi.fn(),
    deleteException: vi.fn(),
  },
}))

vi.mock('./useAuth', () => ({
  useAuth: () => ({ clinicId: CLINIC_ID }),
}))

function makeRule(id: string): AvailabilityRule {
  return {
    id,
    clinic_id: CLINIC_ID,
    day_of_week: 1,
    rule_date: null,
    start_time: '09:00:00',
    end_time: '18:00:00',
    professional_id: null,
    active: true,
  }
}

function makeException(id: string): AvailabilityException {
  return {
    id,
    clinic_id: CLINIC_ID,
    exception_date: '2026-09-07',
    exception_type: 'BLOCKED',
    start_time: null,
    end_time: null,
    reason: 'Feriado',
  }
}

function setup() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
  return { queryClient, wrapper }
}

describe('useDeleteAvailabilityRule', () => {
  beforeEach(() => vi.clearAllMocks())

  it('remove a regra do cache antes da API responder', async () => {
    const { queryClient, wrapper } = setup()
    queryClient.setQueryData(availabilityRuleKeys.list(CLINIC_ID), {
      status: 'SUCCESS',
      data: [makeRule('rule-1'), makeRule('rule-2')],
    })

    // Promise que so resolve quando quisermos: permite inspecionar o estado
    // intermediario, que e exatamente o que o optimistic update promete.
    let resolveDelete: () => void = () => {}
    vi.mocked(availabilityService.deleteRule).mockReturnValue(
      new Promise<void>((resolve) => {
        resolveDelete = resolve
      }),
    )

    const { result } = renderHook(() => useDeleteAvailabilityRule(), { wrapper })
    result.current.mutate('rule-1')

    await waitFor(() => {
      const cached = queryClient.getQueryData<{ data: AvailabilityRule[] }>(
        availabilityRuleKeys.list(CLINIC_ID),
      )
      expect(cached?.data.map((r) => r.id)).toEqual(['rule-2'])
    })

    resolveDelete()
  })

  it('restaura a regra no cache quando a API falha', async () => {
    const { queryClient, wrapper } = setup()
    queryClient.setQueryData(availabilityRuleKeys.list(CLINIC_ID), {
      status: 'SUCCESS',
      data: [makeRule('rule-1'), makeRule('rule-2')],
    })

    vi.mocked(availabilityService.deleteRule).mockRejectedValue(new Error('500'))

    const { result } = renderHook(() => useDeleteAvailabilityRule(), { wrapper })
    result.current.mutate('rule-1')

    await waitFor(() => expect(result.current.isError).toBe(true))

    const cached = queryClient.getQueryData<{ data: AvailabilityRule[] }>(
      availabilityRuleKeys.list(CLINIC_ID),
    )
    expect(cached?.data.map((r) => r.id)).toEqual(['rule-1', 'rule-2'])
  })

  it('cancela queries em voo, senao um refetch repoe o item excluido', async () => {
    const { queryClient, wrapper } = setup()
    queryClient.setQueryData(availabilityRuleKeys.list(CLINIC_ID), {
      status: 'SUCCESS',
      data: [makeRule('rule-1')],
    })

    const cancelSpy = vi.spyOn(queryClient, 'cancelQueries')
    vi.mocked(availabilityService.deleteRule).mockResolvedValue(undefined)

    const { result } = renderHook(() => useDeleteAvailabilityRule(), { wrapper })
    result.current.mutate('rule-1')

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(cancelSpy).toHaveBeenCalledWith({
      queryKey: availabilityRuleKeys.list(CLINIC_ID),
    })
  })

  it('envia o clinicId na chamada do service (isolamento multi-tenant)', async () => {
    const { wrapper } = setup()
    vi.mocked(availabilityService.deleteRule).mockResolvedValue(undefined)

    const { result } = renderHook(() => useDeleteAvailabilityRule(), { wrapper })
    result.current.mutate('rule-1')

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(availabilityService.deleteRule).toHaveBeenCalledWith(CLINIC_ID, 'rule-1')
  })
})

describe('useDeleteAvailabilityException', () => {
  beforeEach(() => vi.clearAllMocks())

  it('remove do cache tratando a lista sem envelope', async () => {
    const { queryClient, wrapper } = setup()
    // Diferente das rules: listExceptions devolve o array direto.
    queryClient.setQueryData(exceptionKeys.list(CLINIC_ID), [
      makeException('exc-1'),
      makeException('exc-2'),
    ])

    vi.mocked(availabilityService.deleteException).mockResolvedValue(undefined)

    const { result } = renderHook(() => useDeleteAvailabilityException(), { wrapper })
    result.current.mutate('exc-1')

    await waitFor(() => {
      const cached = queryClient.getQueryData<AvailabilityException[]>(
        exceptionKeys.list(CLINIC_ID),
      )
      expect(cached?.map((e) => e.id)).toEqual(['exc-2'])
    })
  })

  it('restaura a excecao no cache quando a API falha', async () => {
    const { queryClient, wrapper } = setup()
    queryClient.setQueryData(exceptionKeys.list(CLINIC_ID), [makeException('exc-1')])

    vi.mocked(availabilityService.deleteException).mockRejectedValue(new Error('500'))

    const { result } = renderHook(() => useDeleteAvailabilityException(), { wrapper })
    result.current.mutate('exc-1')

    await waitFor(() => expect(result.current.isError).toBe(true))

    const cached = queryClient.getQueryData<AvailabilityException[]>(exceptionKeys.list(CLINIC_ID))
    expect(cached?.map((e) => e.id)).toEqual(['exc-1'])
  })
})
