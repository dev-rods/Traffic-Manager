import { Badge } from '@/components/ui/Badge'

/**
 * O bot está silenciado para este contato (PRD 039).
 *
 * Aparece SÓ para quem está silenciado (decisão §4.2): marcar quem não está
 * encheria a lista de rótulos e tornaria o selo invisível justo onde importa.
 * Quem silencia e reativa é a tela do bot; aqui o selo só avisa.
 */
export function SeloSilenciado({ silenciado }: { silenciado?: boolean }) {
  if (!silenciado) return null

  return (
    <Badge variant="neutral" className="bg-purple-50 text-purple-700 ring-purple-600/20">
      Bot silenciado
    </Badge>
  )
}
