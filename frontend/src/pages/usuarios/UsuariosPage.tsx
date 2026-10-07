import { useState } from 'react'
import { useClinicUsers, useUpdateClinicUser } from '@/hooks/useClinicUsers'
import { ErrorState } from '@/components/ui/ErrorState'
import { SkeletonTable } from '@/components/ui/Skeleton'
import type { UsuarioDaClinica } from '@/services/clinicUsers.service'
import { JanelaDaAgendaField } from './components/JanelaDaAgendaField'

/**
 * Quem entra no painel, e até onde cada um enxerga a agenda.
 *
 * O administrador não aparece como editável: a janela é um limite de
 * funcionário, e oferecer o campo para quem não tem limite só confundiria.
 */
export function UsuariosPage() {
  const { data: usuarios, isLoading, isError, error, refetch } = useClinicUsers()
  const [aviso, setAviso] = useState<string | null>(null)

  if (isLoading) {
    return (
      <div className="p-6 space-y-3">
        <Cabecalho />
        <SkeletonTable rows={4} />
      </div>
    )
  }

  if (isError) {
    return (
      <div className="p-6 space-y-3">
        <Cabecalho />
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar usuários.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  const lista = usuarios ?? []
  const funcionarios = lista.filter((u) => u.role === 'STAFF')
  const admins = lista.filter((u) => u.role === 'ADMIN')

  return (
    <div className="p-6 space-y-5">
      <Cabecalho />

      {aviso && (
        <p className="rounded-lg bg-brand-50 border border-brand-200 px-4 py-2.5 text-sm text-brand-900">
          {aviso}
        </p>
      )}

      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-gray-700">Funcionários</h2>
        {funcionarios.length === 0 ? (
          <Vazio />
        ) : (
          <ul className="space-y-2">
            {funcionarios.map((u) => (
              <LinhaDeFuncionario key={u.id} usuario={u} onAviso={setAviso} />
            ))}
          </ul>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-semibold text-gray-700">Administradores</h2>
        <ul className="space-y-2">
          {admins.map((u) => (
            <li
              key={u.id}
              className="rounded-lg border border-gray-200 bg-white px-4 py-3 flex items-center justify-between"
            >
              <div>
                <p className="text-sm font-medium text-gray-900">{u.name || u.email}</p>
                <p className="text-xs text-gray-400">{u.email}</p>
              </div>
              <span className="text-xs font-medium text-gray-400">
                acesso completo
              </span>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}

function Cabecalho() {
  return (
    <div>
      <h1 className="text-2xl font-bold tracking-tight text-gray-900">Usuários</h1>
      <p className="text-sm text-gray-400 mt-0.5">
        Quem entra no painel e até onde cada funcionário enxerga a agenda
      </p>
    </div>
  )
}

function Vazio() {
  return (
    <div className="rounded-lg border border-dashed border-gray-200 px-4 py-6 text-center">
      <p className="text-sm text-gray-500">Nenhum funcionário cadastrado.</p>
      <p className="text-xs text-gray-400 mt-1">
        Contas de funcionário são criadas pela equipe técnica.
      </p>
    </div>
  )
}

function Interruptor({
  ligado,
  rotulo,
  ajuda,
  desabilitado,
  onChange,
}: {
  ligado: boolean
  rotulo: string
  ajuda: string
  desabilitado: boolean
  onChange: (valor: boolean) => void
}) {
  return (
    <label className="flex items-start gap-2 text-xs text-gray-600 cursor-pointer max-w-xs">
      <input
        type="checkbox"
        checked={ligado}
        disabled={desabilitado}
        onChange={(e) => onChange(e.target.checked)}
        className="rounded border-gray-300 mt-0.5"
      />
      <span>
        {rotulo}
        <span className="block text-[11px] leading-snug text-gray-400">{ajuda}</span>
      </span>
    </label>
  )
}


function LinhaDeFuncionario({
  usuario,
  onAviso,
}: {
  usuario: UsuarioDaClinica
  onAviso: (texto: string) => void
}) {
  const { mutate, isPending } = useUpdateClinicUser()

  const salvar = (dados: Parameters<typeof mutate>[0]['dados']) => {
    mutate(
      { userId: usuario.id, dados },
      { onSuccess: (r) => onAviso(r.message) },
    )
  }

  return (
    <li className="rounded-lg border border-gray-200 bg-white px-4 py-3 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-gray-900">
            {usuario.name || usuario.email}
          </p>
          <p className="text-xs text-gray-400">{usuario.email}</p>
        </div>

        <label className="flex items-center gap-2 text-xs text-gray-600 cursor-pointer shrink-0">
          <input
            type="checkbox"
            checked={usuario.active}
            disabled={isPending}
            onChange={(e) => salvar({ active: e.target.checked })}
            className="rounded border-gray-300"
          />
          {usuario.active ? 'Ativo' : 'Desativado'}
        </label>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-2">
        <Interruptor
          ligado={usuario.can_see_prices}
          rotulo="Ve valores em reais"
          ajuda="Preco do agendamento e dos servicos. Relatorio financeiro continua fechado."
          desabilitado={isPending}
          onChange={(v) => salvar({ can_see_prices: v })}
        />
        <Interruptor
          ligado={usuario.can_see_patient_list}
          rotulo="Ve a lista de pacientes"
          ajuda="Desligado, ela ainda agenda pelo telefone e ainda registra sessao pela agenda."
          desabilitado={isPending}
          onChange={(v) => salvar({ can_see_patient_list: v })}
        />
      </div>

      <JanelaDaAgendaField
        key={`${usuario.agenda_days_ahead}-${usuario.agenda_visible_until}`}
        dias={usuario.agenda_days_ahead}
        ate={usuario.agenda_visible_until}
        salvando={isPending}
        onChange={salvar}
      />
    </li>
  )
}
