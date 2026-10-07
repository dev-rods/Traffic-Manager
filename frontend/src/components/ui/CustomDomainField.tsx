import { useState } from 'react'
import type { CustomDomainStatus } from '@/types'
import { Button } from './Button'

interface CustomDomainFieldProps {
  value: string | null
  status: CustomDomainStatus | undefined
  saving: boolean
  onSave: (domain: string | null) => Promise<void>
  onRefreshStatus: () => void
  warning?: string | null
}

export function CustomDomainField({ value, status, saving, onSave, onRefreshStatus, warning }: CustomDomainFieldProps) {
  const [draft, setDraft] = useState(value ?? '')
  const [saved, setSaved] = useState(false)

  const dirty = draft.trim() !== (value ?? '')

  async function handleSave() {
    setSaved(false)
    await onSave(draft.trim() ? draft.trim() : null)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <input
          type="text"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          placeholder="agendar.suaempresa.com"
          className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800 placeholder:text-gray-300 focus:border-brand-400 focus:outline-none"
        />
        <Button
          type="button"
          variant="secondary"
          size="sm"
          loading={saving}
          disabled={!dirty}
          onClick={() => void handleSave()}
        >
          Salvar
        </Button>
      </div>

      {saved && <p className="text-sm text-green-600 font-medium">Salvo com sucesso</p>}
      {warning && <p className="text-sm text-amber-700">{warning}</p>}

      {value && status?.registered && (
        <div className="rounded-lg border border-gray-200 bg-white p-4 space-y-3">
          <div className="flex items-center gap-2">
            {status.verified ? (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-green-50 px-2.5 py-1 text-xs font-medium text-green-700">
                <span className="h-1.5 w-1.5 rounded-full bg-green-500" aria-hidden />
                Verificado
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-full bg-amber-50 px-2.5 py-1 text-xs font-medium text-amber-700">
                <span className="h-1.5 w-1.5 rounded-full bg-amber-500" aria-hidden />
                Pendente de verificação
              </span>
            )}
            <button
              type="button"
              onClick={onRefreshStatus}
              className="text-xs font-medium text-gray-400 hover:text-gray-700"
            >
              Verificar novamente
            </button>
          </div>

          {!status.verified && status.dns_records.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 mb-2">
                Crie este registro de DNS no painel do seu provedor de domínio:
              </p>
              <div className="overflow-x-auto rounded-md border border-gray-100">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="bg-gray-50 text-gray-400">
                      <th className="px-3 py-1.5 text-left font-medium">Tipo</th>
                      <th className="px-3 py-1.5 text-left font-medium">Nome</th>
                      <th className="px-3 py-1.5 text-left font-medium">Valor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {status.dns_records.map((record, i) => (
                      <tr key={i} className="border-t border-gray-100">
                        <td className="px-3 py-1.5 font-mono text-gray-700">{record.type}</td>
                        <td className="px-3 py-1.5 font-mono text-gray-700">{record.name}</td>
                        <td className="px-3 py-1.5 font-mono text-gray-700 break-all">{record.value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
