/**
 * O histórico abre o histórico (PRD 042).
 *
 * O que se protege: vindo da agenda, a tela NÃO abre o formulário por cima -
 * era isso que escondia o parâmetro da última sessão, que é a pergunta que
 * justifica esta tela existir. O formulário fica a um clique.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HistoricoDeSessao } from './HistoricoDeSessao'
import type { ListaDeRegistros, RegistroDeSessao, SessaoSemRegistro } from '@/types'

let consulta: {
  data?: ListaDeRegistros
  isLoading: boolean
  isError: boolean
  refetch: () => void
} = { isLoading: false, isError: false, refetch: vi.fn() }

vi.mock('@/hooks/useSessionRecords', () => ({
  useSessionRecords: () => consulta,
  useDeleteSessionRecord: () => ({ mutate: vi.fn(), isPending: false }),
  useCreateSessionRecord: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateSessionRecord: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))
vi.mock('@/hooks/useAreas', () => ({ useClinicAreas: () => ({ data: [] }) }))
vi.mock('@/hooks/useProtocoloLaser', () => ({
  useProtocoloLaser: () => ({ data: { parameters: [], area_map: [] } }),
}))
vi.mock('@/hooks/useProfessionals', () => ({ useProfessionals: () => ({ data: [] }) }))

function registro(over: Partial<RegistroDeSessao> = {}): RegistroDeSessao {
  return {
    id: 'r1',
    appointment_id: 'a1',
    session_date: '2026-11-03',
    professional_id: null,
    professional_name: 'Camila',
    tanned_skin: false,
    skin_type_snapshot: 'BRANCA',
    notes: null,
    applications: [],
    edit_count: 0,
    version: 1,
    created_at: '2026-11-03T12:00:00Z',
    ...over,
  } as RegistroDeSessao
}

function sessao(over: Partial<SessaoSemRegistro> = {}): SessaoSemRegistro {
  return {
    id: 'a9',
    appointment_date: '2026-11-08',
    start_time: '09:00:00',
    areas: 'Axila',
    ...over,
  }
}

function monta(data: Partial<ListaDeRegistros>) {
  consulta = {
    data: {
      status: 'SUCCESS',
      patient: { id: 'p1', name: 'Ana Clara', phone: '5511999990000', skin_type: 'BRANCA' },
      records: [],
      appointments_without_record: [],
      ...data,
    } as ListaDeRegistros,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  }
  render(<HistoricoDeSessao patientId="p1" skinType="BRANCA" />)
}

beforeEach(() => vi.clearAllMocks())
afterEach(cleanup)

describe('HistoricoDeSessao', () => {
  it('abre sem o formulário, mesmo havendo sessão sem registro', () => {
    monta({ records: [registro()], appointments_without_record: [sessao()] })

    expect(screen.queryByText('Novo registro de sessão')).toBeNull()
    expect(screen.getByRole('button', { name: '+ Novo registro' })).toBeInTheDocument()
  })

  it('o formulário fica a um clique', async () => {
    monta({ records: [registro()], appointments_without_record: [sessao()] })

    await userEvent.click(screen.getByRole('button', { name: '+ Novo registro' }))
    expect(screen.getByText('Novo registro de sessão')).toBeInTheDocument()
  })

  it('a sessão sem registro aparece como opção dentro do formulário', async () => {
    monta({ records: [registro()], appointments_without_record: [sessao({ areas: 'Axila, Virilha' })] })

    await userEvent.click(screen.getByRole('button', { name: '+ Novo registro' }))
    expect(screen.getByText('Axila, Virilha')).toBeInTheDocument()
    expect(screen.getAllByRole('radio').length).toBeGreaterThan(1)
  })

  it('paciente sem registro nenhum ainda assim não abre o formulário sozinha', () => {
    // O estado vazio convida com um botão; abrir direto seria o mesmo defeito
    // em outra porta.
    monta({ records: [], appointments_without_record: [sessao()] })

    expect(screen.queryByText('Novo registro de sessão')).toBeNull()
    expect(screen.getByRole('button', { name: 'Registrar a sessão' })).toBeInTheDocument()
  })
})
