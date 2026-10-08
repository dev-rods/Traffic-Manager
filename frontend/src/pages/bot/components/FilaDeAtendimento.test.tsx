/**
 * A fila de quem precisa de uma pessoa.
 *
 * O que estes testes protegem não é o layout: é a ORDEM e a SEPARAÇÃO.
 *
 * Ordem, porque a fila mostra a espera mais antiga primeiro - o contrário do
 * resto do painel. Ordenar pelo mais recente aqui esconderia no fim da lista
 * exatamente a paciente que espera há mais tempo.
 *
 * Separação, porque "aguardando especialista" e "atendente assumiu" eram a
 * mesma lista. Trabalho a fazer e trabalho acontecendo misturados, e o urgente
 * escondido entre os outros.
 */
import { describe, expect, it, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FilaDeAtendimento } from './FilaDeAtendimento'
import type { ActiveConversation } from '@/types'

const AGORA = Math.floor(Date.now() / 1000)

function conversa(over: Partial<ActiveConversation> = {}): ActiveConversation {
  return {
    phone: '5511999990000',
    state: 'HUMAN_HANDOFF',
    bot_paused: true,
    pause_reason: 'attendant',
    attendant_active_until: null,
    handoff_requested_at: AGORA - 120,
    handoff_reason: 'procedimento_fora_do_escopo',
    handoff_reason_label: 'Perguntou sobre outro procedimento',
    updated_at: '2026-10-04T15:00:00Z',
    ...over,
  }
}

function monta(props: Partial<React.ComponentProps<typeof FilaDeAtendimento>> = {}) {
  const onSelect = vi.fn()
  const onResume = vi.fn()
  const onRetry = vi.fn()
  render(
    <FilaDeAtendimento
      conversations={[]}
      isLoading={false}
      isError={false}
      onRetry={onRetry}
      onSelect={onSelect}
      onResume={onResume}
      resumeLoading={false}
      {...props}
    />,
  )
  return { onSelect, onResume, onRetry }
}

describe('ordem da fila', () => {
  it('quem espera há mais tempo aparece primeiro', () => {
    monta({
      conversations: [
        conversa({ phone: '5511900000001', name: 'Recente', handoff_requested_at: AGORA - 60 }),
        conversa({ phone: '5511900000002', name: 'Antiga', handoff_requested_at: AGORA - 10_800 }),
        conversa({ phone: '5511900000003', name: 'Media', handoff_requested_at: AGORA - 3_600 }),
      ],
    })

    const nomes = screen.getAllByRole('listitem').map((li) => li.textContent)
    expect(nomes[0]).toContain('Antiga')
    expect(nomes[1]).toContain('Media')
    expect(nomes[2]).toContain('Recente')
  })

  it('conversa sem data de entrega não embaralha a ordem das que têm', () => {
    // Conversas entregues antes desta mudança não têm o campo. Elas vão para o
    // topo (0 é o mais antigo possível), e o importante é que as datadas
    // continuem entre si na ordem certa.
    monta({
      conversations: [
        conversa({ phone: '5511900000001', name: 'Com data', handoff_requested_at: AGORA - 60 }),
        conversa({ phone: '5511900000002', name: 'Sem data', handoff_requested_at: null }),
      ],
    })

    const nomes = screen.getAllByRole('listitem').map((li) => li.textContent)
    expect(nomes[0]).toContain('Sem data')
    expect(nomes[1]).toContain('Com data')
  })
})

describe('separação das abas', () => {
  it('a aba da especialista só mostra quem o bot entregou', () => {
    monta({
      conversations: [
        conversa({ phone: '5511900000001', name: 'Esperando', state: 'HUMAN_HANDOFF' }),
        conversa({
          phone: '5511900000002',
          name: 'Ja atendida',
          state: 'HUMAN_ATTENDANT_ACTIVE',
        }),
      ],
    })

    const itens = screen.getAllByRole('listitem')
    expect(itens).toHaveLength(1)
    expect(itens[0].textContent).toContain('Esperando')
  })

  it('a aba de pausadas mostra o resto', async () => {
    monta({
      conversations: [
        conversa({ phone: '5511900000001', name: 'Esperando', state: 'HUMAN_HANDOFF' }),
        conversa({
          phone: '5511900000002',
          name: 'Ja atendida',
          state: 'HUMAN_ATTENDANT_ACTIVE',
        }),
      ],
    })

    await userEvent.click(screen.getByRole('button', { name: /Bot pausado/ }))

    const itens = screen.getAllByRole('listitem')
    expect(itens).toHaveLength(1)
    expect(itens[0].textContent).toContain('Ja atendida')
  })

  it('a contagem de cada aba conta a própria lista', () => {
    monta({
      conversations: [
        conversa({ phone: '5511900000001', state: 'HUMAN_HANDOFF' }),
        conversa({ phone: '5511900000002', state: 'HUMAN_HANDOFF' }),
        conversa({ phone: '5511900000003', state: 'HUMAN_ATTENDANT_ACTIVE' }),
      ],
    })

    expect(
      within(screen.getByRole('button', { name: /Aguardando especialista/ })).getByText('2'),
    ).toBeTruthy()
    expect(
      within(screen.getByRole('button', { name: /Bot pausado/ })).getByText('1'),
    ).toBeTruthy()
  })
})

