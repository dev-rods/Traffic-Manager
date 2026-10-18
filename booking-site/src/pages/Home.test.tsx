import { useEffect, useState } from 'react'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Home } from './Home'
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

function bootstrapWith(services: Service[]): BootstrapResponse {
  return {
    status: 'SUCCESS',
    clinic: {
      clinic_id: 'c1',
      name: 'Clínica X',
      display_name: null,
      logo_url: null,
      favicon_url: null,
      timezone: 'America/Sao_Paulo',
      phone: null,
    },
    services,
    professionals: [{ id: 'p1', name: 'Prof', role: null, photo_url: null }],
    serviceAreas: [],
    discountTiers: [],
  }
}

// Simula o estado de quem clicou "Voltar" vindo da etapa de agendamento: o
// carrinho já chega com o serviço dentro, ANTES do primeiro mount do Home.
// Precisa ser em duas fases - efeitos de filho rodam antes dos do pai, então
// se o Home montasse junto, o efeito dele veria o carrinho ainda vazio.
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

function CartCount() {
  const cart = useCart()
  return <p>Agendamento com {cart.items.length} serviço(s)</p>
}

function renderHome({ preloadCart = false } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const body = preloadCart ? (
    <PreloadCart>
      <Home />
    </PreloadCart>
  ) : (
    <Home />
  )

  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/c1']}>
        <ClinicIdContext.Provider value={{ clinicId: 'c1', basePath: '/c1' }}>
          <CartProvider>
            <Routes>
              <Route path="/c1" element={body} />
              <Route path="/c1/agendar" element={<CartCount />} />
            </Routes>
          </CartProvider>
        </ClinicIdContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('Home - serviço único', () => {
  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(bootstrapWith([SERVICE]))
  })

  it('com o serviço já no carrinho, vai direto ao agendamento sem duplicá-lo', async () => {
    // A lista com um item só e "Adicionado" confundia (e, quando o
    // redirecionamento dependia do carrinho vazio, a tela travava no spinner).
    renderHome({ preloadCart: true })

    expect(await screen.findByText('Agendamento com 1 serviço(s)')).toBeInTheDocument()
    expect(screen.queryByText('Adicionado')).not.toBeInTheDocument()
  })

  it('com o carrinho vazio, põe o serviço e vai ao agendamento', async () => {
    renderHome()

    expect(await screen.findByText('Agendamento com 1 serviço(s)')).toBeInTheDocument()
  })
})
