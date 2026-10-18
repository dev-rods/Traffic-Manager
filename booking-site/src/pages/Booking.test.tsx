import { useEffect, useState } from 'react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Booking } from './Booking'
import { CartProvider } from '@/store/CartProvider'
import { useCart } from '@/store/useCart'
import { ClinicIdContext } from '@/store/clinicIdContext'
import { bookingService } from '@/services/booking.service'
import { ApiError } from '@/services/api'
import { toISODate } from '@/utils/dates'
import type { Appointment, AvailabilityResponse, BootstrapResponse, Quote, Service } from '@/types'

vi.mock('@/services/booking.service')

const SERVICE: Service = {
  id: 'svc-1',
  name: 'Depilação a Laser',
  duration_minutes: 20,
  price_cents: 15000,
  description: null,
}

function bootstrap(professionals = 1): BootstrapResponse {
  return {
    status: 'SUCCESS',
    clinic: {
      clinic_id: 'c1',
      name: 'Clínica X',
      display_name: null,
      logo_url: null,
      favicon_url: null,
      timezone: 'America/Sao_Paulo',
      phone: '11999990000',
    },
    services: [SERVICE],
    professionals: Array.from({ length: professionals }, (_, i) => ({
      id: `p${i + 1}`,
      name: `Prof ${i + 1}`,
      role: null,
      photo_url: null,
    })),
    serviceAreas: [],
    discountTiers: [],
  }
}

const TODAY = toISODate(new Date())

function availability(): AvailabilityResponse {
  return {
    days: { [TODAY]: { status: 'AVAILABLE', slots: ['23:59'] } },
    window: { start: TODAY, end: TODAY, nextOpensOn: TODAY },
  }
}

const NO_DISCOUNT: Quote = {
  originalPriceCents: 15000,
  discountPct: 0,
  discountReason: null,
  finalPriceCents: 15000,
  areaCount: 0,
  combos: [],
}
// Com telefone o backend não diz o motivo (não revela se o número já foi
// paciente): só o percentual e o valor final.
const PHONE_DISCOUNT: Quote = {
  ...NO_DISCOUNT,
  discountPct: 50,
  discountReason: null,
  finalPriceCents: 7500,
}

// Monta o carrinho já com o serviço antes do Booking montar - igual ao Home
// faz antes de navegar pra /agendar.
function PreloadCart({ children }: { children: React.ReactNode }) {
  const cart = useCart()
  const [ready, setReady] = useState(false)
  useEffect(() => {
    cart.addItem(SERVICE)
    setReady(true)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return ready ? <>{children}</> : null
}

function renderBooking() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/c1/agendar']}>
        <ClinicIdContext.Provider value={{ clinicId: 'c1', basePath: '/c1' }}>
          <CartProvider>
            <PreloadCart>
              <Routes>
                <Route path="/c1" element={<div>Home mockada</div>} />
                <Route path="/c1/agendar" element={<Booking />} />
              </Routes>
            </PreloadCart>
          </CartProvider>
        </ClinicIdContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

async function chooseSlotAndContinue() {
  await userEvent.click(
    await screen.findByRole('button', { name: new RegExp(`${Number(TODAY.slice(8))} de`) })
  )
  await userEvent.click(await screen.findByRole('button', { name: '23:59' }))
  await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
}

async function fillCustomer() {
  await userEvent.type(screen.getByLabelText(/nome/i), 'Maria Silva')
  await userEvent.type(screen.getByLabelText(/celular/i), '11987654321')
}

describe('Booking - serviço único', () => {
  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrap())
    vi.mocked(bookingService.availability).mockResolvedValue(availability())
    vi.mocked(bookingService.quote).mockResolvedValue(NO_DISCOUNT)
  })

  it('pula a etapa de revisão do carrinho e vai direto pro agendamento', async () => {
    renderBooking()

    expect(await screen.findByText('Escolha o dia')).toBeInTheDocument()

    // Não existe "outro serviço" pra escolher - a etapa de revisão do
    // carrinho (e o botão) nem aparecem, o fluxo já começa no agendamento.
    expect(screen.queryByText('Adicionar outro serviço')).not.toBeInTheDocument()
  })

  it('"Voltar" a partir do agendamento sai direto pro início, sem passar pela revisão', async () => {
    renderBooking()

    expect(await screen.findByText('Escolha o dia')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))

    expect(await screen.findByText('Home mockada')).toBeInTheDocument()
  })

  it('pede a agenda pelo carrinho - a duração é calculada pelo backend', async () => {
    renderBooking()
    await screen.findByText('Escolha o dia')
    const [clinicId, dates, cart] = vi.mocked(bookingService.availability).mock.calls[0]
    expect(clinicId).toBe('c1')
    expect(dates[0]).toBe(TODAY)
    expect(cart).toEqual({ serviceIds: ['svc-1'], serviceAreaPairs: [] })
  })

  it('pergunta de novo pela janela do backend quando o "hoje" do navegador não é o da clínica', async () => {
    // Navegador ainda no mês passado; na clínica já é dia 1º do mês seguinte.
    const now = new Date()
    const clinicToday = toISODate(new Date(now.getFullYear(), now.getMonth() + 1, 1))
    vi.mocked(bookingService.availability).mockImplementation(async (_c, dates) => ({
      days: Object.fromEntries(
        dates.map((d) => [
          d,
          d === clinicToday
            ? { status: 'AVAILABLE', slots: ['10:00'] }
            : { status: 'CLOSED', slots: [] },
        ])
      ),
      window: { start: clinicToday, end: clinicToday, nextOpensOn: clinicToday },
    }))
    renderBooking()

    expect(await screen.findByRole('button', { name: / 1 de / })).toBeInTheDocument()
    const requested = vi.mocked(bookingService.availability).mock.calls.map((c) => c[1])
    expect(requested[0][0]).toBe(toISODate(now))
    expect(requested[requested.length - 1]).toEqual([clinicToday])
    const calls = vi.mocked(bookingService.availability).mock.calls.length
    await new Promise((r) => setTimeout(r, 50))
    expect(vi.mocked(bookingService.availability).mock.calls.length).toBe(calls)
  })

  it('não mostra duração em nenhum lugar', async () => {
    renderBooking()
    await screen.findByText('Escolha o dia')
    expect(screen.queryByText(/\d+\s?min\b/)).not.toBeInTheDocument()
  })
})

