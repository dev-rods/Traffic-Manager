import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AppointmentPopover } from './AppointmentPopover'
import type { Appointment } from '@/types'

vi.mock('@/hooks/useConsents', () => ({
  useConsentsDoPaciente: () => ({ data: undefined, isLoading: false }),
  useDispensarTermo: () => ({ mutate: vi.fn(), isPending: false }),
  useRegistrarPapel: () => ({ mutate: vi.fn(), isPending: false }),
  useRenovarTermo: () => ({ mutate: vi.fn(), isPending: false, isSuccess: false }),
  useAbrirDocumentoDoTermo: () => ({ abrir: vi.fn(), abrindo: null }),
}))
vi.mock('@/hooks/useCaixa', () => ({
  useReceberDinheiro: () => ({
    mutate: vi.fn(),
    isPending: false,
    isSuccess: false,
    data: undefined,
  }),
  useEnviarLink: () => ({ mutate: vi.fn(), isPending: false }),
}))
vi.mock('@/components/ui/toastContext', () => ({ useToast: () => ({ showToast: vi.fn() }) }))

/** O painel em desktop (>= 768px) ou em celular. */
function telaDe(largura: number, altura = 800) {
  vi.stubGlobal('matchMedia', (q: string) => ({
    media: q,
    matches: largura >= 768,
    addEventListener: () => {},
    removeEventListener: () => {},
  }))
  Object.defineProperty(window, 'innerWidth', { value: largura, configurable: true })
  Object.defineProperty(window, 'innerHeight', { value: altura, configurable: true })
}

function agendamento(over: Partial<Appointment> = {}): Appointment {
  return {
    id: 'a1',
    appointment_date: '2026-11-06',
    start_time: '09:00:00',
    end_time: '09:15:00',
    status: 'CONFIRMED',
    patient_name: 'Ana Clara',
    areas: 'Axilas',
    duration_minutes: 15,
    is_first_visit: false,
    lembrete_enviado_em: null,
    lembrete_status: null,
    lembrete_erro: null,
    confirmado_em: null,
    confirmado_por: null,
    ...over,
  } as Appointment
}

const ancora = { top: 700, right: 300, left: 100, bottom: 720, width: 200, height: 20 } as DOMRect

function abre(a: Appointment, over: Partial<Parameters<typeof AppointmentPopover>[0]> = {}) {
  const props = {
    appointment: a,
    anchorRect: ancora,
    onClose: vi.fn(),
    onEdit: vi.fn(),
    onCancel: vi.fn(),
    onMarcarFalta: vi.fn(),
    onDesmarcarFalta: vi.fn(),
    onConfirmar: vi.fn(),
    onDesconfirmar: vi.fn(),
    ...over,
  }
  render(
    <MemoryRouter>
      <AppointmentPopover {...props} />
    </MemoryRouter>
  )
  return props
}

describe('AppointmentPopover', () => {
  beforeEach(() => telaDe(1280, 800))

  it('em desktop a caixa tem teto de altura e rola por dentro, para os botões do fim não caírem fora da tela', () => {
    abre(agendamento())
    const caixa = screen.getByText('Ana Clara').closest('.absolute') as HTMLElement
    // A âncora está em 700px numa tela de 800px: o top sobe para 400 (sobram
    // 400px) e a altura máxima é o que resta da tela a partir dali.
    expect(caixa.style.top).toBe('400px')
    expect(caixa.style.maxHeight).toBe('calc(100vh - 408px)')
    expect(caixa.className).toContain('overflow-y-auto')
  })

  it('em celular a folha de baixo continua com teto e scroll', () => {
    telaDe(375, 667)
    abre(agendamento(), { anchorRect: null })
    const caixa = screen.getByText('Ana Clara').closest('.absolute') as HTMLElement
    expect(caixa.className).toContain('max-h-[85vh]')
    expect(caixa.className).toContain('overflow-y-auto')
  })

  it('confirma presença mesmo sem lembrete enviado (quem confirma por telefone)', async () => {
    const props = abre(agendamento({ lembrete_enviado_em: null }))
    await userEvent.click(screen.getByRole('button', { name: 'Marcar como confirmado' }))
    expect(props.onConfirmar).toHaveBeenCalledWith(expect.objectContaining({ id: 'a1' }))
    expect(props.onClose).toHaveBeenCalled()
  })

  it('confirmada pela equipe sem lembrete: a linha Presença aparece e o botão vira "Desfazer"', () => {
    abre(
      agendamento({
        lembrete_enviado_em: null,
        confirmado_em: '2026-11-05T20:00:00Z',
        confirmado_por: 'EQUIPE',
      })
    )
    expect(screen.getByText('Presença')).toBeInTheDocument()
    expect(screen.getByText('Confirmada pela equipe')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Marcar como confirmado' })).toBeNull()
    expect(screen.getByRole('button', { name: 'Desfazer confirmação' })).toBeInTheDocument()
  })

  it('sem lembrete e sem confirmação não mostra "Pendente": não houve pergunta', () => {
    abre(agendamento())
    expect(screen.queryByText('Presença')).toBeNull()
    expect(screen.queryByText('Pendente')).toBeNull()
  })
})
