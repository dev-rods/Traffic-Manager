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

// Código sempre antes de confirmar (PRD 056): "Confirmar agendamento" leva à
// etapa do código; digitar o código cria com o token.
async function confirmWithCode() {
  await userEvent.click(screen.getByRole('button', { name: 'Confirmar agendamento' }))
  await screen.findByText('Confirme seu celular')
  await userEvent.type(screen.getByLabelText('Código de verificação'), '123456')
  await userEvent.click(screen.getByRole('button', { name: 'Confirmar' }))
}

function mockOtp() {
  vi.mocked(bookingService.sendOtp).mockReset().mockResolvedValue({ status: 'SUCCESS' })
  vi.mocked(bookingService.confirmOtp).mockReset().mockResolvedValue('tok-1')
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

  it('clinica sem profissional cadastrado agenda normalmente', async () => {
    // O horario e da clinica inteira e o backend grava o agendamento sem
    // profissional; bloquear aqui deixava a clinica nova fora do site a toa.
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrap(0))
    renderBooking()

    expect(await screen.findByText('Escolha o dia')).toBeInTheDocument()
    expect(screen.queryByText(/indisponível no momento/i)).not.toBeInTheDocument()
  })

  it('sem "Voltar" na primeira etapa: não há lista de serviços para onde voltar', async () => {
    renderBooking()

    expect(await screen.findByText('Escolha o dia')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Voltar' })).not.toBeInTheDocument()
  })

  it('"Voltar" reaparece nas etapas seguintes e volta uma etapa', async () => {
    renderBooking()
    await screen.findByText('Escolha o dia')
    await chooseSlotAndContinue()

    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))

    expect(await screen.findByText('Escolha o dia')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Voltar' })).not.toBeInTheDocument()
  })

  it('pede a agenda pelo carrinho - a duração é calculada pelo backend', async () => {
    renderBooking()
    await screen.findByText('Escolha o dia')
    const [clinicId, cart] = vi.mocked(bookingService.availability).mock.calls[0]
    expect(clinicId).toBe('c1')
    expect(cart).toEqual({ serviceIds: ['svc-1'], serviceAreaPairs: [] })
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
    mockOtp()
  })

  it('com vários profissionais não pede pra escolher - o backend atribui', async () => {
    renderBooking()
    expect(await screen.findByText('Escolha o dia')).toBeInTheDocument()
    expect(screen.queryByText(/profissional/i)).not.toBeInTheDocument()

    await chooseSlotAndContinue()
    await fillCustomer()
    await confirmWithCode()

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
      token: 'tok-1',
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
    mockOtp()
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
    await confirmWithCode()

    expect(await screen.findByRole('alert')).toHaveTextContent('Esse horário acabou de ser ocupado')
    expect(screen.getByText('Escolha o dia')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '23:59' })).not.toBeInTheDocument()
  })
})

