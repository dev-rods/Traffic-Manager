import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { DocumentosPage } from './DocumentosPage'

vi.mock('@/hooks/useSessionRecords', () => ({
  useSessionRecords: () => ({
    data: { patient: { id: 'p1', name: 'Ana Souza', phone: '5511999990000', skin_type: 'BRANCA' }, records: [] },
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }),
}))
vi.mock('./components/HistoricoDeSessao', () => ({
  HistoricoDeSessao: () => <div>historico aqui</div>,
}))
vi.mock('./components/TermoDeConsentimento', () => ({
  TermoDeConsentimento: ({ patientId }: { patientId: string }) => <div>termo de {patientId}</div>,
}))

function Url() {
  const { search } = useLocation()
  return <output data-testid="url">{search}</output>
}

function renderPage(inicial = '/pacientes/p1/documentos?agendamento=a9') {
  return render(
    <MemoryRouter initialEntries={[inicial]}>
      <Routes>
        <Route
          path="/pacientes/:patientId/documentos"
          element={
            <>
              <DocumentosPage />
              <Url />
            </>
          }
        />
      </Routes>
    </MemoryRouter>
  )
}

describe('DocumentosPage - abas', () => {
  it('abre no histórico e troca para o termo mantendo ?agendamento=', async () => {
    renderPage()
    expect(screen.getByRole('tab', { name: 'Histórico por sessão' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByText('historico aqui')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('tab', { name: 'Termo e anamnese' }))
    expect(screen.getByText('termo de p1')).toBeInTheDocument()
    expect(screen.getByTestId('url')).toHaveTextContent('agendamento=a9')
    expect(screen.getByTestId('url')).toHaveTextContent('doc=termo')

    await userEvent.click(screen.getByRole('tab', { name: 'Histórico por sessão' }))
    expect(screen.getByText('historico aqui')).toBeInTheDocument()
    expect(screen.getByTestId('url')).not.toHaveTextContent('doc=')
  })

  it('?doc=termo abre direto na aba do termo', () => {
    renderPage('/pacientes/p1/documentos?doc=termo')
    expect(screen.getByRole('tab', { name: 'Termo e anamnese' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByText('termo de p1')).toBeInTheDocument()
  })
})
