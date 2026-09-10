import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { CampanhaDoBot } from './CampanhaDoBot'

const DATAS = ['2026-10-07', '2026-10-14', '2026-10-21', '2026-10-28']

function Wrapper({ iniciais = DATAS.slice(0, 3) }: { iniciais?: string[] }) {
  const [selecionadas, setSelecionadas] = useState(iniciais)
  const [ativa, setAtiva] = useState(true)
  return (
    <CampanhaDoBot
      datasDisponiveis={DATAS}
      selecionadas={selecionadas}
      onSelecionar={setSelecionadas}
      ativa={ativa}
      onAtivar={setAtiva}
    />
  )
}

describe('CampanhaDoBot', () => {
  it('mostra as datas disponíveis como opções', () => {
    render(<Wrapper />)
    expect(screen.getByRole('button', { name: '07/10' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '28/10' })).toBeInTheDocument()
  })

  it('trava a seleção em 3 datas', async () => {
    render(<Wrapper />)
    // As 3 primeiras já vêm marcadas; a quarta não pode entrar.
    expect(screen.getByRole('button', { name: '28/10' })).toBeDisabled()
  })

  it('libera a quarta quando uma sai', async () => {
    const user = userEvent.setup()
    render(<Wrapper />)

    await user.click(screen.getByRole('button', { name: '07/10' }))

    expect(screen.getByRole('button', { name: '28/10' })).toBeEnabled()
  })

  it('avisa quando não sobra nenhuma data', async () => {
    render(<Wrapper iniciais={[]} />)
    expect(screen.getByText(/o bot não tem o que oferecer/i)).toBeInTheDocument()
  })

  it('esconde as datas quando o bot não assume', async () => {
    const user = userEvent.setup()
    render(<Wrapper />)

    await user.click(screen.getByRole('checkbox'))

    expect(screen.queryByRole('button', { name: '07/10' })).not.toBeInTheDocument()
  })

  it('explica que a campanha vence', () => {
    render(<Wrapper />)
    expect(screen.getByText(/7 dias/)).toBeInTheDocument()
  })

  it('sem datas de agenda, avisa que o bot não assume', () => {
    render(
      <CampanhaDoBot
        datasDisponiveis={[]}
        selecionadas={[]}
        onSelecionar={vi.fn()}
        ativa
        onAtivar={vi.fn()}
      />,
    )
    expect(screen.getByText(/bot\s+não assume a conversa/i)).toBeInTheDocument()
  })
})
