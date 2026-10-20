import type { Clinic } from '@/types'
import { Button } from '@/components/ui/Button'

export function StartStep({
  clinic,
  onStart,
}: {
  clinic: Clinic | undefined
  onStart: () => void
}) {
  const name = clinic ? clinic.display_name || clinic.name : ''

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-10 text-center">
      <span className="flex h-32 w-32 items-center justify-center overflow-hidden rounded-full bg-ink-100 shadow-card">
        {clinic?.logo_url ? (
          <img src={clinic.logo_url} alt="" className="h-full w-full object-cover" />
        ) : (
          <span className="font-display text-5xl font-semibold text-ink-600" aria-hidden>
            {name.charAt(0).toUpperCase()}
          </span>
        )}
      </span>
      <div className="flex flex-col gap-3">
        <p className="text-xl text-ink-500">Seja bem-vindo(a)</p>
        <h1 className="font-display text-4xl font-bold text-ink-900 sm:text-5xl">{name}</h1>
      </div>
      <Button onClick={onStart} className="min-h-20 w-full max-w-md text-2xl">
        Fazer check-in
      </Button>
      <p className="max-w-md text-base text-ink-500">
        Confirme seu agendamento e faça o pagamento por aqui.
      </p>
    </div>
  )
}
