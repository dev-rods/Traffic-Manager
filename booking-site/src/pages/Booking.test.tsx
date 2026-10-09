import { useEffect, useState } from 'react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Booking } from './Booking'
import { CartProvider } from '@/store/CartProvider'
import { useCart } from '@/store/useCart'
import { ClinicIdContext } from '@/store/clinicIdContext'
import { bookingService } from '@/services/booking.service'
import type { BootstrapResponse, Service } from '@/types'

vi.mock('@/services/booking.service')

const SERVICE: Service = {
  id: 'svc-1',
  name: 'Depilação a Laser',
  duration_minutes: 20,
  price_cents: 15000,
  description: null,
}

function bootstrapSingleServiceSingleProfessional(): BootstrapResponse {
  return {
    status: 'SUCCESS',
    clinic: { clinic_id: 'c1', name: 'Clínica X', display_name: null, logo_url: null, favicon_url: null, timezone: 'America/Sao_Paulo' },
    services: [SERVICE],
    professionals: [{ id: 'p1', name: 'Prof', role: null, photo_url: null }],
    serviceAreas: [],
  }
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

describe('Booking - serviço único', () => {
  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrapSingleServiceSingleProfessional())
    vi.mocked(bookingService.weekAvailability).mockResolvedValue({})
  })

  it('pula a etapa de revisão do carrinho e vai direto pro agendamento', async () => {
    renderBooking()

    await waitFor(() => expect(screen.getByLabelText('Semana anterior')).toBeInTheDocument())

    // Não existe "outro serviço" pra escolher - a etapa de revisão do
    // carrinho (e o botão) nem aparecem, o fluxo já começa no agendamento.
    expect(screen.queryByText('Adicionar outro serviço')).not.toBeInTheDocument()
  })

  it('"Voltar" a partir do agendamento sai direto pro início, sem passar pela revisão', async () => {
    renderBooking()

    await waitFor(() => expect(screen.getByLabelText('Semana anterior')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: 'Voltar' }))

    expect(await screen.findByText('Home mockada')).toBeInTheDocument()
  })
})
