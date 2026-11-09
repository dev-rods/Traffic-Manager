/**
 * Escolher a sessão monta as áreas (PRD 042).
 *
 * É o pedido do André em palavras de teste: a aplicadora escolhe a data e as
 * caixas das áreas aparecem preenchidas, em vez de ela adicionar uma a uma.
 * Inclui a área composta, que vira duas aplicações.
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RegistroDeSessaoModal } from './RegistroDeSessaoModal'
import type {
  ClinicArea,
  LigacaoDeArea,
  ParametroDoProtocolo,
  SessaoSemRegistro,
} from '@/types'

const AREAS: ClinicArea[] = [
  { id: 'ar-axila', clinic_id: 'c1', name: 'Axila', display_order: 1, active: true },
  { id: 'ar-virilha', clinic_id: 'c1', name: 'Virilha Completa + ânus', display_order: 2, active: true },
]

// A composta liga a DUAS chaves do protocolo: é o que faz uma área escolhida
// virar duas aplicações.
const MAPA: LigacaoDeArea[] = [
  { area_id: 'ar-axila', area_name: 'Axila', protocol_area_key: 'axila', display_order: 1 },
  { area_id: 'ar-virilha', area_name: 'Virilha Completa + ânus', protocol_area_key: 'virilha', display_order: 1 },
  { area_id: 'ar-virilha', area_name: 'Virilha Completa + ânus', protocol_area_key: 'perianal', display_order: 2 },
]

function parametro(over: Partial<ParametroDoProtocolo>): ParametroDoProtocolo {
  return {
    skin_type: 'BRANCA',
    method: 'SHR',
    protocol_area_key: 'axila',
    protocol_area_name: 'Axila',
    fluence_j: 10,
    energy_kj: null,
    stacks: null,
    passes: 4,
    source: 'PDF',
    ...over,
  }
}

const PARAMETROS: ParametroDoProtocolo[] = [
  parametro({ protocol_area_key: 'axila', protocol_area_name: 'Axila', fluence_j: 12 }),
  parametro({ protocol_area_key: 'virilha', protocol_area_name: 'Virilha', fluence_j: 14 }),
  parametro({ protocol_area_key: 'perianal', protocol_area_name: 'Perianal', fluence_j: 16 }),
]

vi.mock('@/hooks/useProtocoloLaser', () => ({
  useProtocoloLaser: () => ({
    data: { methods: [], parameters: PARAMETROS, area_map: MAPA },
  }),
}))
vi.mock('@/hooks/useProfessionals', () => ({
  useProfessionals: () => ({ data: [{ id: 'pr1', name: 'Camila' }] }),
}))
vi.mock('@/hooks/useSessionRecords', () => ({
  useCreateSessionRecord: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateSessionRecord: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

function sessao(over: Partial<SessaoSemRegistro> = {}): SessaoSemRegistro {
  return { id: 'a1', appointment_date: '2026-11-08', start_time: '09:00:00', areas: 'Axila', ...over }
}

function monta(sessoes: SessaoSemRegistro[]) {
  render(
    <RegistroDeSessaoModal
      patientId="p1"
      skinType="BRANCA"
      areas={AREAS}
      sessoesSemRegistro={sessoes}
      onClose={vi.fn()}
    />,
  )
}

afterEach(cleanup)

/**
 * Uma aplicação montada é uma caixa com botão "Remover <área>". Mirar nisso, e
 * não no texto da área: o rótulo do rádio também mostra as áreas do
 * agendamento, e `getByText('Axila')` casaria com ele sem provar nada.
 */
function areasMontadas(): string[] {
  return screen
    .queryAllByRole('button', { name: /^Remover / })
    .map((b) => (b.getAttribute('aria-label') ?? '').replace('Remover ', ''))
}

describe('escolher a sessão monta as áreas', () => {
  it('nasce sem área nenhuma: nada está escolhido ainda', () => {
    monta([sessao()])
    expect(areasMontadas()).toEqual([])
    expect(screen.getByText(/Nenhuma área ainda/)).toBeInTheDocument()
  })

  it('escolhida a sessão, a área aparece com o parâmetro do protocolo', async () => {
    monta([sessao({ areas: 'Axila' })])

    await userEvent.click(screen.getAllByRole('radio')[0])

    expect(areasMontadas()).toEqual(['Axila'])
    // Fluência sugerida para Axila/SHR/pele branca, sem ela digitar nada.
    expect(screen.getByDisplayValue('12')).toBeInTheDocument()
  })

  it('área composta vira DUAS aplicações', async () => {
    monta([sessao({ areas: 'Virilha Completa + ânus' })])

    await userEvent.click(screen.getAllByRole('radio')[0])

    expect(areasMontadas()).toEqual(['Virilha', 'Perianal'])
  })

  it('duas áreas no agendamento, uma composta, viram três aplicações', async () => {
    monta([sessao({ areas: 'Axila, Virilha Completa + ânus' })])

    await userEvent.click(screen.getAllByRole('radio')[0])

    expect(areasMontadas()).toEqual(['Axila', 'Virilha', 'Perianal'])
  })

  it('trocar de sessão SUBSTITUI as áreas, não acumula', async () => {
    monta([
      sessao({ id: 'a1', areas: 'Axila' }),
      sessao({ id: 'a2', appointment_date: '2026-10-20', areas: 'Virilha Completa + ânus' }),
    ])

    const radios = screen.getAllByRole('radio')
    await userEvent.click(radios[0])
    expect(areasMontadas()).toEqual(['Axila'])

    await userEvent.click(radios[1])
    expect(areasMontadas()).toEqual(['Virilha', 'Perianal'])
  })

  it('"sessão fora do sistema" não monta área alguma', async () => {
    monta([sessao()])

    await userEvent.click(screen.getByRole('radio', { name: /fora do sistema/i }))
    expect(areasMontadas()).toEqual([])
  })

  it('a ordem recebida é preservada: a mais recente primeiro', () => {
    // A ordem vem do backend (`ORDER BY appointment_date DESC`). Se alguém
    // reordenar aqui, a sessão que ela acabou de atender sai do topo.
    monta([
      sessao({ id: 'a1', appointment_date: '2026-11-08' }),
      sessao({ id: 'a2', appointment_date: '2026-10-20' }),
    ])

    const rotulos = screen
      .getAllByRole('radio')
      .map((r) => r.closest('label')?.textContent ?? '')
    expect(rotulos[0]).toContain('2026-11-08')
    expect(rotulos[1]).toContain('2026-10-20')
  })
})
