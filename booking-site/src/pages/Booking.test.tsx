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
import { guardaSessaoVerificada, limpaSessaoVerificada } from '@/utils/sessaoVerificada'
import { limpaEnviosRecentes } from '@/utils/enviosDeCodigo'
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
const PHONE = '5511987654321'

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
// Cotação de quem já confirmou o código (celular + token): o preço da pessoa,
// com o motivo, e o estado do cadastro.
const PACIENTE_COMPLETA: Quote = {
  ...NO_DISCOUNT,
  discountPct: 50,
  discountReason: 'personalizado',
  finalPriceCents: 7500,
  cadastro: { conhecido: true, completo: true, faltam: [] },
}
const SEM_CADASTRO: Quote = {
  ...NO_DISCOUNT,
  cadastro: { conhecido: false, completo: false, faltam: ['birth_date', 'cpf', 'email'] },
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

// O backend só honra o celular junto com o token (PRD 061): sem os dois, tabela.
function quotePorCelular(comCelular: Quote) {
  vi.mocked(bookingService.quote).mockImplementation(async (_c, _cart, phone, token) =>
    phone && token ? comCelular : NO_DISCOUNT
  )
}

function mockOtp(paciente: { nome: string; faltam: ('cpf' | 'birth_date' | 'email')[] } | null = null) {
  vi.mocked(bookingService.sendOtp).mockReset().mockResolvedValue({ status: 'SUCCESS' })
  vi.mocked(bookingService.confirmOtp).mockReset().mockResolvedValue({ token: 'tok-1', paciente })
  vi.mocked(bookingService.cadastro).mockReset().mockResolvedValue(paciente ?? { nome: 'Maria', faltam: [] })
}

async function typePhone() {
  await screen.findByText('Seu celular')
  await userEvent.type(screen.getByLabelText(/celular/i), '11987654321')
  await waitFor(() => expect(screen.getByRole('button', { name: 'Continuar' })).toBeEnabled())
  await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
}

async function typeCode(code = '123456') {
  await screen.findByText('Confirme seu celular')
  await userEvent.type(screen.getByLabelText('Código de verificação'), code)
  await userEvent.click(screen.getByRole('button', { name: 'Confirmar' }))
}

async function chooseSlotAndConfirm() {
  await userEvent.click(
    await screen.findByRole('button', { name: new RegExp(`${Number(TODAY.slice(8))} de`) })
  )
  await userEvent.click(await screen.findByRole('button', { name: '23:59' }))
  await userEvent.click(screen.getByRole('button', { name: 'Confirmar agendamento' }))
}

// Paciente com cadastro completo: celular, código, "é você?", datas, confirmar.
async function pacienteAteAsDatas() {
  renderBooking()
  await typePhone()
  await typeCode()
  await userEvent.click(await screen.findByRole('button', { name: 'Sou eu' }))
  await screen.findByText('Escolha o dia')
}

async function fillCadastro() {
  await userEvent.type(screen.getByLabelText(/nome/i), 'Maria Silva')
  await userEvent.type(screen.getByLabelText(/cpf/i), '52998224725')
  await userEvent.type(screen.getByLabelText(/nascimento/i), '31101990')
  await userEvent.type(screen.getByLabelText(/e-mail/i), 'Maria@X.com')
  await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
}

beforeEach(() => {
  limpaSessaoVerificada()
  limpaEnviosRecentes()
})

describe('Booking - serviço único', () => {
  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrap())
    vi.mocked(bookingService.availability).mockResolvedValue(availability())
    vi.mocked(bookingService.quote).mockResolvedValue(NO_DISCOUNT)
  })

  it('pula a etapa de revisão do carrinho e começa pelo celular', async () => {
    renderBooking()

    expect(await screen.findByText('Seu celular')).toBeInTheDocument()
    expect(screen.queryByText('Adicionar outro serviço')).not.toBeInTheDocument()
    // Datas só depois de identificar a pessoa (PRD 061).
    expect(screen.queryByText('Escolha o dia')).not.toBeInTheDocument()
  })

  it('clinica sem profissional cadastrado agenda normalmente', async () => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrap(0))
    renderBooking()

    expect(await screen.findByText('Seu celular')).toBeInTheDocument()
    expect(screen.queryByText(/indisponível no momento/i)).not.toBeInTheDocument()
  })

  it('sem "Voltar" na primeira etapa: não há lista de serviços para onde voltar', async () => {
    renderBooking()

    expect(await screen.findByText('Seu celular')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Voltar' })).not.toBeInTheDocument()
  })

  it('"Continuar" só com celular completo', async () => {
    renderBooking()
    await screen.findByText('Seu celular')
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/celular/i), '119876543')
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/celular/i), '21')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Continuar' })).toBeEnabled())
  })

  it('não mostra duração em nenhum lugar', async () => {
    renderBooking()
    await screen.findByText('Seu celular')
    expect(screen.queryByText(/\d+\s?min\b/)).not.toBeInTheDocument()
  })
})

