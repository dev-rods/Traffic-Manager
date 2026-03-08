interface PatientSearchProps {
  value: string
  onChange: (value: string) => void
}

export function PatientSearch({ value, onChange }: PatientSearchProps) {
  return (
    <div className="relative">
      <svg
        className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400"
        fill="none"
        viewBox="0 0 24 24"
        strokeWidth={2}
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
        />
      </svg>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Buscar por nome ou telefone..."
        className="w-full border border-gray-200 rounded-lg pl-10 pr-4 py-2.5 text-sm bg-white transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500"
      />
    </div>
  )
}