describe('Booking - profissional', () => {
  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrap(2))
    vi.mocked(bookingService.availability).mockResolvedValue(availability())
    vi.mocked(bookingService.quote).mockResolvedValue(NO_DISCOUNT)
    vi.mocked(bookingService.createAppointment).mockResolvedValue({
      final_price_cents: 15000,
    } as Appointment)
  })

  it('com vários profissionais não pede pra escolher - o backend atribui', async () => {
    renderBooking()
    expect(await screen.findByText('Escolha o dia')).toBeInTheDocument()
    expect(screen.queryByText(/profissional/i)).not.toBeInTheDocument()

    await chooseSlotAndContinue()
    await fillCustomer()
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar agendamento' }))

    await waitFor(() => expect(bookingService.createAppointment).toHaveBeenCalled())
    const payload = vi.mocked(bookingService.createAppointment).mock.calls[0][1]
    expect(payload).not.toHaveProperty('professionalId')
    expect(payload).toEqual({
      serviceIds: ['svc-1'],
      serviceAreaPairs: [],
      phone: '5511987654321',
      fullName: 'Maria Silva',
      date: TODAY,
      time: '23:59',
    })
    expect(await screen.findByText('Agendamento confirmado!')).toBeInTheDocument()
    expect(screen.getByText(/\(11\) 98765-4321/)).toBeInTheDocument()
  })
})

describe('Booking - preço e desconto', () => {
  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrap())
    vi.mocked(bookingService.availability).mockResolvedValue(availability())
    vi.mocked(bookingService.quote).mockImplementation(async (_c, _cart, phone) =>
      phone ? PHONE_DISCOUNT : NO_DISCOUNT
    )
  })

  it('o desconto do celular aparece ao digitá-lo, antes de confirmar, sem dizer o motivo', async () => {
    renderBooking()
    await screen.findByText('Escolha o dia')
    expect(screen.queryByText(/Desconto/)).not.toBeInTheDocument()

    await chooseSlotAndContinue()
    await fillCustomer()

    expect(await screen.findByText('Desconto (50%)')).toBeInTheDocument()
    expect(screen.getByText('Valor final')).toBeInTheDocument()
    expect(bookingService.quote).toHaveBeenLastCalledWith(
      'c1',
      { serviceIds: ['svc-1'], serviceAreaPairs: [] },
      '5511987654321'
    )
  })

  it('horário ocupado no meio do caminho (409) volta pra agenda com aviso', async () => {
    vi.mocked(bookingService.createAppointment).mockRejectedValue(
      new ApiError('Conflito de horário', 409)
    )
    renderBooking()
    await screen.findByText('Escolha o dia')
    await chooseSlotAndContinue()
    await fillCustomer()
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar agendamento' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Esse horário acabou de ser ocupado')
    expect(screen.getByText('Escolha o dia')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '23:59' })).not.toBeInTheDocument()
  })
})

