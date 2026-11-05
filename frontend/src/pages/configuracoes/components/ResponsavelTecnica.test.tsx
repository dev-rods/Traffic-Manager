import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ResponsavelTecnica } from './ResponsavelTecnica'
import type { Professional } from '@/services/professionals.service'

const atualizar = vi.fn()
let profissionais: Professional[] = []

vi.mock('@/hooks/useProfessionals', () => ({
  useProfessionals: () => ({ data: profissionais, isLoading: false, isError: false }),
  useUpdateProfessional: () => ({ mutate: atualizar, isPending: false, isSuccess: false }),
}))

const LIA: Professional = {
  id: 'p1',
  clinic_id: 'c1',
  name: 'Dra. Lia',
  role: 'Biomédica',
  registro_conselho: null,
  active: true,
}

beforeEach(() => {
  atualizar.mockReset()
  profissionais = [LIA, { ...LIA, id: 'p2', name: 'Bia', role: null, registro_conselho: 'CRBM 9' }]
})

describe('ResponsavelTecnica', () => {
  it('avisa o que falta para o termo ser gerado', () => {
    const { rerender } = render(
      <ResponsavelTecnica responsibleProfessionalId={null} cidade="" onChange={vi.fn()} />
    )
    expect(screen.getByRole('status')).toHaveTextContent('Falta a profissional responsável, a cidade.')

    rerender(<ResponsavelTecnica responsibleProfessionalId="p1" cidade="São Paulo" onChange={vi.fn()} />)
    expect(screen.getByRole('status')).toHaveTextContent('Falta o registro no conselho dela.')

    rerender(<ResponsavelTecnica responsibleProfessionalId="p2" cidade="São Paulo" onChange={vi.fn()} />)
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('escolher a responsável e a cidade sobe para o formulário', async () => {
    const onChange = vi.fn()
    render(<ResponsavelTecnica responsibleProfessionalId={null} cidade="" onChange={onChange} />)
    await userEvent.selectOptions(screen.getByLabelText('Profissional responsável'), 'p1')
    expect(onChange).toHaveBeenCalledWith('responsible_professional_id', 'p1')
    await userEvent.type(screen.getByLabelText('Cidade'), 'S')
    expect(onChange).toHaveBeenCalledWith('cidade', 'S')
  })

  it('o registro é salvo por profissional', async () => {
    render(<ResponsavelTecnica responsibleProfessionalId="p1" cidade="SP" onChange={vi.fn()} />)
    const campo = screen.getByLabelText('Registro no conselho de Dra. Lia')
    const salvar = screen.getAllByRole('button', { name: 'Salvar' })[0]
    expect(salvar).toBeDisabled()
    await userEvent.type(campo, 'CRBM 1234')
    await userEvent.click(salvar)
    expect(atualizar).toHaveBeenCalledWith({ id: 'p1', payload: { registro_conselho: 'CRBM 1234' } })
  })
})