describe('Booking - paciente conhecida (PRD 061)', () => {
  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrap(2))
    vi.mocked(bookingService.availability).mockResolvedValue(availability())
    quotePorCelular(PACIENTE_COMPLETA)
    vi.mocked(bookingService.createAppointment)
      .mockReset()
      .mockResolvedValue({ final_price_cents: 7500 } as Appointment)
    mockOtp({ nome: 'Maria', faltam: [] })
  })

  it('o desconto dela aparece só depois do código, antes de qualquer data', async () => {
    renderBooking()
    await screen.findByText('Seu celular')
    expect(screen.queryByText(/Desconto/)).not.toBeInTheDocument()

    await userEvent.type(screen.getByLabelText(/celular/i), '11987654321')
    // Digitar o número não revela nada: a cotação continua sem celular.
    expect(screen.queryByText(/Desconto/)).not.toBeInTheDocument()
    expect(bookingService.quote).not.toHaveBeenCalledWith('c1', expect.anything(), PHONE, expect.anything())
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
    await typeCode()

    expect(await screen.findByText(/É você\?/)).toBeInTheDocument()
    // Verificada, a pessoa pode saber o motivo do próprio desconto.
    expect(await screen.findByText(/Desconto · Desconto especial \(50%\)/)).toBeInTheDocument()
    expect(screen.getByText('Valor final')).toBeInTheDocument()
    expect(screen.queryByText('Escolha o dia')).not.toBeInTheDocument()
    expect(bookingService.quote).toHaveBeenLastCalledWith(
      'c1',
      { serviceIds: ['svc-1'], serviceAreaPairs: [] },
      PHONE,
      'tok-1'
    )
  })

  it('cotação com token vencido (401) derruba a sessão e refaz o código', async () => {
    vi.mocked(bookingService.quote).mockImplementation(async (_c, _cart, phone, token) => {
      if (phone && token) throw new ApiError('Verificação por WhatsApp expirada.', 401, { code: 'TOKEN_INVALIDO' })
      return NO_DISCOUNT
    })
    renderBooking()
    await typePhone()
    await typeCode()

    expect(await screen.findByText('Confirme seu celular')).toBeInTheDocument()
    // O código anterior saiu há segundos: não manda outro, oferece o reenvio com espera.
    expect(bookingService.sendOtp).toHaveBeenCalledTimes(1)
    expect(screen.getByRole('button', { name: /Reenviar código em \d+s/ })).toBeDisabled()
    expect(screen.queryByText(/É você\?/)).not.toBeInTheDocument()
  })

  it('código logo após o celular, depois "é você?", depois as datas; confirmar não pede outro código', async () => {
    renderBooking()
    await typePhone()

    expect(await screen.findByText('Confirme seu celular')).toBeInTheDocument()
    expect(screen.getByText('(11) 98765-4321')).toBeInTheDocument()
    expect(bookingService.sendOtp).toHaveBeenCalledWith('c1', PHONE)
    // Antes do código, nenhum nome na tela.
    expect(screen.queryByText(/Maria/)).not.toBeInTheDocument()

    await typeCode()
    expect(bookingService.confirmOtp).toHaveBeenCalledWith('c1', PHONE, '123456')
    expect(await screen.findByText(/É você\?/)).toBeInTheDocument()
    expect(screen.getByText('Maria')).toBeInTheDocument()
    expect(screen.queryByLabelText(/cpf/i)).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Sou eu' }))
    // Cadastro completo: nada a gravar antes das datas.
    expect(bookingService.cadastro).not.toHaveBeenCalled()
    expect(await screen.findByText('Escolha o dia')).toBeInTheDocument()
    // A lateral mostra quem agenda.
    expect(screen.getByText('(11) 98765-4321', { exact: false })).toBeInTheDocument()

    await chooseSlotAndConfirm()

    expect(await screen.findByText('Agendamento confirmado!')).toBeInTheDocument()
    expect(bookingService.sendOtp).toHaveBeenCalledTimes(1)
    const payload = vi.mocked(bookingService.createAppointment).mock.calls[0][1]
    expect(payload).not.toHaveProperty('professionalId')
    expect(payload).toEqual({
      serviceIds: ['svc-1'],
      serviceAreaPairs: [],
      phone: PHONE,
      fullName: 'Maria',
      date: TODAY,
      time: '23:59',
      token: 'tok-1',
    })
  })

  it('"Não sou eu" volta ao celular e limpa o nome', async () => {
    renderBooking()
    await typePhone()
    await typeCode()
    await screen.findByText(/É você\?/)

    await userEvent.click(screen.getByRole('button', { name: 'Não sou eu' }))

    expect(await screen.findByText('Seu celular')).toBeInTheDocument()
    expect(screen.queryByText('Maria')).not.toBeInTheDocument()
    expect(screen.getByLabelText(/celular/i)).toHaveValue('')
    expect(bookingService.createAppointment).not.toHaveBeenCalled()
  })

  it('cadastro incompleto: "Sou eu" pede só o que falta e grava antes das datas', async () => {
    mockOtp({ nome: 'Maria', faltam: ['cpf'] })
    renderBooking()
    await typePhone()
    await typeCode()
    await userEvent.click(await screen.findByRole('button', { name: 'Sou eu' }))

    expect(await screen.findByLabelText(/cpf/i)).toBeInTheDocument()
    expect(screen.queryByLabelText(/nascimento/i)).not.toBeInTheDocument()
    expect(screen.queryByLabelText(/nome/i)).not.toBeInTheDocument()

    await userEvent.type(screen.getByLabelText(/cpf/i), '52998224725')
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))

    await waitFor(() => expect(bookingService.cadastro).toHaveBeenCalled())
    expect(vi.mocked(bookingService.cadastro).mock.calls[0][1]).toEqual({
      phone: PHONE,
      token: 'tok-1',
      fullName: undefined,
      cpf: '52998224725',
      birthDate: undefined,
      email: undefined,
    })
    expect(await screen.findByText('Escolha o dia')).toBeInTheDocument()
  })

  it('"Voltar" na etapa do código devolve o celular sem criar nada', async () => {
    renderBooking()
    await typePhone()
    await screen.findByText('Confirme seu celular')

    await userEvent.click(screen.getByRole('button', { name: /voltar/i }))

    expect(await screen.findByText('Seu celular')).toBeInTheDocument()
    expect(screen.getByLabelText(/celular/i)).toHaveValue('(11) 98765-4321')
    expect(bookingService.createAppointment).not.toHaveBeenCalled()
  })

  it('código já confirmado nesta aba: pula o código e vai direto ao "é você?"', async () => {
    guardaSessaoVerificada(PHONE, 'tok-guardado')
    vi.mocked(bookingService.cadastro).mockResolvedValue({ nome: 'Maria', faltam: [] })
    renderBooking()
    await typePhone()

    expect(await screen.findByText(/É você\?/)).toBeInTheDocument()
    expect(bookingService.sendOtp).not.toHaveBeenCalled()
    // Só phone e token: consulta a ficha sem gravar.
    expect(bookingService.cadastro).toHaveBeenCalledWith('c1', { phone: PHONE, token: 'tok-guardado' })

    await userEvent.click(screen.getByRole('button', { name: 'Sou eu' }))
    await chooseSlotAndConfirm()
    expect(await screen.findByText('Agendamento confirmado!')).toBeInTheDocument()
    expect(vi.mocked(bookingService.createAppointment).mock.calls[0][1]).toMatchObject({ token: 'tok-guardado' })
  })

  it('token vencido (401) ao confirmar pede o código de novo e refaz o pedido', async () => {
    vi.mocked(bookingService.createAppointment)
      .mockReset()
      .mockRejectedValueOnce(new ApiError('Verificação por WhatsApp expirada.', 401, {}))
      .mockResolvedValue({ final_price_cents: 7500 } as Appointment)
    await pacienteAteAsDatas()
    await chooseSlotAndConfirm()

    expect(await screen.findByText('Confirme seu celular')).toBeInTheDocument()
    await typeCode('654321')
    expect(await screen.findByText('Agendamento confirmado!')).toBeInTheDocument()
    expect(bookingService.createAppointment).toHaveBeenCalledTimes(2)
    expect(vi.mocked(bookingService.createAppointment).mock.calls[1][1]).toMatchObject({ token: 'tok-1' })
  })

  it('horário ocupado no meio do caminho (409) fica na agenda com aviso', async () => {
    vi.mocked(bookingService.createAppointment).mockRejectedValue(new ApiError('Conflito de horário', 409))
    await pacienteAteAsDatas()
    await chooseSlotAndConfirm()

    expect(await screen.findByRole('alert')).toHaveTextContent('Esse horário acabou de ser ocupado')
    expect(screen.getByText('Escolha o dia')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '23:59' })).not.toBeInTheDocument()
  })
})

