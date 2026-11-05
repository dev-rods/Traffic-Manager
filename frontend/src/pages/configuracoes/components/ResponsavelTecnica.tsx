import { useState } from 'react'
import { useProfessionals, useUpdateProfessional } from '@/hooks/useProfessionals'
import type { Professional } from '@/services/professionals.service'

interface ResponsavelTecnicaProps {
  responsibleProfessionalId: string | null
  cidade: string
  onChange: (key: 'responsible_professional_id' | 'cidade', value: string | null) => void
}

/**
 * Responsável técnica, cidade e registro no conselho (PRD 036): o que vai
 * impresso no termo de consentimento. Responsável e cidade são salvos com o
 * resto do formulário; o registro é salvo por linha, porque é dado da
 * profissional e não da clínica.
 */
export function ResponsavelTecnica({ responsibleProfessionalId, cidade, onChange }: ResponsavelTecnicaProps) {
  const { data: profissionais, isLoading, isError } = useProfessionals()

  const lista = profissionais ?? []
  const responsavel = lista.find((p) => p.id === responsibleProfessionalId) ?? null
  const faltas: string[] = []
  if (!responsavel) faltas.push('a profissional responsável')
  if (responsavel && !responsavel.registro_conselho) faltas.push('o registro no conselho dela')
  if (!cidade.trim()) faltas.push('a cidade')

  return (
    <div className="space-y-4">
      {!isLoading && !isError && faltas.length > 0 && (
        <p role="status" className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Falta {faltas.join(', ')}. Sem isso o termo não é gerado no check-in.
        </p>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label htmlFor="responsavel-tecnica" className="text-xs font-medium text-gray-500 block mb-1.5">
            Profissional responsável
          </label>
          <select
            id="responsavel-tecnica"
            value={responsibleProfessionalId ?? ''}
            disabled={isLoading || isError}
            onChange={(e) => onChange('responsible_professional_id', e.target.value || null)}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 disabled:bg-gray-50"
          >
            <option value="">Nenhuma</option>
            {lista.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
                {p.role ? ` (${p.role})` : ''}
              </option>
            ))}
          </select>
          {isError && <p className="text-[11px] text-red-500 mt-1">Não foi possível carregar as profissionais.</p>}
        </div>
        <div>
          <label htmlFor="cidade-do-termo" className="text-xs font-medium text-gray-500 block mb-1.5">
            Cidade
          </label>
          <input
            id="cidade-do-termo"
            type="text"
            value={cidade}
            maxLength={120}
            onChange={(e) => onChange('cidade', e.target.value)}
            placeholder="Como aparece no termo: São Paulo"
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
          />
        </div>
      </div>

      {lista.length > 0 && (
        <div>
          <p className="text-xs font-medium text-gray-500 mb-1.5">Registro no conselho, por profissional</p>
          <ul className="divide-y divide-gray-100 rounded-lg border border-gray-200">
            {lista.map((p) => (
              <RegistroDaProfissional key={p.id} profissional={p} />
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function RegistroDaProfissional({ profissional: p }: { profissional: Professional }) {
  const atualizar = useUpdateProfessional()
  const [registro, setRegistro] = useState(p.registro_conselho ?? '')
  const mudou = registro.trim() !== (p.registro_conselho ?? '')

  return (
    <li className="flex items-center gap-3 px-3 py-2">
      <span className="min-w-0 flex-1 truncate text-sm text-gray-800">
        {p.name}
        {p.role && <span className="ml-1 text-xs text-gray-400">{p.role}</span>}
      </span>
      <input
        type="text"
        aria-label={`Registro no conselho de ${p.name}`}
        value={registro}
        maxLength={60}
        onChange={(e) => setRegistro(e.target.value)}
        placeholder="Ex.: CRBM 12345"
        className="w-44 border border-gray-200 rounded-lg px-3 py-2 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
      />
      <button
        type="button"
        disabled={!mudou || atualizar.isPending}
        onClick={() =>
          atualizar.mutate({ id: p.id, payload: { registro_conselho: registro.trim() || null } })
        }
        className="rounded-lg px-3 py-2 text-xs font-semibold text-brand-600 hover:bg-brand-50 disabled:text-gray-300 disabled:hover:bg-transparent cursor-pointer disabled:cursor-not-allowed"
      >
        {atualizar.isPending ? 'Salvando…' : atualizar.isSuccess && !mudou ? 'Salvo' : 'Salvar'}
      </button>
    </li>
  )
}
