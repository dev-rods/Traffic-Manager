import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, act } from '@testing-library/react'
import { AuthProvider } from './AuthContext'
import { useAuth } from '@/hooks/useAuth'

// Mock the api module
vi.mock('@/services/api', () => ({
  api: {
    post: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  },
}))

import { api } from '@/services/api'
const mockApi = api as unknown as { post: ReturnType<typeof vi.fn> }

// Helper component to expose auth state
function AuthConsumer() {
  const { isAuthenticated, clinicId, login, logout } = useAuth()
  return (
    <div>
      <span data-testid="auth">{isAuthenticated ? 'yes' : 'no'}</span>
      <span data-testid="clinic">{clinicId ?? 'none'}</span>
      <button onClick={() => void login({ email: 'test@test.com', password: '123' })}>
        login
      </button>
      <button onClick={logout}>logout</button>
    </div>
  )
}

describe('AuthContext', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('starts unauthenticated when no stored session', async () => {
    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    )
    expect(screen.getByTestId('auth').textContent).toBe('no')
    expect(screen.getByTestId('clinic').textContent).toBe('none')
  })

  it('restores session from localStorage', async () => {
    localStorage.setItem('tm_token', 'tok123')
    localStorage.setItem('tm_clinic_id', 'clinic-abc')

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    )
    expect(screen.getByTestId('auth').textContent).toBe('yes')
    expect(screen.getByTestId('clinic').textContent).toBe('clinic-abc')
  })

  it('login stores token and updates state', async () => {
    mockApi.post.mockResolvedValueOnce({
      data: {
        token: 'new-token',
        clinic_id: 'clinic-xyz',
        clinic: { clinic_id: 'clinic-xyz', name: 'Test Clinic', owner_email: 'a@b.com' },
      },
    })

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    )

    await act(async () => {
      screen.getByText('login').click()
    })

    expect(screen.getByTestId('auth').textContent).toBe('yes')
    expect(screen.getByTestId('clinic').textContent).toBe('clinic-xyz')
    expect(localStorage.getItem('tm_token')).toBe('new-token')
    expect(localStorage.getItem('tm_clinic_id')).toBe('clinic-xyz')
  })

  it('logout clears state and localStorage', async () => {
    localStorage.setItem('tm_token', 'tok')
    localStorage.setItem('tm_clinic_id', 'cid')

    render(
      <AuthProvider>
        <AuthConsumer />
      </AuthProvider>
    )

    act(() => {
      screen.getByText('logout').click()
    })

    expect(screen.getByTestId('auth').textContent).toBe('no')
    expect(localStorage.getItem('tm_token')).toBeNull()
    expect(localStorage.getItem('tm_clinic_id')).toBeNull()
  })
})