describe('o que a linha diz', () => {
  it('mostra o motivo que o servidor traduziu', () => {
    monta({ conversations: [conversa()] })
    expect(screen.getByText(/Perguntou sobre outro procedimento/)).toBeTruthy()
  })

  it('sem motivo gravado, diz isso em vez de ficar em branco', () => {
    // Conversas entregues antes desta mudança não têm motivo. Rótulo vazio
    // pareceria defeito da tela.
    monta({ conversations: [conversa({ handoff_reason: null, handoff_reason_label: '' })] })
    expect(screen.getByText(/Motivo não registrado/)).toBeTruthy()
  })

  it('a espera aparece em texto, não só em cor', () => {
    // Quem não distingue vermelho de cinza tem que ler o tempo do mesmo jeito.
    monta({ conversations: [conversa({ handoff_requested_at: AGORA - 7_200 })] })
    expect(screen.getByText(/espera 2h/)).toBeTruthy()
  })

  it('cai no telefone quando a paciente não tem cadastro', () => {
    monta({ conversations: [conversa({ phone: '5511988887777', name: '' })] })
    expect(screen.getByText('(11) 98888-7777')).toBeTruthy()
  })
})

describe('ações', () => {
  it('"Ver conversa" abre a thread daquela pessoa', async () => {
    const { onSelect } = monta({
      conversations: [conversa({ phone: '5511900000009', name: 'Ana' })],
    })

    await userEvent.click(screen.getByRole('button', { name: 'Ver conversa' }))
    expect(onSelect).toHaveBeenCalledWith('5511900000009', 'Ana')
  })

  it('"Retomar bot" devolve aquela conversa ao bot', async () => {
    const { onResume } = monta({
      conversations: [conversa({ phone: '5511900000009' })],
    })

    await userEvent.click(screen.getByRole('button', { name: 'Retomar bot' }))
    expect(onResume).toHaveBeenCalledWith('5511900000009')
  })
})

describe('os quatro estados', () => {
  it('carregando', () => {
    monta({ isLoading: true, conversations: [] })
    expect(screen.queryByText(/Ninguém esperando/)).toBeNull()
  })

  it('erro vem antes de vazio', () => {
    // Lista vazia por falha de rede não é "ninguém esperando": dizer isso faria
    // a recepção parar de olhar justamente quando há alguém na fila.
    const { onRetry } = monta({ isError: true, conversations: [] })

    expect(screen.queryByText(/Ninguém esperando/)).toBeNull()
    expect(screen.getByText(/Pode haver alguém esperando/)).toBeTruthy()
    expect(onRetry).not.toHaveBeenCalled()
  })

  it('vazio ensina o que faz a conversa aparecer ali', () => {
    monta({ conversations: [] })
    expect(screen.getByText(/Ninguém esperando/)).toBeTruthy()
    expect(screen.getByText(/outro procedimento/)).toBeTruthy()
  })

  it('sucesso', () => {
    monta({ conversations: [conversa({ name: 'Ana Clara' })] })
    expect(screen.getByText('Ana Clara')).toBeTruthy()
  })
})

describe('pendência, tarefa e alerta (PRD 020 fase 3)', () => {
  it('conversa com tarefa aberta fica na aba da especialista mesmo sem HUMAN_HANDOFF', () => {
    monta({
      conversations: [
        conversa({
          phone: '5511900000001', name: 'Pendente', state: 'HUMAN_ATTENDANT_ACTIVE',
          handler: 'HUMAN_PENDING', pending_intent: 'faq_sem_resposta', pending_task_id: 't1',
        }),
      ],
    })

    const itens = screen.getAllByRole('listitem')
    expect(itens).toHaveLength(1)
    expect(itens[0].textContent).toContain('Pendente')
    expect(itens[0].textContent).toContain('tarefa aberta')
  })

  it('"Concluir tarefa" substitui "Retomar bot" quando há tarefa, e chama com o id', async () => {
    const onFecharTarefa = vi.fn()
    monta({
      conversations: [
        conversa({ phone: '5511900000001', handler: 'HUMAN_PENDING', pending_task_id: 't1' }),
      ],
      onFecharTarefa,
    })

    expect(screen.queryByRole('button', { name: 'Retomar bot' })).not.toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Concluir tarefa' }))
    expect(onFecharTarefa).toHaveBeenCalledWith('t1')
  })

  it('alerta do cron aparece na fila com o rótulo do servidor', () => {
    monta({
      conversations: [
        conversa({
          phone: '5511900000001', name: 'Calada', state: '', bot_paused: false,
          handler: 'COOLDOWN', alerta: 'modelo_disse_nao', alerta_label: 'Não parecia esperar resposta',
        }),
      ],
    })

    const itens = screen.getAllByRole('listitem')
    expect(itens).toHaveLength(1)
    expect(itens[0].textContent).toContain('Ficou sem resposta: Não parecia esperar resposta')
  })

  it('alerta com atendente ativa não entra na fila: alguém já está lá', () => {
    monta({
      conversations: [
        conversa({ phone: '5511900000001', state: 'HUMAN_ATTENDANT_ACTIVE', handler: 'HUMAN_ACTIVE', alerta: 'fecho_social' }),
      ],
    })
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
  })

  it('quem está na fila da especialista não aparece de novo em pausadas', async () => {
    monta({
      conversations: [
        conversa({ phone: '5511900000001', state: 'HUMAN_ATTENDANT_ACTIVE', handler: 'HUMAN_PENDING', pending_task_id: 't1' }),
      ],
    })
    await userEvent.click(screen.getByRole('button', { name: /Bot pausado/ }))
    expect(screen.queryAllByRole('listitem')).toHaveLength(0)
  })
})