describe('Booking - quem ainda não é paciente (PRD 061)', () => {
  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrap())
    vi.mocked(bookingService.availability).mockResolvedValue(availability())
    quotePorCelular(SEM_CADASTRO)
    vi.mocked(bookingService.createAppointment)
      .mockReset()
      .mockResolvedValue({ final_price_cents: 15000 } as Appointment)
    mockOtp(null)
  })

  it('código logo após o celular; sem ficha, cadastro completo; a ficha nasce ao enviá-lo, antes das datas', async () => {
    renderBooking()
    await typePhone()

    expect(await screen.findByText('Confirme seu celular')).toBeInTheDocument()
    expect(bookingService.sendOtp).toHaveBeenCalledWith('c1', PHONE)
    await typeCode()

    expect(await screen.findByText('Seus dados')).toBeInTheDocument()
    expect(bookingService.cadastro).not.toHaveBeenCalled()
    // O celular já foi digitado: o campo não repete.
    expect(screen.queryByLabelText(/celular/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/É você\?/)).not.toBeInTheDocument()

    await fillCadastro()

    await waitFor(() => expect(bookingService.cadastro).toHaveBeenCalled())
    expect(vi.mocked(bookingService.cadastro).mock.calls[0][1]).toEqual({
      phone: PHONE,
      token: 'tok-1',
      fullName: 'Maria Silva',
      cpf: '52998224725',
      birthDate: '1990-10-31',
      email: 'Maria@X.com',
    })
    expect(await screen.findByText('Escolha o dia')).toBeInTheDocument()

    await chooseSlotAndConfirm()
    expect(await screen.findByText('Agendamento confirmado!')).toBeInTheDocument()
    const payload = vi.mocked(bookingService.createAppointment).mock.calls[0][1]
    expect(payload).toMatchObject({ phone: PHONE, fullName: 'Maria Silva', token: 'tok-1' })
    // O cadastro já foi gravado pela rota própria: a criação não repete os campos.
    expect(payload.cpf).toBeUndefined()
    expect(payload.birthDate).toBeUndefined()
    expect(payload.email).toBeUndefined()
    expect(screen.getByText(/\(11\) 98765-4321/)).toBeInTheDocument()
  })

  it('CPF de outro paciente: volta ao cadastro com a mensagem do servidor', async () => {
    vi.mocked(bookingService.cadastro).mockRejectedValue(
      new ApiError('Este CPF já está cadastrado com outro celular. Fale com a clínica.', 409, {
        code: 'CPF_EM_USO',
      })
    )
    renderBooking()
    await typePhone()
    await typeCode()
    await screen.findByText('Seus dados')
    await fillCadastro()

    expect(await screen.findByRole('alert')).toHaveTextContent('Este CPF já está cadastrado com outro celular')
    expect(screen.getByText('Seus dados')).toBeInTheDocument()
    expect(screen.queryByText('Escolha o dia')).not.toBeInTheDocument()
    expect(bookingService.createAppointment).not.toHaveBeenCalled()
  })

  it('"Voltar" no cadastro devolve o celular; seguir com o mesmo número não pede outro código', async () => {
    renderBooking()
    await typePhone()
    await typeCode()
    await screen.findByText('Seus dados')
    await userEvent.click(screen.getByRole('button', { name: /voltar/i }))
    expect(await screen.findByText('Seu celular')).toBeInTheDocument()

    vi.mocked(bookingService.cadastro).mockResolvedValueOnce(null)
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(await screen.findByText('Seus dados')).toBeInTheDocument()
    expect(bookingService.sendOtp).toHaveBeenCalledTimes(1)
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
    quotePorCelular(PACIENTE_COMPLETA)
    vi.mocked(bookingService.createAppointment)
      .mockReset()
      .mockRejectedValueOnce(conflito)
      .mockResolvedValue({ final_price_cents: 15000 } as Appointment)
    mockOtp({ nome: 'Maria', faltam: [] })
  })

  async function submit() {
    await pacienteAteAsDatas()
    await chooseSlotAndConfirm()
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
    expect(screen.getByText('Escolha o dia')).toBeInTheDocument()
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

  it('o "Continuar" fica no rodapé com a contagem de áreas e leva ao celular', async () => {
    renderBooking()
    expect(await screen.findByText('Escolha ao menos uma área')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Continuar' })).toBeDisabled()

    await userEvent.click(screen.getByLabelText(/Axilas/))
    await userEvent.click(screen.getByLabelText(/Buço/))

    expect(await screen.findByText('2 áreas selecionadas')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Continuar' }))
    expect(await screen.findByText('Seu celular')).toBeInTheDocument()
    // Com áreas há para onde voltar.
    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))
    expect(await screen.findByText('Selecione as áreas de tratamento')).toBeInTheDocument()
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
    quotePorCelular(PACIENTE_COMPLETA)
    vi.mocked(bookingService.createAppointment)
      .mockReset()
      .mockRejectedValueOnce(pergunta)
      .mockResolvedValue({ final_price_cents: 15000 } as Appointment)
    mockOtp({ nome: 'Maria', faltam: [] })
  })

  async function submit() {
    await pacienteAteAsDatas()
    await chooseSlotAndConfirm()
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
    expect(screen.getByText('Escolha o dia')).toBeInTheDocument()
    expect(bookingService.createAppointment).toHaveBeenCalledTimes(1)
  })
})
