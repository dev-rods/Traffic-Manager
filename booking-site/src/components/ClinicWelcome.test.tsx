import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { ClinicWelcome } from './ClinicWelcome'
import type { Clinic } from '@/types'

const CLINIC: Clinic = {
  clinic_id: 'c1',
  name: 'Clínica X',
  display_name: 'Clínica Essência',
  logo_url: null,
  favicon_url: null,
  timezone: 'America/Sao_Paulo',
  phone: null,
}

describe('ClinicWelcome', () => {
  it('mostra o nome de exibição e a inicial quando não há logo', () => {
    const { container } = render(<ClinicWelcome clinic={CLINIC} />)
    expect(screen.getByRole('heading', { name: 'Clínica Essência' })).toBeInTheDocument()
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText('C')).toBeInTheDocument()
  })

  it('usa o logo e cai no nome cadastrado sem nome de exibição', () => {
    const { container } = render(
      <ClinicWelcome clinic={{ ...CLINIC, display_name: null, logo_url: 'https://x/logo.png' }} />
    )
    expect(screen.getByRole('heading', { name: 'Clínica X' })).toBeInTheDocument()
    expect(container.querySelector('img')).toHaveAttribute('src', 'https://x/logo.png')
  })
})
