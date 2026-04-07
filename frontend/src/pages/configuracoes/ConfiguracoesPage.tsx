import { useState } from 'react'
import { useClinic, useUpdateClinic } from '@/hooks/useClinic'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { ErrorState } from '@/components/ui/ErrorState'
import { Button } from '@/components/ui/Button'
import { Switch } from '@/components/ui/Switch'
import type { UpdateClinicPayload } from '@/types'
import { buildDefaultMessage } from '@/pages/pacientes/components/BatchMessageModal'

function buildFormFromClinic(clinic: NonNullable<ReturnType<typeof useClinic>['data']>): UpdateClinicPayload {
  return {
    name: clinic.name ?? '',
    display_name: clinic.display_name ?? '',
    phone: clinic.phone ?? '',
    address: clinic.address ?? '',
    buffer_minutes: clinic.buffer_minutes ?? 10,
    max_future_dates: clinic.max_future_dates ?? 5,
    max_session_minutes: clinic.max_session_minutes ?? 120,
    pre_session_instructions: clinic.pre_session_instructions ?? '',
    zapi_instance_id: clinic.zapi_instance_id ?? '',
    zapi_instance_token: clinic.zapi_instance_token ?? '',
    use_agent: clinic.use_agent ?? false,
    batch_message_template: clinic.batch_message_template ?? '',
  }
}

