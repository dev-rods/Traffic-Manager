import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CelularComPais } from './CelularComPais'

describe('CelularComPais (PRD 067)', () => {
  it('Brasil por padrão, com máscara, e manda 55 + número', async () => {
    const onChange = vi.fn()
    render(<CelularComPais label="WhatsApp" onChange={onChange} />)
    expect(screen.getByLabelText('País do telefone')).toHaveValue('55')
    await userEvent.type(screen.getByLabelText('WhatsApp'), '11987654321')
    expect(screen.getByLabelText('WhatsApp')).toHaveValue('(11) 98765-4321')
    expect(onChange).toHaveBeenLastCalledWith('5511987654321')
  })

  it('EUA manda +1 e o número, sem o 55', async () => {
    const onChange = vi.fn()
    render(<CelularComPais label="WhatsApp" onChange={onChange} />)
    await userEvent.selectOptions(screen.getByLabelText('País do telefone'), '1')
    await userEvent.type(screen.getByLabelText('WhatsApp'), '2025550147')
    expect(onChange).toHaveBeenLastCalledWith('+12025550147')
  })

  it('"Outro país" só vale com o código', async () => {
    const onChange = vi.fn()
    render(<CelularComPais label="WhatsApp" onChange={onChange} />)
    await userEvent.selectOptions(screen.getByLabelText('País do telefone'), 'outro')
    await userEvent.type(screen.getByLabelText('WhatsApp'), '12345678')
    expect(onChange).toHaveBeenLastCalledWith('')
    await userEvent.type(screen.getByLabelText('Código do país'), '45')
    expect(onChange).toHaveBeenLastCalledWith('+4512345678')
  })

  it('abre o número gravado no país certo e não avisa nada sem mexer', () => {
    const onChange = vi.fn()
    render(<CelularComPais label="WhatsApp" defaultValue="12025550147" onChange={onChange} />)
    expect(screen.getByLabelText('País do telefone')).toHaveValue('1')
    expect(screen.getByLabelText('WhatsApp')).toHaveValue('2025550147')
    expect(onChange).not.toHaveBeenCalled()
  })
})