describe('Booking - cadastro de quem ainda não é paciente (PRD 032)', () => {
  const SEM_CADASTRO: Quote = {
    ...NO_DISCOUNT,
    cadastro: { completo: false, faltam: ['birth_date', 'cpf', 'email'] },
  }

  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrap())
    vi.mocked(bookingService.availability).mockResolvedValue(availability())
    vi.mocked(bookingService.createAppointment).mockResolvedValue({
      final_price_cents: 15000,
    } as Appointment)
    mockOtp()
  })

  it('número novo: os campos aparecem depois do celular e vão no payload normalizados', async () => {
    vi.mocked(bookingService.quote).mockImplementation(async (_c, _cart, phone) =>
      phone ? SEM_CADASTRO : NO_DISCOUNT
    )
    renderBooking()
    await screen.findByText('Escolha o dia')
    await chooseSlotAndContinue()

    // Antes do celular, nada de cadastro na tela.
    expect(screen.queryByLabelText(/cpf/i)).not.toBeInTheDocument()
    await fillCustomer()

    await userEvent.type(await screen.findByLabelText(/cpf/i), '52998224725')
    await userEvent.type(screen.getByLabelText(/nascimento/i), '31101990')
    await userEvent.type(screen.getByLabelText(/e-mail/i), 'Maria@X.com')
    await confirmWithCode()

    await waitFor(() => expect(bookingService.createAppointment).toHaveBeenCalled())
    const calls = vi.mocked(bookingService.createAppointment).mock.calls
    const payload = calls[calls.length - 1][1]
    expect(payload).toMatchObject({ cpf: '52998224725', birthDate: '1990-10-31', email: 'Maria@X.com' })
  })

  it('paciente completo: só nome e celular, e nada de cadastro no payload', async () => {
    vi.mocked(bookingService.quote).mockResolvedValue({
      ...NO_DISCOUNT,
      cadastro: { completo: true, faltam: [] },
    })
    renderBooking()
    await screen.findByText('Escolha o dia')
    await chooseSlotAndContinue()
    await fillCustomer()
    expect(screen.queryByLabelText(/cpf/i)).not.toBeInTheDocument()
    await confirmWithCode()

    await waitFor(() => expect(bookingService.createAppointment).toHaveBeenCalled())
    const calls = vi.mocked(bookingService.createAppointment).mock.calls
    const payload = calls[calls.length - 1][1]
    expect(payload.cpf).toBeUndefined()
    expect(payload.birthDate).toBeUndefined()
    expect(payload.email).toBeUndefined()
  })

  it('servidor pediu o cadastro que a tela não mostrou: avisa o que falta', async () => {
    vi.mocked(bookingService.quote).mockResolvedValue(NO_DISCOUNT)
    vi.mocked(bookingService.createAppointment).mockRejectedValue(
      new ApiError('Para a primeira sessão precisamos de CPF, data de nascimento e e-mail.', 400, {
        code: 'CADASTRO_INCOMPLETO',
        faltam: ['cpf', 'email'],
      })
    )
    renderBooking()
    await screen.findByText('Escolha o dia')
    await chooseSlotAndContinue()
    await fillCustomer()
    await confirmWithCode()

    expect(await screen.findByRole('alert')).toHaveTextContent('Precisamos completar seu cadastro: CPF e e-mail.')
  })

  it('CPF de outro paciente: mostra a mensagem do servidor', async () => {
    vi.mocked(bookingService.quote).mockResolvedValue(NO_DISCOUNT)
    vi.mocked(bookingService.createAppointment).mockRejectedValue(
      new ApiError('Este CPF já está cadastrado com outro celular. Fale com a clínica.', 409, {
        code: 'CPF_EM_USO',
      })
    )
    renderBooking()
    await screen.findByText('Escolha o dia')
    await chooseSlotAndContinue()
    await fillCustomer()
    await confirmWithCode()

    expect(await screen.findByRole('alert')).toHaveTextContent('Este CPF já está cadastrado com outro celular')
    // Não é "horário ocupado": continua na tela de dados.
    expect(screen.queryByText('Escolha o dia')).not.toBeInTheDocument()
  })
})

