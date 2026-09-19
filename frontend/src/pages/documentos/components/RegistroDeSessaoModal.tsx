import { useMemo, useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { useProfessionals } from '@/hooks/useProfessionals'
import { useProtocoloLaser } from '@/hooks/useProtocoloLaser'
import { useCreateSessionRecord, useUpdateSessionRecord } from '@/hooks/useSessionRecords'
import type {
  AplicacaoDeSessao,
  RegistroDeSessao,
  SessaoSemRegistro,
  ClinicArea,
  SkinType,
} from '@/types'
import { metodosDaArea, sugestao } from '@/lib/protocolo'
import { paraPayload } from '@/lib/prontuario'
import { AplicacoesField } from './AplicacoesField'
import { AvisosDoProtocolo } from './AvisosDoProtocolo'

interface RegistroDeSessaoModalProps {
  patientId: string
  skinType: SkinType | null
  areas: ClinicArea[]
  sessoesSemRegistro: SessaoSemRegistro[]
  registro?: RegistroDeSessao | null
  /** Abre já com este agendamento escolhido (atalho vindo da Agenda). */
  agendamentoInicial?: string | null
  onClose: () => void
}

/**
 * Criar ou editar um registro de sessão.
 *
 * O ponto da tela é preencher quase sozinha: escolhida a sessão, as áreas vêm
 * do agendamento e cada uma traz o parâmetro do protocolo conforme o tipo de
 * pele. A profissional confere e salva.
 */
export function RegistroDeSessaoModal({
  patientId,
  skinType,
  areas,
  sessoesSemRegistro,
  registro,
  agendamentoInicial,
  onClose,
}: RegistroDeSessaoModalProps) {
  const editando = Boolean(registro)
  const criar = useCreateSessionRecord(patientId)
  const editar = useUpdateSessionRecord()
  const { data: protocolo } = useProtocoloLaser()
  const { data: profissionais } = useProfessionals()

  const parametros = useMemo(() => protocolo?.parameters ?? [], [protocolo])
  const mapaDeAreas = useMemo(() => {
    const m = new Map<string, string>()
    for (const l of protocolo?.area_map ?? []) m.set(l.area_id, l.protocol_area_key)
    return m
  }, [protocolo])

  const [appointmentId, setAppointmentId] = useState<string | null>(
    registro?.appointment_id ?? agendamentoInicial ?? null,
  )
  const [sessionDate, setSessionDate] = useState(
    registro?.session_date ?? sessaoPorId(agendamentoInicial)?.appointment_date ?? '',
  )
  const [professionalId, setProfessionalId] = useState(registro?.professional_id ?? '')
  const [bronzeada, setBronzeada] = useState(registro?.tanned_skin ?? false)
  const [notes, setNotes] = useState(registro?.notes ?? '')
  const [aplicacoes, setAplicacoes] = useState<AplicacaoDeSessao[]>(
    registro?.applications ?? [],
  )
  const [erro, setErro] = useState<string | null>(null)

  function sessaoPorId(id: string | null | undefined) {
    return sessoesSemRegistro.find((s) => s.id === id)
  }

  /**
   * Escolher a sessão traz data e áreas prontas.
   *
   * A expansão da composta acontece aqui e no backend pela mesma tabela: a
   * `Virilha Completa + ânus` vira duas aplicações, virilha no SHR e perianal
   * no Stacking, porque é o que ela de fato aplica.
   */
  const escolheSessao = (id: string | null) => {
    setAppointmentId(id)
    const sessao = sessaoPorId(id)
    if (!sessao) return
    setSessionDate(sessao.appointment_date)

    const nomes = sessao.areas.split(',').map((n) => n.trim()).filter(Boolean)
    const novas: AplicacaoDeSessao[] = []
    for (const nome of nomes) {
      const area = areas.find((a) => a.name === nome)
      const chaves = area
        ? (protocolo?.area_map ?? [])
            .filter((l) => l.area_id === area.id)
            .sort((a, b) => a.display_order - b.display_order)
            .map((l) => l.protocol_area_key)
        : []

      if (chaves.length === 0) {
        novas.push(vazia(nome, area?.id ?? null, null, novas.length))
        continue
      }
      for (const chave of chaves) {
        const metodos = metodosDaArea(parametros, chave)
        const metodo = metodos.length === 1 ? metodos[0] : null
        const s = sugestao(parametros, chave, metodo, skinType)
        novas.push({
          area_id: area?.id ?? null,
          area_name: nomeDoProtocolo(chave) ?? nome,
          protocol_area_key: chave,
          method: metodo,
          fluence_j: s?.fluence_j ?? null,
          energy_kj: s?.energy_kj ?? null,
          stacks: s?.stacks ?? null,
          passes: s?.passes ?? null,
          display_order: novas.length,
        })
      }
    }
    setAplicacoes(novas)
  }

  function nomeDoProtocolo(chave: string) {
    return parametros.find((p) => p.protocol_area_key === chave)?.protocol_area_name
  }

  function vazia(
    nome: string,
    areaId: string | null,
    chave: string | null,
    ordem: number,
  ): AplicacaoDeSessao {
    return {
      area_id: areaId,
      area_name: nome,
      protocol_area_key: chave,
      method: null,
      fluence_j: null,
      energy_kj: null,
      stacks: null,
      passes: null,
      display_order: ordem,
    }
  }

  const salvando = criar.isPending || editar.isPending

  const submete = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!sessionDate) {
      setErro('Informe a data da sessão.')
      return
    }
    setErro(null)

    const payload = {
      appointmentId,
      sessionDate,
      professionalId: professionalId || null,
      tannedSkin: bronzeada,
      notes,
      applications: aplicacoes.map(paraPayload),
      changedBy: nomeDoProfissional(professionalId),
    }

    try {
      if (registro) {
        await editar.mutateAsync({ recordId: registro.id, payload })
      } else {
        await criar.mutateAsync(payload)
      }
      onClose()
    } catch (err: unknown) {
      const detalhe =
        err && typeof err === 'object' && 'response' in err
          ? (err as { response: { data?: { message?: string } } }).response.data?.message
          : null
      setErro(detalhe ?? 'Não foi possível salvar o registro.')
    }
  }

  function nomeDoProfissional(id: string) {
    return profissionais?.find((p) => p.id === id)?.name ?? undefined
  }

  const metodoEmUso = aplicacoes.find((a) => a.method)?.method ?? null

  return (
    <Modal open onClose={onClose} title={editando ? 'Editar registro' : 'Novo registro de sessão'}>
      <form onSubmit={submete} className="space-y-5">
        {!editando && sessoesSemRegistro.length > 0 && (
          <fieldset>
            <legend className="mb-1.5 text-xs font-medium text-gray-500">De qual sessão?</legend>
            <div className="space-y-1.5">
              {sessoesSemRegistro.map((s) => (
                <label key={s.id} className="flex cursor-pointer items-start gap-2.5">
                  <input
                    type="radio"
                    name="sessao"
                    checked={appointmentId === s.id}
                    onChange={() => escolheSessao(s.id)}
                    className="mt-0.5 accent-brand-500"
                  />
                  <span className="text-sm text-gray-700">
                    {s.appointment_date} · {s.start_time?.slice(0, 5)}
                    <span className="block text-xs text-gray-400">{s.areas || 'sem áreas'}</span>
                  </span>
                </label>
              ))}
              <label className="flex cursor-pointer items-center gap-2.5">
                <input
                  type="radio"
                  name="sessao"
                  checked={appointmentId === null}
                  onChange={() => setAppointmentId(null)}
                  className="accent-brand-500"
                />
                <span className="text-sm text-gray-700">Sessão feita fora do sistema</span>
              </label>
            </div>
          </fieldset>
        )}

        <div className="flex flex-wrap gap-4">
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-gray-500">Data</span>
            <input
              type="date"
              value={sessionDate}
              onChange={(e) => setSessionDate(e.target.value)}
              className="rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800"
            />
          </label>

          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-gray-500">Profissional</span>
            <select
              value={professionalId}
              onChange={(e) => setProfessionalId(e.target.value)}
              className="rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800"
            >
              <option value="">Não informado</option>
              {(profissionais ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label className="flex cursor-pointer items-center gap-2.5">
          <input
            type="checkbox"
            checked={bronzeada}
            onChange={(e) => setBronzeada(e.target.checked)}
            className="h-4 w-4 accent-amber-500"
          />
          <span className="text-sm text-gray-700">Pele bronzeada nesta sessão</span>
        </label>

        <AvisosDoProtocolo metodo={metodoEmUso} skinType={skinType} bronzeada={bronzeada} />

        {!skinType && (
          <p className="rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-500">
            Esta paciente ainda não tem o tipo de pele marcado, então não há
            parâmetro sugerido. Marque no cadastro para a tela sugerir.
          </p>
        )}

        <AplicacoesField
          aplicacoes={aplicacoes}
          onChange={setAplicacoes}
          parametros={parametros}
          areas={areas}
          mapaDeAreas={mapaDeAreas}
          skinType={skinType}
          bronzeada={bronzeada}
          disabled={salvando}
        />

        <label className="block">
          <span className="mb-1.5 block text-xs font-medium text-gray-500">Observações</span>
          <textarea
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={3}
            placeholder="Ex: sem intercorrências, pele reagiu bem…"
            className="w-full resize-none rounded-lg border border-gray-200 px-3 py-2.5 text-sm text-gray-800"
          />
        </label>

        {erro && <p className="text-sm text-red-600">{erro}</p>}

        <div className="flex justify-end gap-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={salvando}>
            Cancelar
          </Button>
          <Button type="submit" loading={salvando}>
            Salvar
          </Button>
        </div>
      </form>
    </Modal>
  )
}
