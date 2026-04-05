import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/Button'

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
      setServerError('E-mail ou senha invalidos. Tente novamente.')
    }
  }

  return (
    <div className="flex h-screen w-full">
      {/* Brand panel */}
      <div className="hidden lg:flex flex-col justify-between w-96 bg-brand-600 p-10 text-white flex-shrink-0">
        <div>
          <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center mb-8">
            <svg className="w-6 h-6" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round">
              <path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
            </svg>
          </div>
          <h1 className="text-3xl font-bold leading-tight mb-3">Painel da Clínica</h1>
          <p className="text-brand-100 text-sm leading-relaxed">
            Gerencie agendamentos, pacientes, bot do WhatsApp e relatórios da sua clínica.
          </p>
        </div>
        <p className="text-brand-200 text-xs">© {new Date().getFullYear()}</p>
      </div>

      {/* Form panel */}
      <div className="flex-1 flex items-center justify-center p-8 bg-gray-50">
        <div className="w-full max-w-sm">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-2 mb-8">
            <div className="w-8 h-8 rounded-lg bg-brand-500 flex items-center justify-center">
              <svg className="w-4.5 h-4.5 text-white" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
            </div>
            <span className="font-bold text-gray-800">Painel da Clínica</span>
          </div>

          <h2 className="text-2xl font-bold text-gray-800 mb-1">Entrar</h2>
          <p className="text-sm text-gray-400 mb-8">Acesse o painel de gestão da sua clínica</p>

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

            <Button type="submit" loading={isSubmitting} className="w-full">
              Entrar
            </Button>
          </form>

          <p className="text-xs text-gray-400 mt-6 text-center">
            Problemas para acessar? Fale com o suporte.
          </p>
        </div>
      </div>
    </div>
  )
}
