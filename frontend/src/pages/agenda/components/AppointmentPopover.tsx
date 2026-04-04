import { useEffect, useRef } from 'react'
import { formatCurrency } from '@/utils/formatCurrency'
import type { Appointment } from '@/types'

const DISCOUNT_LABELS: Record<string, string> = {
  first_session: '1a sessao',
  tier_2: '2-4 areas',
  tier_3: '5+ areas',
  partnership: 'Parceria',
}

interface AppointmentPopoverProps {
  appointment: Appointment | null
  anchorRect: DOMRect | null
  onClose: () => void
  onEdit: (appointment: Appointment) => void
  onCancel: (appointment: Appointment) => void
}

export function AppointmentPopover({ appointment, anchorRect, onClose, onEdit, onCancel }: AppointmentPopoverProps) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!appointment) return

    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose()
      }
    }
    function handleEsc(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }

    document.addEventListener('mousedown', handleClickOutside)
    document.addEventListener('keydown', handleEsc)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
      document.removeEventListener('keydown', handleEsc)
    }
  }, [appointment, onClose])

  if (!appointment || !anchorRect) return null

  const a = appointment
  const displayName = a.patient_name || a.full_name || 'Sem nome'
  const serviceLine = [a.service_name, a.areas].filter(Boolean).join(' · ')
  const timeSlot = `${a.start_time.slice(0, 5)}–${a.end_time.slice(0, 5)}`
  const isCancelled = a.status === 'CANCELLED'

  // Position the popover near the anchor
  const top = Math.min(anchorRect.top, window.innerHeight - 400)
  const left = anchorRect.right + 8

  return (
    <div className="fixed inset-0 z-50">
      <div
        ref={ref}
        className="absolute bg-white rounded-xl shadow-xl border border-gray-200 w-80 animate-in fade-in"
        style={{ top: `${Math.max(top, 8)}px`, left: `${Math.min(left, window.innerWidth - 340)}px` }}
      >
        {/* Header */}
        <div className="flex items-start justify-between p-4 pb-2">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <p className="font-semibold text-gray-800 truncate">{displayName}</p>
              {a.discount_reason === 'partnership' && (
                <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-100 text-amber-700 flex-shrink-0">
                  PARCERIA
                </span>
              )}
            </div>
            {serviceLine && <p className="text-sm text-gray-500">{serviceLine}</p>}
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-lg leading-none ml-2 cursor-pointer"
          >
            x
          </button>
        </div>

        {/* Details */}
        <div className="px-4 pb-3 space-y-1.5 text-sm">
          <div className="flex justify-between">
            <span className="text-gray-400">Horario</span>
            <span className="font-medium text-gray-800">{timeSlot}</span>
          </div>
          {a.professional_name && (
            <div className="flex justify-between">
              <span className="text-gray-400">Profissional</span>
              <span className="font-medium text-gray-800">{a.professional_name}</span>
            </div>
          )}
          <div className="flex justify-between">
            <span className="text-gray-400">Status</span>
            <span className={isCancelled ? 'font-medium text-red-500' : 'font-medium text-emerald-600'}>
              {isCancelled ? 'Cancelado' : 'Confirmado'}
            </span>
          </div>
        </div>

        {/* Price breakdown */}
        {a.final_price_cents != null && a.final_price_cents > 0 && (
          <div className="mx-4 mb-3 rounded-lg bg-gray-50 p-3 text-sm space-y-1">
            {a.original_price_cents != null && (
              <div className="flex justify-between">
                <span className="text-gray-500">Valor de tabela</span>
                <span className="text-gray-800">{formatCurrency(a.original_price_cents)}</span>
              </div>
            )}
            {a.discount_pct > 0 && a.original_price_cents != null && (
              <div className="flex justify-between text-emerald-600">
                <span>
                  -{a.discount_pct}% ({DISCOUNT_LABELS[a.discount_reason ?? ''] ?? a.discount_reason})
                </span>
                <span>-{formatCurrency(a.original_price_cents - a.final_price_cents)}</span>
              </div>
            )}
            <div className="flex justify-between font-semibold border-t border-gray-200 pt-1 mt-1">
              <span className="text-gray-800">Total</span>
              <span className="text-brand-600">{formatCurrency(a.final_price_cents)}</span>
            </div>
          </div>
        )}

        {/* Notes */}
        {a.notes && (
          <div className="px-4 pb-3">
            <p className="text-xs text-gray-400 mb-1">Observações</p>
            <p className="text-sm text-gray-600">{a.notes}</p>
          </div>
        )}

        {/* Actions */}
        <div className="border-t border-gray-100 p-2 space-y-0.5">
          {!isCancelled && (
            <>
              <button
                onClick={() => { onEdit(a); onClose() }}
                className="w-full text-left px-3 py-2 rounded-lg text-sm text-gray-700 hover:bg-gray-50 transition-colors cursor-pointer"
              >
                Editar agendamento
              </button>
              <button
                onClick={() => { onCancel(a); onClose() }}
                className="w-full text-left px-3 py-2 rounded-lg text-sm text-red-500 hover:bg-red-50 transition-colors cursor-pointer"
              >
                Cancelar agendamento
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
