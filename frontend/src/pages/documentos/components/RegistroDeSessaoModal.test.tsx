/**
 * Escolher a sessão monta as áreas (PRD 042).
 *
 * É o pedido do André em palavras de teste: a aplicadora escolhe a data e as
 * caixas das áreas aparecem preenchidas, em vez de ela adicionar uma a uma.
 * Inclui a área composta, que vira duas aplicações.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
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
  useProfessionals: () => ({
    data: [
      { id: 'pr1', name: 'Camila' },
      { id: 'pr2', name: 'Janaína' },
    ],
  }),
}))
const clinica = vi.hoisted(() => ({ padrao: null as string | null }))
vi.mock('@/hooks/useClinic', () => ({
  useClinic: () => ({ data: { default_professional_id: clinica.padrao } }),
}))
vi.mock('@/hooks/useSessionRecords', () => ({
  useCreateSessionRecord: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useUpdateSessionRecord: () => ({ mutateAsync: vi.fn(), isPending: false }),
}))

function sessao(over: Partial<SessaoSemRegistro> = {}): SessaoSemRegistro {
  return { id: 'a1', appointment_date: '2026-11-08', start_time: '09:00:00', areas: 'Axila', ...over }
}

function monta(sessoes: SessaoSemRegistro[], agendamentoDeOrigem?: string | null) {
  render(
    <RegistroDeSessaoModal
      patientId="p1"
      skinType="BRANCA"
      areas={AREAS}
      sessoesSemRegistro={sessoes}
      agendamentoDeOrigem={agendamentoDeOrigem}
      onClose={vi.fn()}
    />,
  )
}

beforeEach(() => {
  // Só o Date: userEvent depende dos timers reais.
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-11-10T12:00:00'))
})

afterEach(() => {
  clinica.padrao = null
  cleanup()
  vi.useRealTimers()
})

/**
 * Uma aplicação montada é uma caixa com botão "Remover <área>". Mirar nisso, e
 * não no texto da área: a opção do select também mostra as áreas do
 * agendamento, e `getByText('Axila')` casaria com ela sem provar nada.
 */
function areasMontadas(): string[] {
  return screen
    .queryAllByRole('button', { name: /^Remover / })
    .map((b) => (b.getAttribute('aria-label') ?? '').replace('Remover ', ''))
}

function seletor() {
  return screen.getByRole('combobox', { name: /qual sessão/i }) as HTMLSelectElement
}

function opcoes(): string[] {
  return Array.from(seletor().options).map((o) => o.textContent ?? '')
}

describe('escolher a sessão monta as áreas', () => {
  it('a pendente mais recente já vem escolhida, com as áreas e a data', async () => {
    monta([sessao({ areas: 'Axila' })])

    await waitFor(() => expect(areasMontadas()).toEqual(['Axila']))
    // Fluência sugerida para Axila/SHR/pele branca, sem ela digitar nada.
    expect(screen.getByDisplayValue('12')).toBeInTheDocument()
    expect(screen.getByLabelText('Data')).toHaveValue('2026-11-08')
  })

  it('área composta vira DUAS aplicações', async () => {
    monta([sessao({ areas: 'Virilha Completa + ânus' })])

    await waitFor(() => expect(areasMontadas()).toEqual(['Virilha', 'Perianal']))
  })

  it('duas áreas no agendamento, uma composta, viram três aplicações', async () => {
    monta([sessao({ areas: 'Axila, Virilha Completa + ânus' })])

    await waitFor(() => expect(areasMontadas()).toEqual(['Axila', 'Virilha', 'Perianal']))
  })

  it('trocar de sessão SUBSTITUI as áreas, não acumula', async () => {
    monta([
      sessao({ id: 'a1', areas: 'Axila' }),
      sessao({ id: 'a2', appointment_date: '2026-10-20', areas: 'Virilha Completa + ânus' }),
    ])
    await waitFor(() => expect(areasMontadas()).toEqual(['Axila']))

    await userEvent.selectOptions(seletor(), 'a2')
    expect(areasMontadas()).toEqual(['Virilha', 'Perianal'])
  })

  it('"Registrar manual" é escolhível e não muda a escolha de volta sozinho', async () => {
    monta([sessao()])
    await waitFor(() => expect(areasMontadas()).toEqual(['Axila']))

    await userEvent.selectOptions(seletor(), 'manual')
    expect(seletor().value).toBe('manual')
  })
})

