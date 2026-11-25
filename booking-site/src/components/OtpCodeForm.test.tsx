import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { OtpCodeForm } from './OtpCodeForm'
import { limpaEnviosRecentes } from '@/utils/enviosDeCodigo'
import { bookingService } from '@/services/booking.service'

vi.mock('@/services/booking.service', () => ({
  bookingService: { sendOtp: vi.fn(), confirmOtp: vi.fn() },
}))

const PHONE = '5511987654321'

function monta() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const ui = (
    <QueryClientProvider client={client}>
      <OtpCodeForm clinicId="c1" phone={PHONE} onVerified={vi.fn()} />
    </QueryClientProvider>
  )
  const r = render(ui)
  return { ...r, remonta: () => { r.unmount(); return render(ui) } }
}

describe('OtpCodeForm', () => {
  beforeEach(() => {
    limpaEnviosRecentes()
    vi.mocked(bookingService.sendOtp).mockReset().mockResolvedValue({ status: 'SUCCESS' })
  })

  it('envia um código ao montar e começa a contagem do reenvio', async () => {
    monta()
    expect(await screen.findByRole('button', { name: /Reenviar código em \d+s/ })).toBeDisabled()
    await waitFor(() => expect(bookingService.sendOtp).toHaveBeenCalledTimes(1))
    expect(bookingService.sendOtp).toHaveBeenCalledWith('c1', PHONE)
  })

  it('remontar o formulário logo depois não manda outro código', async () => {
    const { remonta } = monta()
    await screen.findByRole('button', { name: /Reenviar código em/ })
    remonta()
    expect(await screen.findByRole('button', { name: /Reenviar código em/ })).toBeDisabled()
    expect(bookingService.sendOtp).toHaveBeenCalledTimes(1)
  })

  it('passada a espera, "Reenviar código" manda outro e reinicia a contagem', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    try {
      monta()
      await vi.advanceTimersByTimeAsync(31_000)
      const botao = await screen.findByRole('button', { name: 'Reenviar código' })
      expect(botao).toBeEnabled()
      await userEvent.click(botao, { advanceTimers: vi.advanceTimersByTime })
      expect(bookingService.sendOtp).toHaveBeenCalledTimes(2)
      expect(await screen.findByRole('button', { name: /Reenviar código em/ })).toBeDisabled()
    } finally {
      vi.useRealTimers()
    }
  })
})