export function ConfiguracoesPage() {
  const { data: clinic, isLoading, isError, error, refetch } = useClinic()
  const updateClinic = useUpdateClinic()

  const [form, setForm] = useState<UpdateClinicPayload>({})
  const [saved, setSaved] = useState(false)
  const [prevClinicId, setPrevClinicId] = useState<string | null>(null)

  // Derived state pattern — populate form when clinic data loads
  if (clinic && clinic.clinic_id !== prevClinicId) {
    setPrevClinicId(clinic.clinic_id)
    setForm(buildFormFromClinic(clinic))
  }

  const set = (key: keyof UpdateClinicPayload, value: string | number | boolean) => {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  const handleSave = async () => {
    setSaved(false)
    await updateClinic.mutateAsync(form)
    setSaved(true)
    setTimeout(() => setSaved(false), 3000)
  }

  if (isLoading) return <div className="p-6"><SkeletonTable rows={8} /></div>
  if (isError) {
    return (
      <div className="p-6">
        <ErrorState
          message={error instanceof Error ? error.message : 'Erro ao carregar configurações.'}
          onRetry={() => refetch()}
        />
      </div>
    )
  }

  return (
    <div className="p-6">
      <div className="mb-8">
        <h1 className="text-2xl font-bold tracking-tight text-gray-900">Configurações</h1>
        <p className="text-sm text-gray-400 mt-1">Dados e preferências da sua clínica</p>
      </div>

      <div className="space-y-8">
        {/* General info */}
        <Section title="Dados gerais" description="Informações básicas da clínica">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Nome" value={form.name as string} onChange={(v) => set('name', v)} />
            <Field label="Nome de exibição" value={form.display_name as string} onChange={(v) => set('display_name', v)} placeholder="Como aparece para o paciente" />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Telefone" value={form.phone as string} onChange={(v) => set('phone', v)} />
            <Field label="Endereço" value={form.address as string} onChange={(v) => set('address', v)} />
          </div>
        </Section>

        <hr className="border-gray-100" />

        {/* Scheduling */}
        <Section title="Agendamento" description="Parâmetros que afetam a disponibilidade de horários">
          <div className="grid grid-cols-3 gap-4">
            <NumberField
              label="Buffer (min)"
              value={form.buffer_minutes as number}
              onChange={(v) => set('buffer_minutes', v)}
              min={0}
              max={120}
              help="Intervalo entre agendamentos"
            />
            <NumberField
              label="Datas futuras"
              value={form.max_future_dates as number}
              onChange={(v) => set('max_future_dates', v)}
              min={1}
              max={90}
              help="Máx. dias que o paciente vê"
            />
            <NumberField
              label="Sessão máx. (min)"
              value={form.max_session_minutes as number}
              onChange={(v) => set('max_session_minutes', v)}
              min={15}
              max={480}
              help="Duração máxima de uma sessão"
            />
          </div>
        </Section>

        <hr className="border-gray-100" />

        {/* Pre-session instructions */}
        <Section title="Instruções pré-sessão" description="Enviadas ao paciente antes do agendamento">
          <textarea
            value={form.pre_session_instructions as string}
            onChange={(e) => set('pre_session_instructions', e.target.value)}
            rows={3}
            placeholder="Instruções gerais enviadas antes de cada sessão..."
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 resize-none"
          />
        </Section>

        <hr className="border-gray-100" />

        {/* z-api Integration */}
        <Section title="Integração z-api" description="Credenciais para conexão com o WhatsApp via z-api">
          <div className="grid grid-cols-2 gap-4">
            <Field label="Instance ID" value={form.zapi_instance_id as string} onChange={(v) => set('zapi_instance_id', v)} placeholder="ID da instância z-api" />
            <Field label="Instance Token" value={form.zapi_instance_token as string} onChange={(v) => set('zapi_instance_token', v)} placeholder="Token da instância z-api" />
          </div>
        </Section>

        <hr className="border-gray-100" />

        {/* Batch WhatsApp message template */}
        <Section title="Mensagem WhatsApp em lote" description="Template padrão para envio em lote. Use {nome} para o primeiro nome do paciente.">
          <textarea
            value={form.batch_message_template as string}
            onChange={(e) => set('batch_message_template', e.target.value)}
            rows={4}
            placeholder={buildDefaultMessage([])}
            className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 resize-none"
          />
          <p className="text-[11px] text-gray-400">Deixe vazio para usar a mensagem padrão com as datas disponíveis.</p>
        </Section>

        <hr className="border-gray-100" />

        {/* AI Agent — inline toggle, no section wrapper */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-semibold text-gray-800">Agente de IA</p>
            <p className="text-xs text-gray-400 mt-0.5">Usa inteligência artificial para conduzir conversas no WhatsApp</p>
          </div>
          <Switch
            checked={!!form.use_agent}
            onChange={(v) => set('use_agent', v)}
            label="Agente de IA"
          />
        </div>

        {/* Save */}
        <div className="flex items-center gap-3 pt-2">
          <Button onClick={() => void handleSave()} loading={updateClinic.isPending}>
            Salvar configurações
          </Button>
          {saved && <span className="text-sm text-green-600 font-medium">Salvo com sucesso</span>}
          {updateClinic.isError && <span className="text-sm text-red-500">Erro ao salvar</span>}
        </div>
      </div>
    </div>
  )
}

// ── Section wrapper ──────────────────────────────────────────
function Section({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-sm font-semibold text-gray-800">{title}</h2>
        <p className="text-xs text-gray-400 mt-0.5">{description}</p>
      </div>
      {children}
    </section>
  )
}

// ── Field components ─────────────────────────────────────────
function Field({ label, value, onChange, placeholder }: { label: string; value: string; onChange: (v: string) => void; placeholder?: string }) {
  return (
    <div>
      <label className="text-xs font-medium text-gray-500 block mb-1.5">{label}</label>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500"
      />
    </div>
  )
}

function NumberField({ label, value, onChange, min, max, help }: { label: string; value: number; onChange: (v: number) => void; min: number; max: number; help?: string }) {
  return (
    <div>
      <label className="text-xs font-medium text-gray-500 block mb-1.5">{label}</label>
      <input
        type="number"
        value={value}
        onChange={(e) => {
          const v = parseInt(e.target.value, 10)
          if (!isNaN(v) && v >= min && v <= max) onChange(v)
        }}
        min={min}
        max={max}
        className="w-full border border-gray-200 rounded-lg px-3 py-2.5 text-sm text-gray-800 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
      />
      {help && <p className="text-[11px] text-gray-400 mt-1">{help}</p>}
    </div>
  )
}