describe('sessão de origem (vindo da agenda)', () => {
  it('a sessão futura da agenda vem escolhida, com data e áreas', async () => {
    monta(
      [
        sessao({ id: 'a1', appointment_date: '2026-11-08', areas: 'Axila' }),
        sessao({ id: 'a2', appointment_date: '2026-11-19', areas: 'Virilha Completa + ânus' }),
      ],
      'a2',
    )

    await waitFor(() => expect(seletor().value).toBe('a2'))
    expect(areasMontadas()).toEqual(['Virilha', 'Perianal'])
    expect(screen.getByLabelText('Data')).toHaveValue('2026-11-19')
  })

  it('a origem vence a pendente mais recente até hoje', async () => {
    monta(
      [
        sessao({ id: 'a1', appointment_date: '2026-11-08' }),
        sessao({ id: 'a2', appointment_date: '2026-10-01' }),
      ],
      'a2',
    )

    await waitFor(() => expect(seletor().value).toBe('a2'))
  })

  it('origem que já não está pendente cai na mais recente até hoje', async () => {
    monta(
      [
        sessao({ id: 'a1', appointment_date: '2026-11-08' }),
        sessao({ id: 'a2', appointment_date: '2026-11-19' }),
      ],
      'inexistente',
    )

    await waitFor(() => expect(seletor().value).toBe('a1'))
  })
})

describe('opções do seletor', () => {
  it('data brasileira, da mais próxima de hoje para a mais antiga, manual por último', () => {
    monta([
      sessao({ id: 'a2', appointment_date: '2026-10-20', areas: 'Virilha Completa + ânus' }),
      sessao({ id: 'a1', appointment_date: '2026-11-08', areas: 'Axila' }),
    ])

    expect(opcoes()).toEqual([
      '08/11/2026 · 09:00 · Axila',
      '20/10/2026 · 09:00 · Virilha Completa + ânus',
      'Registrar manual',
    ])
  })

  it('sessão de hoje entra e é a pré-selecionada, mesmo com horário depois de agora', async () => {
    monta([
      sessao({ id: 'a1', appointment_date: '2026-11-08' }),
      sessao({ id: 'a2', appointment_date: '2026-11-10', start_time: '18:00:00' }),
    ])

    await waitFor(() => expect(seletor().value).toBe('a2'))
  })

  it('sessão futura aparece na lista, mas não é a pré-selecionada', async () => {
    monta([
      sessao({ id: 'a1', appointment_date: '2026-11-08' }),
      sessao({ id: 'a2', appointment_date: '2026-11-11' }),
    ])

    expect(opcoes()).toEqual([
      '11/11/2026 · 09:00 · Axila',
      '08/11/2026 · 09:00 · Axila',
      'Registrar manual',
    ])
    await waitFor(() => expect(seletor().value).toBe('a1'))
  })

  it('só com sessão futura, o seletor aparece em "Registrar manual", sem montar áreas', () => {
    // Paciente com um único agendamento confirmado, daqui a dois dias: o
    // seletor sumia, e a aplicadora não tinha como vincular a sessão.
    monta([sessao({ id: 'a1', appointment_date: '2026-11-12', areas: 'Axila' })])

    expect(opcoes()).toEqual(['12/11/2026 · 09:00 · Axila', 'Registrar manual'])
    expect(seletor().value).toBe('manual')
    expect(areasMontadas()).toEqual([])
  })

  it('escolher a sessão futura monta data e áreas', async () => {
    monta([sessao({ id: 'a1', appointment_date: '2026-11-12', areas: 'Axila' })])

    await userEvent.selectOptions(seletor(), 'a1')

    expect(areasMontadas()).toEqual(['Axila'])
    expect(screen.getByLabelText('Data')).toHaveValue('2026-11-12')
  })

  it('propõe a profissional padrão da clínica e deixa trocar', async () => {
    clinica.padrao = 'pr2'
    monta([sessao()])

    const profissional = screen.getByLabelText('Profissional')
    expect(profissional).toHaveValue('pr2')

    await userEvent.selectOptions(profissional, 'pr1')
    expect(profissional).toHaveValue('pr1')
  })

  it('sem padrão na clínica, o seletor começa em "Não informado"', () => {
    clinica.padrao = null
    monta([sessao()])

    expect(screen.getByLabelText('Profissional')).toHaveValue('')
  })

  it('sem nenhuma pendente, não mostra o seletor', () => {
    monta([])

    expect(screen.queryByRole('combobox', { name: /qual sessão/i })).toBeNull()
  })
})
