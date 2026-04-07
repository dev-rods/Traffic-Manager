interface PaginationProps {
  page: number
  perPage: number
  total: number
  onPageChange: (page: number) => void
  onPerPageChange: (perPage: number) => void
  perPageOptions?: number[]
}

export function Pagination({
  page,
  perPage,
  total,
  onPageChange,
  onPerPageChange,
  perPageOptions = [10, 25, 50, 100],
}: PaginationProps) {
  const totalPages = Math.max(1, Math.ceil(total / perPage))
  const from = total === 0 ? 0 : (page - 1) * perPage + 1
  const to = Math.min(page * perPage, total)

  return (
    <div className="flex items-center justify-between px-1 py-3">
      <div className="flex items-center gap-3">
        <label className="text-xs text-gray-500">Por página</label>
        <select
          value={perPage}
          onChange={(e) => {
            onPerPageChange(Number(e.target.value))
            onPageChange(1)
          }}
          className="border border-gray-200 rounded-lg px-2 py-1.5 text-xs text-gray-700 bg-white focus:outline-none focus:ring-2 focus:ring-brand-500 cursor-pointer"
        >
          {perPageOptions.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
        <span className="text-xs text-gray-400">
          {from}–{to} de {total}
        </span>
      </div>

      <div className="flex items-center gap-1">
        <button
          onClick={() => onPageChange(1)}
          disabled={page <= 1}
          className="px-2 py-1.5 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title="Primeira página"
        >
          ««
        </button>
        <button
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          ‹ Anterior
        </button>
        <span className="px-3 py-1.5 text-xs font-semibold text-gray-700">
          {page} / {totalPages}
        </span>
        <button
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          Próxima ›
        </button>
        <button
          onClick={() => onPageChange(totalPages)}
          disabled={page >= totalPages}
          className="px-2 py-1.5 rounded-lg text-xs font-medium text-gray-600 hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
          title="Última página"
        >
          »»
        </button>
      </div>
    </div>
  )
}
