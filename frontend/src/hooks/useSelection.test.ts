import { describe, it, expect } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useSelection } from './useSelection'

interface Row {
  id: string
  name: string
}

const page1: Row[] = [
  { id: '1', name: 'Ana' },
  { id: '2', name: 'Bruno' },
]
const page2: Row[] = [
  { id: '3', name: 'Carla' },
  { id: '4', name: 'Diego' },
]

function names(items: Row[]) {
  return items.map((i) => i.name).sort()
}

describe('useSelection', () => {
  it('starts empty', () => {
    const { result } = renderHook(() => useSelection(page1))
    expect(result.current.selectedItems).toEqual([])
    expect(result.current.pageFullySelected).toBe(false)
  })

  it('toggles a single item on and off', () => {
    const { result } = renderHook(() => useSelection(page1))

    act(() => result.current.toggle(page1[0]))
    expect(names(result.current.selectedItems)).toEqual(['Ana'])

    act(() => result.current.toggle(page1[0]))
    expect(result.current.selectedItems).toEqual([])
  })

  it('selects and clears the whole current page', () => {
    const { result } = renderHook(() => useSelection(page1))

    act(() => result.current.togglePage())
    expect(names(result.current.selectedItems)).toEqual(['Ana', 'Bruno'])
    expect(result.current.pageFullySelected).toBe(true)

    act(() => result.current.togglePage())
    expect(result.current.selectedItems).toEqual([])
  })

  // The regression: selecting page 1 then paginating used to drop Ana and Bruno from the
  // batch while the counter still claimed 4 selected, so they never got the message.
  it('keeps selections made on a previous page after paginating', () => {
    const { result, rerender } = renderHook(({ items }) => useSelection(items), {
      initialProps: { items: page1 },
    })

    act(() => result.current.togglePage())
    rerender({ items: page2 })

    expect(names(result.current.selectedItems)).toEqual(['Ana', 'Bruno'])
    expect(result.current.pageFullySelected).toBe(false)

    act(() => result.current.togglePage())
    expect(names(result.current.selectedItems)).toEqual(['Ana', 'Bruno', 'Carla', 'Diego'])
    expect(result.current.selectedIds).toEqual(new Set(['1', '2', '3', '4']))
  })

  it('clearing the current page leaves other pages selected', () => {
    const { result, rerender } = renderHook(({ items }) => useSelection(items), {
      initialProps: { items: page1 },
    })

    act(() => result.current.togglePage())
    rerender({ items: page2 })
    act(() => result.current.togglePage())
    act(() => result.current.togglePage())

    expect(names(result.current.selectedItems)).toEqual(['Ana', 'Bruno'])
  })

  it('clear() drops everything across pages', () => {
    const { result, rerender } = renderHook(({ items }) => useSelection(items), {
      initialProps: { items: page1 },
    })

    act(() => result.current.togglePage())
    rerender({ items: page2 })
    act(() => result.current.togglePage())
    act(() => result.current.clear())

    expect(result.current.selectedItems).toEqual([])
    expect(result.current.selectedIds.size).toBe(0)
  })

  it('pageFullySelected is false for an empty page', () => {
    const { result } = renderHook(() => useSelection<Row>([]))
    expect(result.current.pageFullySelected).toBe(false)
    act(() => result.current.togglePage())
    expect(result.current.selectedItems).toEqual([])
  })
})
