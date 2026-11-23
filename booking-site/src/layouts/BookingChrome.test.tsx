import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BookingLayout } from './BookingLayout'
import { bookingService } from '@/services/booking.service'
import type { BootstrapResponse } from '@/types'

vi.mock('@/services/booking.service')

const BOOTSTRAP: BootstrapResponse = {
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
  services: [],
  professionals: [],
  serviceAreas: [],
  discountTiers: [],
}

function UrlAtual() {
  const { pathname, search } = useLocation()
  return <output data-testid="url">{pathname + search}</output>
}

function monta(url: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/:clinicId" element={<BookingLayout />}>
            <Route index element={<div>Home mockada</div>} />
          </Route>
        </Routes>
        <UrlAtual />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('BookingChrome - link direto para "Meus agendamentos" (PRD 060)', () => {
  beforeEach(() => {
    vi.mocked(bookingService.bootstrap).mockResolvedValue(BOOTSTRAP)
  })

  it('sem o parâmetro o modal fica fechado', async () => {
    monta('/c1')
    expect(await screen.findByText('Home mockada')).toBeInTheDocument()
    expect(screen.queryByRole('dialog', { name: 'Meus agendamentos' })).not.toBeInTheDocument()
  })

  it('?meus=1 abre o modal direto, já pedindo o celular', async () => {
    monta('/c1?meus=1')
    const dialog = await screen.findByRole('dialog', { name: 'Meus agendamentos' })
    expect(dialog).toHaveTextContent('Digite o celular usado para agendar o serviço.')
  })

  it('fechar limpa o parâmetro da URL e mantém o resto', async () => {
    monta('/c1?utm=x&meus=1')
    await screen.findByRole('dialog', { name: 'Meus agendamentos' })
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Meus agendamentos' })).not.toBeInTheDocument()
    expect(screen.getByTestId('url')).toHaveTextContent('/c1?utm=x')
  })

  it('o botão do cabeçalho continua abrindo e fechando sem mexer na URL', async () => {
    monta('/c1')
    await screen.findByText('Home mockada')
    await userEvent.click(screen.getByRole('button', { name: 'Meus agendamentos' }))
    expect(screen.getByRole('dialog', { name: 'Meus agendamentos' })).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog', { name: 'Meus agendamentos' })).not.toBeInTheDocument()
    expect(screen.getByTestId('url')).toHaveTextContent('/c1')
  })
})
