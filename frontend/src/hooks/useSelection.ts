import { useCallback, useMemo, useState } from 'react'

interface Identifiable {
  id: string
}

export interface Selection<T> {
  /** Ids of everything selected, across every page visited */
  selectedIds: Set<string>
  /** The selected items themselves — safe to act on even after paginating away */
  selectedItems: T[]
  /** True when every item on the current page is selected */
  pageFullySelected: boolean
  toggle: (item: T) => void
  /** Selects the whole current page, or clears it when already fully selected */
  togglePage: () => void
  clear: () => void
}

/**
 * Selection that survives pagination.
 *
 * Holds the items, not just their ids: deriving the selection by filtering the current
 * page would silently drop everything selected on other pages, so a bulk action would
 * only hit the page that happened to be open while the counter showed the full total.
 */
export function useSelection<T extends Identifiable>(pageItems: T[]): Selection<T> {
  const [selected, setSelected] = useState<Map<string, T>>(new Map())

  const selectedIds = useMemo(() => new Set(selected.keys()), [selected])
  const selectedItems = useMemo(() => [...selected.values()], [selected])

  const pageFullySelected = useMemo(
    () => pageItems.length > 0 && pageItems.every((item) => selected.has(item.id)),
    [pageItems, selected],
  )

  const toggle = useCallback((item: T) => {
    setSelected((prev) => {
      const next = new Map(prev)
      if (next.has(item.id)) next.delete(item.id)
      else next.set(item.id, item)
      return next
    })
  }, [])

  // Only touches the current page — selections made on other pages stay put
  const togglePage = useCallback(() => {
    setSelected((prev) => {
      const next = new Map(prev)
      const deselecting = pageItems.length > 0 && pageItems.every((item) => next.has(item.id))
      for (const item of pageItems) {
        if (deselecting) next.delete(item.id)
        else next.set(item.id, item)
      }
      return next
    })
  }, [pageItems])

  const clear = useCallback(() => setSelected(new Map()), [])

  return { selectedIds, selectedItems, pageFullySelected, toggle, togglePage, clear }
}
