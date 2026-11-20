/**
 * Escolher a sessão monta as áreas (PRD 042).
 *
 * É o pedido do André em palavras de teste: a aplicadora escolhe a data e as
 * caixas das áreas aparecem preenchidas, em vez de ela adicionar uma a uma.
 * Inclui a área composta, que vira duas aplicações.
 *
 * Desde o PRD 051 quem monta é o backend (`GET session-applications`); aqui o
 * dublê `backend()` faz a mesma conta que ele, com nome COMERCIAL e o
 * protocolo como subtítulo.
 */
import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RegistroDeSessaoModal } from './RegistroDeSessaoModal'
import type {
  AplicacaoDeSessao,
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
const gravacao = vi.hoisted(() => ({ mutateAsync: vi.fn().mockResolvedValue({}) }))
// O que o GET session-applications devolveria para cada sessão: o dublê faz a
// conta do backend (nome comercial, uma aplicação por chave do mapa).
const backend = vi.hoisted(() => ({
  sessoes: [] as { id: string; areas: string }[],
  falha: false,
}))

vi.mock('@/hooks/useSessionRecords', () => ({
  useCreateSessionRecord: () => ({ mutateAsync: gravacao.mutateAsync, isPending: false }),
  useUpdateSessionRecord: () => ({ mutateAsync: vi.fn(), isPending: false }),
  useAplicacoesDoAgendamento: () => (id: string) => {
    if (backend.falha) return Promise.reject(new Error('rede'))
    const s = backend.sessoes.find((x) => x.id === id)
    const nomes = (s?.areas ?? '').split(',').map((n) => n.trim()).filter(Boolean)
    const out: AplicacaoDeSessao[] = []
    for (const nome of nomes) {
      const area = AREAS.find((a) => a.name === nome)
      const chaves = MAPA.filter((l) => l.area_id === area?.id).map((l) => l.protocol_area_key)
      const desmembrada = chaves.length > 1
      for (const chave of chaves.length ? chaves : [null]) {
        const p = PARAMETROS.find((x) => x.protocol_area_key === chave)
        out.push({
          area_id: area?.id ?? null,
          // PRD 052: parte de composta leva o nome do protocolo e a origem.
          area_name: desmembrada && p ? p.protocol_area_name : nome,
          source_area_name: desmembrada ? nome : null,
          protocol_area_key: chave,
          protocol_area_name: p?.protocol_area_name ?? null,
          method: p ? 'SHR' : null,
          fluence_j: p?.fluence_j ?? null,
          energy_kj: p ? 8 : null,
          stacks: null,
          passes: null,
          display_order: out.length,
        })
      }
    }
    return Promise.resolve(out)
  },
}))

function sessao(over: Partial<SessaoSemRegistro> = {}): SessaoSemRegistro {
  return { id: 'a1', appointment_date: '2026-11-08', start_time: '09:00:00', areas: 'Axila', ...over }
}

function monta(sessoes: SessaoSemRegistro[], agendamentoDeOrigem?: string | null) {
  backend.sessoes = sessoes
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
  backend.falha = false
  gravacao.mutateAsync.mockClear()
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

  it('área composta vira DUAS aplicações, cada parte com o nome do protocolo e a origem (PRD 052)', async () => {
    monta([sessao({ areas: 'Virilha Completa + ânus' })])

    await waitFor(() => expect(areasMontadas()).toEqual(['Virilha', 'Perianal']))
    expect(screen.getAllByText('de: Virilha Completa + ânus')).toHaveLength(2)
    expect(screen.queryByText(/parâmetros de/)).toBeNull()
  })

  it('duas áreas no agendamento, uma composta, viram três aplicações', async () => {
    monta([sessao({ areas: 'Axila, Virilha Completa + ânus' })])

    await waitFor(() => expect(areasMontadas()).toEqual(['Axila', 'Virilha', 'Perianal']))
  })

  it('o nome comercial fica: "Perna Completa" não vira "Meia perna" (PRD 051)', async () => {
    AREAS.push({ id: 'ar-perna', clinic_id: 'c1', name: 'Perna Completa', display_order: 3, active: true })
    MAPA.push({ area_id: 'ar-perna', area_name: 'Perna Completa', protocol_area_key: 'meia_perna', display_order: 1 })
    PARAMETROS.push(parametro({ protocol_area_key: 'meia_perna', protocol_area_name: 'Meia perna', fluence_j: 9 }))
    try {
      monta([sessao({ areas: 'Perna Completa' })])

      await waitFor(() => expect(areasMontadas()).toEqual(['Perna Completa (Meia perna)']))
      expect(screen.getByText('Perna Completa')).toBeInTheDocument()
      expect(screen.getByText('parâmetros de Meia perna')).toBeInTheDocument()
      expect(screen.getByDisplayValue('9')).toBeInTheDocument()
    } finally {
      AREAS.pop()
      MAPA.pop()
      PARAMETROS.pop()
    }
  })

  it('se o backend falhar, avisa e deixa adicionar manualmente', async () => {
    backend.falha = true
    monta([sessao()])

    await waitFor(() =>
      expect(screen.getByText(/Não foi possível carregar as áreas/)).toBeInTheDocument(),
    )
    expect(areasMontadas()).toEqual([])
    expect(screen.getByPlaceholderText('+ Adicionar área')).toBeEnabled()
  })

  it('trocar de sessão SUBSTITUI as áreas, não acumula', async () => {
    monta([
      sessao({ id: 'a1', areas: 'Axila' }),
      sessao({ id: 'a2', appointment_date: '2026-10-20', areas: 'Virilha Completa + ânus' }),
    ])
    await waitFor(() => expect(areasMontadas()).toEqual(['Axila']))

    await userEvent.selectOptions(seletor(), 'a2')
    await waitFor(() => expect(areasMontadas()).toEqual(['Virilha', 'Perianal']))
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
    await waitFor(() => expect(areasMontadas()).toEqual(['Virilha', 'Perianal']))
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

describe('nenhum registro incompleto (PRD 051)', () => {
  const salvar = () => screen.getByRole('button', { name: /salvar/i })

  it('Energia apagada: destaca o campo, mostra a mensagem e não grava', async () => {
    monta([sessao({ areas: 'Axila' })])
    await waitFor(() => expect(areasMontadas()).toEqual(['Axila']))

    const energia = screen.getByLabelText(/Energia \(kJ\)/)
    await userEvent.clear(energia)
    expect(screen.queryByText(/informe Energia/)).toBeNull() // durante a edição nada acusa

    await userEvent.click(salvar())

    expect(gravacao.mutateAsync).not.toHaveBeenCalled()
    expect(screen.getByText('Axila: informe Energia (kJ).')).toBeInTheDocument()
    expect(screen.getByLabelText(/Energia \(kJ\)/)).toHaveAttribute('aria-invalid', 'true')
  })

  it('preencher o que faltava libera o salvamento', async () => {
    monta([sessao({ areas: 'Axila' })])
    await waitFor(() => expect(areasMontadas()).toEqual(['Axila']))

    await userEvent.clear(screen.getByLabelText(/Energia \(kJ\)/))
    await userEvent.click(salvar())
    await userEvent.type(screen.getByLabelText(/Energia \(kJ\)/), '8')

    expect(screen.getByLabelText(/Energia \(kJ\)/)).not.toHaveAttribute('aria-invalid')
    await userEvent.click(salvar())
    expect(gravacao.mutateAsync).toHaveBeenCalledTimes(1)
  })

  it('área sem método: destaca o seletor; "Remover" a área resolve', async () => {
    monta([sessao({ areas: 'Axila, Área nova' })])
    await waitFor(() => expect(areasMontadas()).toEqual(['Axila', 'Área nova']))

    await userEvent.click(salvar())

    expect(gravacao.mutateAsync).not.toHaveBeenCalled()
    expect(screen.getByText('Área nova: escolha o método.')).toBeInTheDocument()
    const seletores = screen.getAllByRole('combobox', { name: /Método/ })
    expect(seletores[1]).toHaveAttribute('aria-invalid', 'true')
    expect(seletores[0]).not.toHaveAttribute('aria-invalid')

    await userEvent.click(screen.getByRole('button', { name: 'Remover Área nova' }))
    await userEvent.click(salvar())
    expect(gravacao.mutateAsync).toHaveBeenCalledTimes(1)
  })

  it('registro sem nenhuma área não grava', async () => {
    monta([sessao({ id: 'f1', appointment_date: '2026-12-01', areas: 'Axila' })])
    await userEvent.type(screen.getByLabelText('Data'), '2026-11-09')

    await userEvent.click(salvar())

    expect(gravacao.mutateAsync).not.toHaveBeenCalled()
    expect(screen.getByText('Informe ao menos uma área aplicada.')).toBeInTheDocument()
  })

  it('várias pendências viram um resumo contado', async () => {
    monta([sessao({ areas: 'Axila' })])
    await waitFor(() => expect(areasMontadas()).toEqual(['Axila']))

    await userEvent.clear(screen.getByLabelText(/Energia \(kJ\)/))
    await userEvent.clear(screen.getByLabelText(/Fluência \(J\)/))
    await userEvent.click(salvar())

    expect(screen.getByText(/Faltam 2 campos/)).toBeInTheDocument()
  })
})
