import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { ConfiguracoesPage } from './ConfiguracoesPage'
import { LEMBRETE_PADRAO } from '@/lib/lembretePadrao'

const mutateAsync = vi.fn()
vi.mock('@/hooks/useClinic', () => ({
  useClinic: () => ({
    data: {
      clinic_id: 'c1', name: 'Essência', display_name: 'Essência', phone: '', address: '',
      buffer_minutes: 10, max_future_dates: 5, pre_session_instructions: '', zapi_instance_id: '',
      zapi_instance_token: '', batch_message_template: '', lembrete_automatico: false,
      lembrete_antecedencia_horas: 24,
    },
    isLoading: false, isError: false, error: null, refetch: vi.fn(),
  }),
  useUpdateClinic: () => ({ mutateAsync, isPending: false, isError: false }),
}))
vi.mock('@/hooks/useTemplates', () => ({
  useTemplate: () => ({ data: null, isLoading: false, isError: false }),
  useSalvaTemplate: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}))

describe('ConfiguracoesPage - lembrete de sessao', () => {
  // O texto padrao e o mesmo do backend e nao pode citar a saida: citar
  // cancelar planta a ideia (PRD 027). Teste literal, de proposito.
  it('o padrao do lembrete nao cita cancelar, remarcar nem link', () => {
    const t = LEMBRETE_PADRAO.toLowerCase()
    for (const proibido of ['cancel', 'remarc', 'http']) expect(t).not.toContain(proibido)
    for (const v of ['{{nome}}', '{{areas}}', '{{clinic_name}}', '{{dia}}', '{{hora}}']) expect(LEMBRETE_PADRAO).toContain(v)
  })

  it('ligar o automatico e mudar a antecedencia vao no payload', async () => {
    mutateAsync.mockResolvedValue({})
    render(<ConfiguracoesPage />)
    fireEvent.click(screen.getByRole('switch', { name: 'Enviar lembrete automaticamente' }))
    fireEvent.change(screen.getByLabelText('Antecedência (horas)'), { target: { value: '48' } })
    fireEvent.click(screen.getByRole('button', { name: 'Salvar configurações' }))
    expect(mutateAsync).toHaveBeenCalledWith(expect.objectContaining({ lembrete_automatico: true, lembrete_antecedencia_horas: 48 }))
  })

  it('a previa do texto usa dados de exemplo', () => {
    render(<ConfiguracoesPage />)
    expect(screen.getByTestId('preview')).toHaveTextContent('Oi Maria! Sua sessão de Axilas e Virilha Completa')
  })
})