describe('Booking - código antes de confirmar (PRD 056)', () => {
  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrap())
    vi.mocked(bookingService.availability).mockResolvedValue(availability())
    vi.mocked(bookingService.quote).mockResolvedValue(NO_DISCOUNT)
    vi.mocked(bookingService.createAppointment)
      .mockReset()
      .mockResolvedValue({ final_price_cents: 15000 } as Appointment)
    mockOtp()
  })

  it('"Confirmar agendamento" pede o código; só depois cria, com o token', async () => {
    renderBooking()
    await screen.findByText('Escolha o dia')
    await chooseSlotAndContinue()
    await fillCustomer()
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar agendamento' }))

    expect(await screen.findByText('Confirme seu celular')).toBeInTheDocument()
    expect(screen.getByText('(11) 98765-4321')).toBeInTheDocument()
    expect(bookingService.createAppointment).not.toHaveBeenCalled()
    expect(bookingService.sendOtp).toHaveBeenCalledWith('c1', '5511987654321')

    await userEvent.type(screen.getByLabelText('Código de verificação'), '123456')
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar' }))

    expect(await screen.findByText('Agendamento confirmado!')).toBeInTheDocument()
    expect(bookingService.confirmOtp).toHaveBeenCalledWith('c1', '5511987654321', '123456')
    expect(vi.mocked(bookingService.createAppointment).mock.calls[0][1]).toMatchObject({
      phone: '5511987654321',
      token: 'tok-1',
    })
    expect(vi.mocked(bookingService.createAppointment).mock.calls[0][1]).not.toHaveProperty('substituir')
  })

  it('"Voltar" na etapa do código devolve "Seus dados" sem criar nada', async () => {
    renderBooking()
    await screen.findByText('Escolha o dia')
    await chooseSlotAndContinue()
    await fillCustomer()
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar agendamento' }))
    await screen.findByText('Confirme seu celular')

    await userEvent.click(screen.getByRole('button', { name: /voltar/i }))
    expect(screen.getByText('Seus dados')).toBeInTheDocument()
    expect(bookingService.createAppointment).not.toHaveBeenCalled()
  })

  it('token vencido (401) volta para o código e refaz o pedido', async () => {
    vi.mocked(bookingService.createAppointment)
      .mockReset()
      .mockRejectedValueOnce(new ApiError('Verificação por WhatsApp expirada.', 401, {}))
      .mockResolvedValue({ final_price_cents: 15000 } as Appointment)
    renderBooking()
    await screen.findByText('Escolha o dia')
    await chooseSlotAndContinue()
    await fillCustomer()
    await confirmWithCode()

    expect(await screen.findByText('Confirme seu celular')).toBeInTheDocument()
    await userEvent.type(screen.getByLabelText('Código de verificação'), '654321')
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar' }))
    expect(await screen.findByText('Agendamento confirmado!')).toBeInTheDocument()
    expect(bookingService.createAppointment).toHaveBeenCalledTimes(2)
  })
})

