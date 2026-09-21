import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '@/hooks/useAuth'
import { podeVer, rotaInicial } from '@/lib/permissoes'

/**
 * Impede que uma rota fechada abra por URL digitada.
 *
 * Esconder o item no menu resolve o caminho normal; isto resolve o outro, que
 * é alguém colar `/relatorios` na barra de endereço. Nenhum dos dois é
 * segurança - a tela abriria vazia de qualquer forma, porque o servidor
 * responde 403 - mas uma tela de erro sem explicação faz a pessoa achar que o
 * sistema quebrou.
 */
export function RotaPermitida() {
  const { papel, permissoes } = useAuth()
  const { pathname } = useLocation()

  if (!podeVer({ papel, permissoes }, pathname)) {
    return <Navigate to={rotaInicial(papel)} replace />
  }

  return <Outlet />
}
