import { useEffect, useState } from 'react'
import { Link, Outlet, useSearchParams } from 'react-router-dom'
import { MyAppointmentsModal } from '@/components/MyAppointmentsModal'
import { Button } from '@/components/ui/Button'
import { useClinicBootstrap } from '@/hooks/useBooking'
import { useClinicId } from '@/hooks/useClinicId'

function useDynamicFavicon(faviconUrl: string | null | undefined) {
  useEffect(() => {
    if (!faviconUrl) return
    let link = document.querySelector<HTMLLinkElement>("link[rel~='icon']")
    if (!link) {
      link = document.createElement('link')
      link.rel = 'icon'
      document.head.appendChild(link)
    }
    link.href = faviconUrl
  }, [faviconUrl])
}

/** Header, favicon dinâmico e modal de "Meus agendamentos" — compartilhados
 * entre o layout por path (/:clinicId) e o layout por domínio próprio. A
 * única diferença entre os dois é COMO o clinicId chega até aqui. */
/** `?meus=1` abre "Meus agendamentos" direto (PRD 060). É o link que o bot e
 * a recepção mandam para remarcar ou cancelar: a raiz abria o fluxo de
 * marcar e a paciente não achava o botão do cabeçalho. */
export const PARAMETRO_MEUS_AGENDAMENTOS = 'meus'

export function BookingChrome() {
  const { clinicId, basePath } = useClinicId()
  const [searchParams, setSearchParams] = useSearchParams()
  const abrirPelaUrl = searchParams.has(PARAMETRO_MEUS_AGENDAMENTOS)
  const [abertoPeloBotao, setMyAppointmentsOpen] = useState(false)
  // Derivado, sem efeito: a URL manda enquanto o parâmetro existir; fechar o
  // tira da URL e o botão do cabeçalho continua funcionando sozinho.
  const myAppointmentsOpen = abertoPeloBotao || abrirPelaUrl
  const bootstrap = useClinicBootstrap(clinicId)
  const clinic = bootstrap.data?.clinic

  useDynamicFavicon(clinic?.favicon_url)

  function fecharMeusAgendamentos() {
    setMyAppointmentsOpen(false)
    if (abrirPelaUrl) {
      // Fechar limpa a URL: voltar ao site depois não reabre o modal, e o
      // link compartilhado continua sendo o da raiz.
      const proximos = new URLSearchParams(searchParams)
      proximos.delete(PARAMETRO_MEUS_AGENDAMENTOS)
      setSearchParams(proximos, { replace: true })
    }
  }

  return (
    <div className="min-h-screen bg-ink-50">
      <header className="border-b border-ink-200 bg-surface">
        <div className="mx-auto flex max-w-[720px] items-center justify-between px-5 py-3 sm:px-10">
          {/* A identidade da clínica fica nas boas-vindas de cada tela
              (ClinicWelcome); repetir o logo aqui duplicava o avatar. */}
          <Link
            to={basePath || '/'}
            className="-ml-1 flex min-h-11 items-center px-1 font-display text-base font-semibold tracking-wide text-ink-900 transition-opacity hover:opacity-70"
          >
            Agende online
          </Link>
          <Button
            variant="muted"
            size="sm"
            className="h-11"
            onClick={() => setMyAppointmentsOpen(true)}
          >
            Meus agendamentos
          </Button>
        </div>
      </header>
      <main className="mx-auto max-w-[720px] px-5 py-6 sm:px-10 sm:py-10">
        <Outlet />
      </main>
      <MyAppointmentsModal
        open={myAppointmentsOpen}
        clinicId={clinicId}
        onClose={fecharMeusAgendamentos}
      />
    </div>
  )
}