describe('Booking - sessão no mesmo mês (PRD 056)', () => {
  const conflito = new ApiError('Você já tem uma sessão nesta clínica neste mês.', 409, {
    code: 'SAME_MONTH_APPOINTMENT',
    existing: { id: 'x1', date: '2026-11-25', time: '14:00', areas: 'Axilas' },
  })

  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrap())
    vi.mocked(bookingService.availability).mockResolvedValue(availability())
    vi.mocked(bookingService.quote).mockResolvedValue(NO_DISCOUNT)
    vi.mocked(bookingService.createAppointment)
      .mockReset()
      .mockRejectedValueOnce(conflito)
      .mockResolvedValue({ final_price_cents: 15000 } as Appointment)
    mockOtp()
  })

  async function submit() {
    renderBooking()
    await screen.findByText('Escolha o dia')
    await chooseSlotAndContinue()
    await fillCustomer()
    await confirmWithCode()
    return screen.findByRole('dialog', { name: 'Você já tem uma sessão este mês' })
  }

  it('avisa qual sessão será substituída e, confirmando, reenvia com substituir', async () => {
    const dialog = await submit()
    expect(dialog).toHaveTextContent('Sua sessão de 25/11/2026 às 14:00 será substituída por')
    expect(within(dialog).getByRole('link', { name: 'Falar no WhatsApp' })).toHaveAttribute(
      'href',
      'https://wa.me/5511999990000'
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Confirmar remarcação' }))

    expect(await screen.findByText('Agendamento remarcado!')).toBeInTheDocument()
    const calls = vi.mocked(bookingService.createAppointment).mock.calls
    expect(calls).toHaveLength(2)
    expect(calls[0][1]).not.toHaveProperty('substituir')
    expect(calls[1][1]).toEqual({ ...calls[0][1], substituir: true })
  })

  it('"Voltar" fecha o aviso sem criar nada; confirmar de novo não pede outro código', async () => {
    const dialog = await submit()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Voltar' }))

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    expect(screen.getByText('Seus dados')).toBeInTheDocument()
    expect(bookingService.createAppointment).toHaveBeenCalledTimes(1)

    await userEvent.click(screen.getByRole('button', { name: 'Confirmar agendamento' }))
    expect(await screen.findByText('Agendamento confirmado!')).toBeInTheDocument()
    expect(bookingService.sendOtp).toHaveBeenCalledTimes(1)
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

  it('o "Continuar" fica no rodapé com a contagem de áreas e o valor', async () => {
    renderBooking()
    expect(await screen.findByText('Escolha ao menos uma área')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeDisabled()

    await userEvent.click(screen.getByLabelText(/Axilas/))
    await userEvent.click(screen.getByLabelText(/Buço/))

    expect(await screen.findByText('2 áreas selecionadas')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeEnabled()
  })

  it('clínica sem faixas não anuncia nada', async () => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue({ ...bootstrap(), serviceAreas: AREAS })
    renderBooking()
    await screen.findByText('Selecione as áreas de tratamento')
    expect(screen.queryByText(/Desconto progressivo/)).not.toBeInTheDocument()
  })
})

describe('Booking - sessão futura em outro mês (PRD 060)', () => {
  const pergunta = new ApiError('Você já tem uma sessão em 10/12.', 409, {
    code: 'OTHER_MONTH_APPOINTMENT',
    existing: { id: 'x2', date: '2026-12-10', time: '09:00', areas: 'Virilha' },
  })

  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrap())
    vi.mocked(bookingService.availability).mockResolvedValue(availability())
    vi.mocked(bookingService.quote).mockResolvedValue(NO_DISCOUNT)
    vi.mocked(bookingService.createAppointment)
      .mockReset()
      .mockRejectedValueOnce(pergunta)
      .mockResolvedValue({ final_price_cents: 15000 } as Appointment)
    mockOtp()
  })

  async function submit() {
    renderBooking()
    await screen.findByText('Escolha o dia')
    await chooseSlotAndContinue()
    await fillCustomer()
    await confirmWithCode()
    return screen.findByRole('dialog', { name: 'Você já tem uma sessão marcada' })
  }

  it('pergunta o que fazer, com a sessão, as áreas e o WhatsApp da clínica', async () => {
    const dialog = await submit()
    expect(dialog).toHaveTextContent('Você já tem uma sessão em 10/12/2026 às 09:00. O que você quer fazer?')
    expect(dialog).toHaveTextContent('Áreas: Virilha')
    expect(within(dialog).getByRole('link', { name: 'Falar no WhatsApp' })).toHaveAttribute(
      'href',
      'https://wa.me/5511999990000'
    )
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    // Não é o diálogo do mesmo mês: nada de "será substituída"
    expect(screen.queryByRole('dialog', { name: 'Você já tem uma sessão este mês' })).not.toBeInTheDocument()
    expect(bookingService.createAppointment).toHaveBeenCalledTimes(1)
  })

  it('"Remarcar essa sessão" reenvia com remarcarExistente e a tela diz remarcado', async () => {
    const dialog = await submit()
    await userEvent.click(within(dialog).getByRole('button', { name: /^Remarcar essa sessão para/ }))

    expect(await screen.findByText('Agendamento remarcado!')).toBeInTheDocument()
    const calls = vi.mocked(bookingService.createAppointment).mock.calls
    expect(calls).toHaveLength(2)
    expect(calls[0][1]).not.toHaveProperty('remarcarExistente')
    expect(calls[0][1]).not.toHaveProperty('maisUma')
    expect(calls[1][1]).toEqual({ ...calls[0][1], remarcarExistente: true })
  })

  it('"Marcar mais uma" reenvia com maisUma e a tela diz confirmado', async () => {
    const dialog = await submit()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Marcar mais uma' }))

    expect(await screen.findByText('Agendamento confirmado!')).toBeInTheDocument()
    const calls = vi.mocked(bookingService.createAppointment).mock.calls
    expect(calls).toHaveLength(2)
    expect(calls[1][1]).toEqual({ ...calls[0][1], maisUma: true })
    expect(calls[1][1]).not.toHaveProperty('remarcarExistente')
  })

  it('"Voltar" fecha a pergunta sem criar nada', async () => {
    const dialog = await submit()
    await userEvent.click(within(dialog).getByRole('button', { name: 'Voltar' }))
    expect(screen.queryByRole('dialog', { name: 'Você já tem uma sessão marcada' })).not.toBeInTheDocument()
    expect(screen.getByText('Seus dados')).toBeInTheDocument()
    expect(bookingService.createAppointment).toHaveBeenCalledTimes(1)
  })
})
