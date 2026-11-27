import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { EditPatientModal } from './EditPatientModal'
import type { PatientWithStats } from '@/types'

const mutateAsync = vi.fn()
vi.mock('@/hooks/usePatients', () => ({ useUpdatePatient: () => ({ mutateAsync }) }))
vi.mock('@/hooks/useOverlayLock', () => ({ useOverlayLock: () => undefined }))

function paciente(phone: string): PatientWithStats {
  return {
    id: 'p1',
    name: 'Fulana Teste',
    phone,
    gender: 'F',
    total_visits: 0,
    last_visit: null,
    next_visit: null,
    total_spent_cents: 0,
    last_message_at: null,
    consent_status: null,
  } as unknown as PatientWithStats
}

beforeEach(() => mutateAsync.mockReset().mockResolvedValue({}))

describe('Editar paciente: telefone com país (PRD 067)', () => {
  it('abre a paciente estrangeira no país certo e salvar sem mexer mantém o número', async () => {
    render(<EditPatientModal patient={paciente('12025550147')} onClose={vi.fn()} />)
    expect(screen.getByLabelText('País do telefone')).toHaveValue('1')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    await waitFor(() => expect(mutateAsync).toHaveBeenCalled())
    expect(mutateAsync.mock.calls[0][0].data.phone).toBe('12025550147')
  })

  it('trocar para EUA grava sem o 55', async () => {
    render(<EditPatientModal patient={paciente('5511999990000')} onClose={vi.fn()} />)
    await userEvent.selectOptions(screen.getByLabelText('País do telefone'), '1')
    const numero = screen.getByLabelText('WhatsApp')
    await userEvent.clear(numero)
    await userEvent.type(numero, '2025550147')
    await userEvent.click(screen.getByRole('button', { name: 'Salvar' }))
    await waitFor(() => expect(mutateAsync).toHaveBeenCalled())
    expect(mutateAsync.mock.calls[0][0].data.phone).toBe('12025550147')
  })
})
