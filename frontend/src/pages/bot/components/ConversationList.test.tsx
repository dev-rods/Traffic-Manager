/**
 * A lista diz por que o bot está calado em cada conversa e deixa ativá-lo sem
 * abrir (PRD 031). O que se protege: o selo segue o motivo que o servidor
 * mandou; "Ativar bot" só existe para quem está fora da regra e não abre a
 * conversa ao ser clicado; o filtro separa os casos.
 */
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConversationList } from './ConversationList'
import { passaNoFiltro } from '@/lib/motivoDaPausa'
import type { ConversationPreview } from '@/types'

function conversa(over: Partial<ConversationPreview> = {}): ConversationPreview {
  return {
    phone: '5511999990000',
    last_message: 'oi, quanto custa a axila?',
    last_direction: 'INBOUND',
    last_message_at: '2026-10-31T14:00:00Z',
    sender_name: 'Maria',
    ...over,
  }
}

function monta(conversations: ConversationPreview[], over: Partial<React.ComponentProps<typeof ConversationList>> = {}) {
  const onSelect = vi.fn()
  const onResume = vi.fn()
  render(
    <ConversationList
      conversations={conversations}
      selectedPhone={null}
      onSelect={onSelect}
      onResume={onResume}
      resumeLoadingPhone={null}
      {...over}
    />,
  )
  return { onSelect, onResume }
}

describe('selo do motivo', () => {
  it('mostra o motivo que o servidor mandou', () => {
    monta([
      conversa({ phone: '1', sender_name: 'Avulsa', pause_reason: 'not_eligible' }),
      conversa({ phone: '2', sender_name: 'Com gente', pause_reason: 'attendant' }),
      conversa({ phone: '3', sender_name: 'Pausada', pause_reason: 'clinic_paused' }),
    ])
    expect(screen.getByText('Fora da regra')).toBeInTheDocument()
    expect(screen.getByText('Com atendente')).toBeInTheDocument()
    expect(screen.getByText('Bot pausado')).toBeInTheDocument()
  })

  it('sem motivo, sem selo - inclusive quando o backend antigo nem manda o campo', () => {
    monta([conversa({ phone: '1', pause_reason: null }), conversa({ phone: '2' })])
    expect(screen.queryByText(/Fora da regra|Com atendente|Bot pausado/)).not.toBeInTheDocument()
  })
})

describe('ativar bot pela linha', () => {
  it('só quem está fora da regra tem o botão', () => {
    monta([
      conversa({ phone: '1', pause_reason: 'not_eligible' }),
      conversa({ phone: '2', pause_reason: 'attendant' }),
      conversa({ phone: '3' }),
    ])
    expect(screen.getAllByRole('button', { name: 'Ativar bot' })).toHaveLength(1)
  })

  it('clicar ativa sem abrir a conversa', async () => {
    const { onSelect, onResume } = monta([conversa({ pause_reason: 'not_eligible' })])
    await userEvent.click(screen.getByRole('button', { name: 'Ativar bot' }))
    expect(onResume).toHaveBeenCalledWith('5511999990000')
    expect(onSelect).not.toHaveBeenCalled()
  })

  it('clicar na linha abre a conversa', async () => {
    const { onSelect } = monta([conversa()])
    await userEvent.click(screen.getByRole('button', { name: 'Abrir conversa com Maria' }))
    expect(onSelect).toHaveBeenCalledWith('5511999990000', 'Maria')
  })

  it('a linha abre pelo teclado', async () => {
    const { onSelect } = monta([conversa()])
    screen.getByRole('button', { name: 'Abrir conversa com Maria' }).focus()
    await userEvent.keyboard('{Enter}')
    expect(onSelect).toHaveBeenCalledTimes(1)
  })

  it('só o botão da conversa em andamento gira', () => {
    monta(
      [conversa({ phone: '1', pause_reason: 'not_eligible' }), conversa({ phone: '2', pause_reason: 'not_eligible' })],
      { resumeLoadingPhone: '1' },
    )
    const botoes = screen.getAllByRole('button', { name: 'Ativar bot' })
    expect(botoes[0]).toBeDisabled()
    expect(botoes[1]).not.toBeDisabled()
  })
})

describe('vazio', () => {
  it('usa a mensagem do filtro quando dada', () => {
    monta([], { emptyMessage: 'Nenhuma conversa neste filtro' })
    expect(screen.getByText('Nenhuma conversa neste filtro')).toBeInTheDocument()
  })
})

describe('passaNoFiltro', () => {
  it.each([
    ['todas', 'not_eligible', true],
    ['todas', undefined, true],
    ['fora_da_regra', 'not_eligible', true],
    ['fora_da_regra', 'attendant', false],
    ['com_atendente', 'attendant', true],
    ['com_atendente', null, false],
    ['bot_ativo', null, true],
    ['bot_ativo', undefined, true],
    ['bot_ativo', 'clinic_paused', false],
  ] as const)('%s x %s -> %s', (filtro, motivo, esperado) => {
    expect(passaNoFiltro(motivo, filtro)).toBe(esperado)
  })
})