describe('Booking - agendamento futuro no mesmo número', () => {
  const duplicate = new ApiError('Este número já tem agendamento futuro nesta clínica.', 409, {
    code: 'HAS_FUTURE_APPOINTMENT',
    existingCount: 1,
  })

  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrap())
    vi.mocked(bookingService.availability).mockResolvedValue(availability())
    vi.mocked(bookingService.quote).mockResolvedValue(NO_DISCOUNT)
    vi.mocked(bookingService.createAppointment)
      .mockReset()
      .mockRejectedValueOnce(duplicate)
      .mockResolvedValue({ final_price_cents: 15000 } as Appointment)
  })

  async function submit() {
    renderBooking()
    await screen.findByText('Escolha o dia')
    await chooseSlotAndContinue()
    await fillCustomer()
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar agendamento' }))
    return screen.findByRole('dialog', { name: 'Você já tem agendamento' })
  }

  it('avisa e, confirmando, cria com confirmDuplicate', async () => {
    const dialog = await submit()
    expect(dialog).toHaveTextContent('Este número já tem um agendamento futuro')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Manter os dois' }))

    expect(await screen.findByText('Agendamento confirmado!')).toBeInTheDocument()
    const calls = vi.mocked(bookingService.createAppointment).mock.calls
    expect(calls).toHaveLength(2)
    expect(calls[0][1]).not.toHaveProperty('confirmDuplicate')
    expect(calls[1][1]).toEqual({ ...calls[0][1], confirmDuplicate: true })
  })

  it('"Voltar" fecha o aviso sem criar nada e mantém os dados', async () => {
    const dialog = await submit()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Voltar' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('Seus dados')).toBeInTheDocument()
    expect(bookingService.createAppointment).toHaveBeenCalledTimes(1)
  })
})

describe('Booking - desconto progressivo', () => {
  const AREAS = ['Axilas', 'Buço', 'Perna'].map((name, i) => ({
    service_area_id: `sa${i}`,
    service_id: 'svc-1',
    area_id: `a${i}`,
    area_name: name,
    display_order: i,
    duration_minutes: 10,
    price_cents: 10000,
  }))

  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue({
      ...bootstrap(),
      serviceAreas: AREAS,
      discountTiers: [
        { minAreas: 2, maxAreas: 3, pct: 10 },
        { minAreas: 4, maxAreas: null, pct: 20 },
      ],
    })
    vi.mocked(bookingService.availability).mockResolvedValue(availability())
    vi.mocked(bookingService.quote).mockImplementation(async (_c, cart) => ({
      ...NO_DISCOUNT,
      areaCount: cart.serviceAreaPairs.length,
    }))
  })

  it('anuncia as faixas antes da escolha e diz quanto falta para a próxima', async () => {
    renderBooking()
    expect(
      await screen.findByText(/2 a 3 áreas: 10% off · 4 ou mais áreas: 20% off/)
    ).toBeInTheDocument()
    expect(screen.queryByText(/Falta/)).not.toBeInTheDocument()

    await userEvent.click(screen.getByLabelText(/Axilas/))
    expect(await screen.findByText('Falta 1 área para 10% de desconto')).toBeInTheDocument()

    await userEvent.click(screen.getByLabelText(/Buço/))
    expect(await screen.findByText('Faltam 2 áreas para 20% de desconto')).toBeInTheDocument()
  })

  it('clínica sem faixas não anuncia nada', async () => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue({ ...bootstrap(), serviceAreas: AREAS })
    renderBooking()
    await screen.findByText('Selecione as áreas de tratamento')
    expect(screen.queryByText(/Desconto progressivo/)).not.toBeInTheDocument()
  })
})
