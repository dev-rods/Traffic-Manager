import { useMemo, useState } from 'react'
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { useClinic } from '@/hooks/useClinic'
import { useProfessionals } from '@/hooks/useProfessionals'
import { useProtocoloLaser } from '@/hooks/useProtocoloLaser'
import {
  useAplicacoesDoAgendamento,
  useCreateSessionRecord,
  useUpdateSessionRecord,
} from '@/hooks/useSessionRecords'
import type {
  AplicacaoDeSessao,
  RegistroDeSessao,
  SessaoSemRegistro,
  ClinicArea,
  SkinType,
} from '@/types'
import { paraPayload } from '@/lib/prontuario'
import { normaliza, pendenciasDoRegistro, resumoDasPendencias } from '@/lib/aplicacoes'
import { ordenaPendentes, rotuloDaSessao, sessaoPreSelecionada } from '@/lib/sessoesPendentes'
import { todayStr } from '@/utils/dateHelpers'
import { AplicacoesField } from './AplicacoesField'
import { AvisosDoProtocolo } from './AvisosDoProtocolo'

const MANUAL = 'manual'

interface RegistroDeSessaoModalProps {
  patientId: string
  skinType: SkinType | null
  areas: ClinicArea[]
  sessoesSemRegistro: SessaoSemRegistro[]
  /** Vem escolhida no seletor, se ainda estiver pendente. Senão, a mais recente até hoje. */
  agendamentoDeOrigem?: string | null
  registro?: RegistroDeSessao | null
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
  agendamentoDeOrigem,
  registro,
  onClose,
}: RegistroDeSessaoModalProps) {
  const editando = Boolean(registro)
  const criar = useCreateSessionRecord(patientId)
  const editar = useUpdateSessionRecord()
  const buscaAplicacoes = useAplicacoesDoAgendamento()
  const { data: protocolo } = useProtocoloLaser()
  const { data: profissionais } = useProfessionals()
  const { data: clinica } = useClinic()

  const parametros = useMemo(() => protocolo?.parameters ?? [], [protocolo])
  const mapaDeAreas = useMemo(() => {
    const m = new Map<string, string>()
    for (const l of protocolo?.area_map ?? []) m.set(l.area_id, l.protocol_area_key)
    return m
  }, [protocolo])

  // Quem escolhe a sessão é o seletor, e só ele (PRD 042). Até 08/11/2026 o
  // atalho da agenda pré-selecionava aqui, sem passar por `escolheSessao`: o
  // item aparecia marcado e a lista de áreas vinha vazia, então a aplicadora
  // tinha de adicionar área por área. Um caminho só, uma regra só.
  const [appointmentId, setAppointmentId] = useState<string | null>(
    registro?.appointment_id ?? null,
  )
  const [sessionDate, setSessionDate] = useState(registro?.session_date ?? '')
  // `null` = ninguém mexeu no seletor: vale a padrão da clínica, só ao criar.
  // Editar mostra o que foi gravado, mesmo que seja "Não informado".
  const [escolhida, setProfessionalId] = useState<string | null>(
    registro ? (registro.professional_id ?? '') : null,
  )
  const padraoDaClinica = (profissionais ?? []).some(
    (p) => p.id === clinica?.default_professional_id,
  )
    ? (clinica?.default_professional_id ?? '')
    : ''
  const professionalId = escolhida ?? padraoDaClinica
  const [bronzeada, setBronzeada] = useState(registro?.tanned_skin ?? false)
  const [notes, setNotes] = useState(registro?.notes ?? '')
  const [aplicacoes, setAplicacoes] = useState<AplicacaoDeSessao[]>(
    registro?.applications ?? [],
  )
  const [erro, setErro] = useState<string | null>(null)
  // Enquanto o backend monta as áreas da sessão escolhida (PRD 051).
  const [montando, setMontando] = useState(false)
  // As pendências só aparecem depois da primeira tentativa de salvar: durante
  // a digitação nada acusa (mesma lição do PRD 050).
  const [tentouSalvar, setTentouSalvar] = useState(false)

  const [preselecionada, setPreselecionada] = useState(editando)
  const [pendentes] = useState(() => ordenaPendentes(sessoesSemRegistro))
  const [padrao] = useState(
    () =>
      pendentes.find((s) => s.id === agendamentoDeOrigem) ??
      sessaoPreSelecionada(pendentes, todayStr()),
  )

  function sessaoPorId(id: string | null | undefined) {
    return pendentes.find((s) => s.id === id)
  }

  /**
   * Escolher a sessão traz data e áreas prontas.
   *
   * As áreas vêm montadas do backend (PRD 051): nome comercial, protocolo de
   * referência, método quando é um só e a sugestão pela pele. Até 19/11/2026 a
   * tela montava por conta própria, casando nomes por string, e trocava o nome
   * comercial pelo do protocolo ("Perna Completa" virava "Meia perna").
   */
  const escolheSessao = async (id: string | null) => {
    setAppointmentId(id)
    const sessao = sessaoPorId(id)
    if (!sessao) return
    setSessionDate(sessao.appointment_date)
    setMontando(true)
    try {
      setAplicacoes(await buscaAplicacoes(sessao.id))
      setErro(null)
    } catch {
      setAplicacoes([])
      setErro('Não foi possível carregar as áreas do agendamento. Adicione-as manualmente.')
    } finally {
      setMontando(false)
    }
  }

  // Pré-seleciona a sessão de onde ela veio (agenda) ou, sem ela, a pendente
  // mais recente até hoje. Passa por `escolheSessao` (um caminho só, PRD 042),
  // uma vez, e respeita quem já escolheu.
  if (!preselecionada && padrao) {
    setPreselecionada(true)
    void escolheSessao(padrao.id)
  }

  const pendencias = tentouSalvar ? pendenciasDoRegistro(normaliza(aplicacoes)) : []

  const salvando = criar.isPending || editar.isPending

  const submete = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!sessionDate) {
      setErro('Informe a data da sessão.')
      return
    }
    // Nenhum registro incompleto (PRD 051): o backend recusa igual, mas aqui
    // dá para apontar o campo.
    const faltam = pendenciasDoRegistro(normaliza(aplicacoes))
    if (faltam.length > 0) {
      setTentouSalvar(true)
      setErro(resumoDasPendencias(faltam))
      return
    }
    setErro(null)

    const payload = {
      appointmentId,
      sessionDate,
      professionalId: professionalId || null,
      tannedSkin: bronzeada,
      notes,
      applications: normaliza(aplicacoes).map(paraPayload),
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

  // HR em QUALQUER linha manda: os avisos são dele. Com vários métodos por
  // área (PRD 030), olhar só o primeiro escondia o aviso de quem pôs HR
  // depois de um SHR.
  const metodoEmUso = aplicacoes.some((a) => a.method === 'HR')
    ? 'HR'
    : (aplicacoes.find((a) => a.method)?.method ?? null)

  return (
    <Modal open onClose={onClose} title={editando ? 'Editar registro' : 'Novo registro de sessão'}>
      <form onSubmit={submete} className="space-y-5">
        {!editando && pendentes.length > 0 && (
          <label className="flex flex-col gap-1">
            <span className="text-xs font-medium text-gray-500">Qual sessão?</span>
            <select
              value={appointmentId ?? MANUAL}
              onChange={(e) => {
                setPreselecionada(true)
                void escolheSessao(e.target.value === MANUAL ? null : e.target.value)
              }}
              className="rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-800"
            >
              {pendentes.map((s) => (
                <option key={s.id} value={s.id}>
                  {rotuloDaSessao(s)} · {s.areas || 'sem áreas'}
                </option>
              ))}
              <option value={MANUAL}>Registrar manual</option>
            </select>
          </label>
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

        {montando && (
          <p className="text-xs text-gray-400" role="status">
            Carregando áreas do agendamento…
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
          pendencias={pendencias}
          disabled={salvando || montando}
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
