import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { PatientsTable } from './PatientsTable'
import type { PatientWithStats } from '@/types'

/**
 * A troca entre tabela e cards.
 *
 * É fiação: o componente certo pode existir e não ser escolhido, e o defeito
 * aparece só no celular de quem usa - que é onde ninguém está olhando quando
 * roda o teste. Por isso o teste mira a ESCOLHA, e não o conteúdo de cada um.
 */
function telaDe(largura: number) {
  vi.stubGlobal('matchMedia', (q: string) => ({
    media: q,
    matches: largura >= 768,
    addEventListener: () => {},
    removeEventListener: () => {},
  }))
}

const PACIENTE: PatientWithStats = {
  id: 'p1',
  clinic_id: 'c',
  phone: '5511999998888',
  name: 'Beatriz Nogueira',
  gender: 'F',
  cpf: null,
  birth_date: null,
  email: null,
  custom_discount_pct: null,
  skin_type: null,
  created_at: '',
  updated_at: '',
  total_visits: 3,
  last_visit: '2026-09-15',
  next_visit: '2026-09-23',
  total_spent_cents: 58500,
  last_message_at: null,
}

function renderiza() {
  return render(
    <MemoryRouter>
      <PatientsTable
        patients={[PACIENTE]}
        onSelect={vi.fn()}
        onWhatsApp={vi.fn()}
        onPauseBot={vi.fn()}
        onDelete={vi.fn()}
        pausedPhones={new Set()}
        selectedIds={new Set()}
        allSelected={false}
        onToggleSelect={vi.fn()}
        onToggleAll={vi.fn()}
      />
    </MemoryRouter>,
  )
}

beforeEach(() => vi.unstubAllGlobals())
afterEach(cleanup)

describe('PatientsTable', () => {
  it('no desktop continua sendo tabela', () => {
    telaDe(1200)
    const { container } = renderiza()

    expect(container.querySelector('table')).toBeInTheDocument()
  })

  it('no celular vira lista, e não tabela', () => {
    // Nove colunas em 375px só existem dentro de um scroll horizontal, e
    // ninguém rola de lado para ler uma linha.
    telaDe(375)
    const { container } = renderiza()

    expect(container.querySelector('table')).not.toBeInTheDocument()
    expect(container.querySelector('ul')).toBeInTheDocument()
  })

  it('o paciente aparece nos dois modos', () => {
    telaDe(1200)
    renderiza()
    expect(screen.getByText('Beatriz Nogueira')).toBeInTheDocument()
    cleanup()

    telaDe(375)
    renderiza()
    expect(screen.getByText('Beatriz Nogueira')).toBeInTheDocument()
  })

  it('a seleção em lote sobrevive ao celular', () => {
    // As ações em lote dependem do checkbox. Se ele sumisse no card, o
    // recurso existiria na tela e não funcionaria.
    telaDe(375)
    renderiza()

    expect(
      screen.getByRole('checkbox', { name: /Selecionar Beatriz/ }),
    ).toBeInTheDocument()
    expect(screen.getByText(/Selecionar todos desta página/)).toBeInTheDocument()
  })

  it('as ações do dia a dia ficam a um toque no celular', () => {
    telaDe(375)
    renderiza()

    for (const nome of [/WhatsApp/, /Pausar bot/, /Documentos/, /Excluir/]) {
      expect(screen.getByRole(nome.source.includes('Documentos') ? 'link' : 'button', { name: nome })).toBeInTheDocument()
    }
  })
})
