import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuth } from '@/hooks/useAuth'

const schema = z.object({
  email: z.string().min(1, 'E-mail obrigatório').email('E-mail inválido'),
  password: z.string().min(1, 'Senha obrigatória'),
})

type FormData = z.infer<typeof schema>

export default function LoginPage() {
  const { login } = useAuth()
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormData>({ resolver: zodResolver(schema) })

  const onSubmit = async (data: FormData) => {
    setServerError(null)
    try {
      await login(data)
    } catch {
      setServerError('E-mail ou senha inválidos. Tente novamente.')
    }
  }

  return (
    <div className="flex h-screen w-full">
      {/* Brand panel */}
      <div className="hidden lg:flex flex-col justify-between w-96 bg-brand-600 p-10 text-white flex-shrink-0">
        <div>
          <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center text-xl font-bold mb-8">
            T
          </div>
          <h1 className="text-3xl font-bold leading-tight mb-3">Traffic Manager</h1>
          <p className="text-brand-100 text-sm leading-relaxed">
            Painel de gestão para clínicas de estética. Visualize agendamentos, pacientes e
            relatórios em tempo real.
          </p>
        </div>
        <p className="text-brand-200 text-xs">© {new Date().getFullYear()} Traffic Manager</p>
      </div>

      {/* Form panel */}
      <div className="flex-1 flex items-center justify-center p-8 bg-gray-50">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center text-white font-bold">
              T
            </div>
            <span className="font-bold text-gray-800">Traffic Manager</span>
          </div>

          <h2 className="text-2xl font-bold text-gray-800 mb-1">Entrar</h2>
          <p className="text-sm text-gray-400 mb-8">Acesse o painel da sua clínica</p>

          <form onSubmit={(e) => void handleSubmit(onSubmit)(e)} className="space-y-4" noValidate>
            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">
                E-mail
              </label>
              <input
                type="email"
                autoComplete="email"
                placeholder="seu@email.com"
                {...register('email')}
                className={[
                  'w-full border rounded-lg px-3 py-2.5 text-sm bg-white transition-colors',
                  'focus:outline-none focus:ring-2 focus:ring-brand-500',
                  errors.email ? 'border-red-400' : 'border-gray-200',
                ].join(' ')}
              />
              {errors.email && (
                <p className="text-xs text-red-500 mt-1">{errors.email.message}</p>
              )}
            </div>

            <div>
              <label className="text-xs font-medium text-gray-500 block mb-1">Senha</label>
              <input
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                {...register('password')}
                className={[
                  'w-full border rounded-lg px-3 py-2.5 text-sm bg-white transition-colors',
                  'focus:outline-none focus:ring-2 focus:ring-brand-500',
                  errors.password ? 'border-red-400' : 'border-gray-200',
                ].join(' ')}
              />
              {errors.password && (
                <p className="text-xs text-red-500 mt-1">{errors.password.message}</p>
              )}
            </div>

            {serverError && (
              <div className="bg-red-50 border border-red-200 text-red-600 text-sm rounded-lg px-4 py-3">
                {serverError}
              </div>
            )}

            <button
              type="submit"
              disabled={isSubmitting}
              className={[
                'w-full font-semibold py-2.5 rounded-lg text-sm transition-colors',
                isSubmitting
                  ? 'bg-brand-300 text-white cursor-not-allowed'
                  : 'bg-brand-500 hover:bg-brand-600 text-white',
              ].join(' ')}
            >
              {isSubmitting ? 'Entrando…' : 'Entrar'}
            </button>
          </form>

          <p className="text-xs text-gray-400 mt-6 text-center">
            Problemas para acessar? Fale com o suporte.
          </p>
        </div>
      </div>
    </div>
  )
}
