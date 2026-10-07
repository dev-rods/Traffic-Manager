import { createContext } from 'react'

export interface ClinicIdContextValue {
  clinicId: string
  // '/:clinicId' no domínio padrão (*.vercel.app) — '' no domínio próprio da
  // clínica, onde a raiz já é a clínica e repetir o id na URL não faz sentido.
  basePath: string
}

export const ClinicIdContext = createContext<ClinicIdContextValue | null>(null)
