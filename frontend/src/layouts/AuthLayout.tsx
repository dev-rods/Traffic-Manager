import type { ReactNode } from 'react'

interface Props {
  children: ReactNode
}

export default function AuthLayout({ children }: Props) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      {children}
    </div>
  )
}
