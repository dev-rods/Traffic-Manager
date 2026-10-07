import type { CartItem, ServiceArea } from '@/types'
import { formatCurrencyBRL, formatDuration } from '@/utils/format'
import { getAreasForService } from '@/utils/cartTotals'
import { cx } from '@/utils/cx'

interface AreaPickerProps {
  items: CartItem[]
  serviceAreas: ServiceArea[]
  onToggleArea: (serviceId: string, areaId: string) => void
}

export function AreaPicker({ items, serviceAreas, onToggleArea }: AreaPickerProps) {
  const itemsWithAreas = items
    .map((item) => ({ item, areas: getAreasForService(serviceAreas, item.service.id) }))
    .filter(({ areas }) => areas.length > 0)

  return (
    <div className="flex flex-col gap-6">
      {itemsWithAreas.map(({ item, areas }) => (
        <div key={item.service.id}>
          {itemsWithAreas.length > 1 ? (
            <h3 className="mb-2 font-semibold text-ink-900">{item.service.name}</h3>
          ) : null}
          <div className="flex flex-col divide-y divide-ink-100 rounded-2xl border border-ink-200 bg-white">
            {areas.map((area) => {
              const checked = item.areaIds.includes(area.area_id)
              return (
                <label
                  key={area.area_id}
                  className={cx(
                    'flex cursor-pointer items-center justify-between gap-3 px-4 py-3 text-sm transition-colors',
                    checked ? 'bg-accent-50' : 'hover:bg-ink-50'
                  )}
                >
                  <span className="flex items-center gap-3">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => onToggleArea(item.service.id, area.area_id)}
                      className="h-4 w-4 accent-accent-600"
                    />
                    <span className="text-ink-800">{area.area_name}</span>
                  </span>
                  <span className="shrink-0 text-ink-500">
                    {formatDuration(area.duration_minutes)}
                    {area.price_cents != null ? ` · ${formatCurrencyBRL(area.price_cents)}` : ''}
                  </span>
                </label>
              )
            })}
          </div>
        </div>
      ))}
    </div>
  )
}
