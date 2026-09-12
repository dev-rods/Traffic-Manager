import { useState } from 'react'
import { useClinic, useUpdateClinic } from '@/hooks/useClinic'
import { useProfessionals } from '@/hooks/useProfessionals'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { ImageUploadField } from '@/components/ui/ImageUploadField'

export function SiteAgendamentoPage() {
  const { data: clinic, isLoading, isError, error, refetch } = useClinic()
  const professionals = useProfessionals()
  const updateClinic = useUpdateClinic()
  const [savedField, setSavedField] = useState<'logo_url' | 'favicon_url' | null>(null)

  async function handleUploaded(field: 'logo_url' | 'favicon_url', publicUrl: string) {
    setSavedField(null)
    await updateClinic.mutateAsync({ [field]: publicUrl })
    setSavedField(field)
    setTimeout(() => setSavedField((prev) => (prev === field ? null : prev)), 3000)
  }

  if (isLoading) return <div className="p-6"><SkeletonTable rows={4} /></div>
  if (isError || !clinic) {
    return (
      <div className="p-6">
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar o site de agendamento.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Site de Agendamento</h1>
        <p className="text-sm text-gray-400 mt-1">
          Identidade visual da sua página pública de agendamento
        </p>
      </div>

      <div className="space-y-8 max-w-xl">
        <section className="space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-gray-800">Profissional</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Quem atende os agendamentos feitos pelo site público
            </p>
          </div>

          {professionals.isLoading ? (
            <SkeletonTable rows={2} />
          ) : professionals.isError ? (
            <ErrorState
              message="Erro ao carregar profissionais."
              onRetry={() => professionals.refetch()}
            />
          ) : professionals.data && professionals.data.length > 0 ? (
            <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200 bg-white">
              {professionals.data.map((prof) => (
                <li key={prof.id} className="flex items-center justify-between px-4 py-3">
                  <span className="text-sm font-medium text-gray-800">{prof.name}</span>
                  {prof.role ? <span className="text-xs text-gray-400">{prof.role}</span> : null}
                </li>
              ))}
            </ul>
          ) : (
            <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
              <span className="text-amber-500" aria-hidden>
                ⚠
              </span>
              <div>
                <p className="text-sm font-medium text-amber-800">Nenhum profissional cadastrado</p>
                <p className="text-xs text-amber-700 mt-0.5">
                  Cadastre pelo menos um profissional para que ele apareça no site de
                  agendamento dos seus clientes.
                </p>
              </div>
            </div>
          )}
        </section>

        <hr className="border-gray-100" />

        <section className="space-y-4">
          <div>
            <h2 className="text-sm font-semibold text-gray-800">Identidade visual</h2>
            <p className="text-xs text-gray-400 mt-0.5">
              Aparecem para o paciente ao abrir o link de agendamento
            </p>
          </div>

          <ImageUploadField
            clinicId={clinic.clinic_id}
            kind="logo"
            label="Logo da página"
            helpText="Mostrada no topo da página de agendamento. PNG, JPG, SVG ou WebP, até 2MB."
            value={clinic.logo_url}
            previewShape="circle"
            onUploaded={(url) => void handleUploaded('logo_url', url)}
          />

          <ImageUploadField
            clinicId={clinic.clinic_id}
            kind="favicon"
            label="Ícone da aba do navegador"
            helpText="Aparece na aba do navegador quando o paciente abre a página. PNG, ICO ou SVG, até 2MB."
            value={clinic.favicon_url}
            previewShape="square"
            onUploaded={(url) => void handleUploaded('favicon_url', url)}
          />

          {savedField && <p className="text-sm text-green-600 font-medium">Salvo com sucesso</p>}
          {updateClinic.isError && <p className="text-sm text-red-500">Erro ao salvar</p>}
        </section>
      </div>
    </div>
  )
}
