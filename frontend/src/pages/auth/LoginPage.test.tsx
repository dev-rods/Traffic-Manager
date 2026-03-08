import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from '@/store/AuthContext'
import LoginPage from './LoginPage'

const mockLogin = vi.fn()

vi.mock('@/hooks/useAuth', () => ({
  useAuth: () => ({ login: mockLogin, isAuthenticated: false, isLoading: false }),
}))

function renderLogin() {
  return render(
    <MemoryRouter>
      <AuthProvider>
        <LoginPage />
      </AuthProvider>
    </MemoryRouter>
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders email and password fields', () => {
    renderLogin()
    expect(screen.getByPlaceholderText('seu@email.com')).toBeInTheDocument()
    expect(screen.getByPlaceholderText('••••••••')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /entrar/i })).toBeInTheDocument()
  })

  it('shows validation errors when submitting empty form', async () => {
    renderLogin()
    await userEvent.click(screen.getByRole('button', { name: /entrar/i }))
    expect(await screen.findByText('E-mail obrigatório')).toBeInTheDocument()
    expect(await screen.findByText('Senha obrigatória')).toBeInTheDocument()
  })

  it('shows validation error for invalid email', async () => {
    renderLogin()
    await userEvent.type(screen.getByPlaceholderText('seu@email.com'), 'notanemail')
    await userEvent.type(screen.getByPlaceholderText('••••••••'), '123456')
    await userEvent.click(screen.getByRole('button', { name: /entrar/i }))
    expect(await screen.findByText('E-mail inválido')).toBeInTheDocument()
  })

  it('calls login with correct credentials', async () => {
    mockLogin.mockResolvedValueOnce(undefined)
    renderLogin()
    await userEvent.type(screen.getByPlaceholderText('seu@email.com'), 'test@clinic.com')
    await userEvent.type(screen.getByPlaceholderText('••••••••'), 'secret123')
    await userEvent.click(screen.getByRole('button', { name: /entrar/i }))
    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith({
        email: 'test@clinic.com',
        password: 'secret123',
      })
    })
  })

  it('shows server error when login fails', async () => {
    mockLogin.mockRejectedValueOnce(new Error('Unauthorized'))
    renderLogin()
    await userEvent.type(screen.getByPlaceholderText('seu@email.com'), 'test@clinic.com')
    await userEvent.type(screen.getByPlaceholderText('••••••••'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: /entrar/i }))
    expect(await screen.findByText(/e-mail ou senha inválidos/i)).toBeInTheDocument()
  })

  it('disables button while submitting', async () => {
    mockLogin.mockImplementation(() => new Promise((r) => setTimeout(r, 100)))
    renderLogin()
    await userEvent.type(screen.getByPlaceholderText('seu@email.com'), 'test@clinic.com')
    await userEvent.type(screen.getByPlaceholderText('••••••••'), 'secret123')
    await userEvent.click(screen.getByRole('button', { name: /entrar/i }))
    expect(screen.getByRole('button', { name: /entrando/i })).toBeDisabled()
  })
})
