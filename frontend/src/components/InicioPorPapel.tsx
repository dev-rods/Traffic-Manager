import { Navigate } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { rotaInicial } from '@/lib/permissoes'

/**
 * Para onde `/` leva.
 *
 * Era sempre `/dashboard`. O funcionário não tem dashboard - ali mora o
 * faturamento - então mandá-lo para lá o jogaria numa tela que o servidor
 * recusa, logo no primeiro clique depois do login.
 */
export function InicioPorPapel() {
  const { papel } = useAuth()

  return <Navigate to={rotaInicial(papel)} replace />
}
