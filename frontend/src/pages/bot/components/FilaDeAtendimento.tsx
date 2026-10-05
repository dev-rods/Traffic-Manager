import { useState } from 'react'
import { Badge } from '@/components/ui/Badge'
import { Button } from '@/components/ui/Button'
import { EmptyState } from '@/components/ui/EmptyState'
import { ErrorState } from '@/components/ui/ErrorState'
import { SkeletonTable } from '@/components/ui/Skeleton'
import { formatPhone } from '@/utils/formatPhone'
import { esperaDemais, esperaDesde } from '@/utils/esperaDesde'
import type { ActiveConversation } from '@/types'

type Aba = 'especialista' | 'pausadas'

interface FilaDeAtendimentoProps {
  conversations: ActiveConversation[]
  isLoading: boolean
  isError: boolean
  onRetry: () => void
  onSelect: (phone: string, nome: string) => void
  onResume: (phone: string) => void
  resumeLoading: boolean
}

/**
 * As conversas que precisam de uma pessoa, em duas abas.
 *
 * Antes havia uma lista só, "Conversas pausadas", que misturava duas coisas
 * diferentes: a paciente esperando resposta de uma especialista e a conversa que
 * a atendente já assumiu pelo celular. A primeira é trabalho a fazer; a segunda
 * é trabalho acontecendo - e juntas numa lista a urgente ficava escondida entre
 * as outras.
 *
 * A aba "Aguardando especialista" ordena pela espera MAIS ANTIGA primeiro. É o
 * contrário do resto do painel, que mostra o mais recente no topo, e é de
 * propósito: aqui o topo da lista tem que ser quem está esperando há mais tempo.
 */
export function FilaDeAtendimento({
  conversations,
  isLoading,
  isError,
  onRetry,
  onSelect,
  onResume,
  resumeLoading,
}: FilaDeAtendimentoProps) {
  const [aba, setAba] = useState<Aba>('especialista')

  // Aguardando especialista: o bot pediu ajuda e ninguém assumiu. Quem já tem
  // atendente fica de fora - aquela conversa não está esperando ninguém.
  const aguardando = conversations
    .filter((c) => c.state === 'HUMAN_HANDOFF')
    .sort((a, b) => (a.handoff_requested_at ?? 0) - (b.handoff_requested_at ?? 0))

  const pausadas = conversations.filter((c) => c.bot_paused && c.state !== 'HUMAN_HANDOFF')

  const lista = aba === 'especialista' ? aguardando : pausadas

  return (
    <section>
      <div className="flex items-center gap-1 mb-3">
        <AbaBotao
          ativa={aba === 'especialista'}
          onClick={() => setAba('especialista')}
          quantidade={aguardando.length}
          urgente={aguardando.some((c) => esperaDemais(c.handoff_requested_at))}
        >
          Aguardando especialista
        </AbaBotao>
        <AbaBotao
          ativa={aba === 'pausadas'}
          onClick={() => setAba('pausadas')}
          quantidade={pausadas.length}
        >
          Bot pausado
        </AbaBotao>
      </div>

      {isLoading ? (
        <div className="rounded-lg border border-gray-200 p-4">
          <SkeletonTable rows={3} />
        </div>
      ) : isError ? (
        /*
          O erro vem ANTES do vazio, e a ordem é a regra inteira: lista vazia
          por falha de rede não é "ninguém esperando". Dizer isso à recepção a
          faria parar de olhar justamente quando há alguém na fila.
        */
        <div className="rounded-lg border border-gray-200">
          <ErrorState
            message="Não conseguimos carregar a fila de atendimento. Pode haver alguém esperando."
            onRetry={onRetry}
          />
        </div>
      ) : lista.length === 0 ? (
        <div className="rounded-lg border border-gray-200">
          {aba === 'especialista' ? (
            <EmptyState
              title="Ninguém esperando"
              description="Quando o bot não souber responder algo - ou quando perguntarem sobre outro procedimento - a conversa aparece aqui."
            />
          ) : (
            <EmptyState
              title="Nenhuma conversa pausada"
              description="Conversas em que alguém da clínica assumiu o atendimento aparecem aqui, com o botão para devolver ao bot."
            />
          )}
        </div>
      ) : (
        <ul className="rounded-lg border border-gray-200 divide-y divide-gray-100">
          {lista.map((conv) => (
            <LinhaDaFila
              key={conv.phone}
              conversa={conv}
              mostraEspera={aba === 'especialista'}
              onSelect={onSelect}
              onResume={onResume}
              resumeLoading={resumeLoading}
            />
          ))}
        </ul>
      )}
    </section>
  )
}

function AbaBotao({
  ativa,
  onClick,
  quantidade,
  urgente = false,
  children,
}: {
  ativa: boolean
  onClick: () => void
  quantidade: number
  urgente?: boolean
  children: React.ReactNode
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={ativa}
      className={[
        'flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium cursor-pointer',
        'transition-colors duration-150',
        ativa ? 'bg-brand-500 text-white' : 'text-gray-500 hover:bg-gray-100',
      ].join(' ')}
    >
      {children}
      {quantidade > 0 && (
        <span
          className={[
            'inline-flex min-w-5 justify-center rounded-md px-1.5 py-0.5 text-[11px] font-semibold',
            ativa
              ? 'bg-white/20 text-white'
              : urgente
                ? 'bg-red-50 text-red-700'
                : 'bg-gray-100 text-gray-600',
          ].join(' ')}
        >
          {quantidade}
        </span>
      )}
    </button>
  )
}

function LinhaDaFila({
  conversa,
  mostraEspera,
  onSelect,
  onResume,
  resumeLoading,
}: {
  conversa: ActiveConversation
  mostraEspera: boolean
  onSelect: (phone: string, nome: string) => void
  onResume: (phone: string) => void
  resumeLoading: boolean
}) {
  const nome = conversa.name || ''
  const atrasada = mostraEspera && esperaDemais(conversa.handoff_requested_at)

  return (
    <li className="flex items-center justify-between gap-4 px-4 py-3">
      <div className="min-w-0">
        <p className="text-sm font-medium text-gray-800 truncate">
          {nome || formatPhone(conversa.phone)}
        </p>
        <p className="text-xs text-gray-500 mt-0.5 truncate">
          {nome && <span className="text-gray-400">{formatPhone(conversa.phone)} · </span>}
          {/*
            O motivo vem traduzido do servidor. Sem motivo gravado - conversas
            entregues antes desta mudança - a linha diz o que sabe, em vez de
            mostrar um rótulo vazio que pareceria um defeito da tela.
          */}
          {mostraEspera
            ? conversa.handoff_reason_label || 'Motivo não registrado'
            : conversa.pause_reason === 'attendant'
              ? 'Atendente assumiu'
              : conversa.pause_reason === 'clinic_paused'
                ? 'Bot desligado na clínica'
                : 'Fora da política de resposta'}
        </p>
      </div>

      <div className="flex items-center gap-3 flex-shrink-0">
        {mostraEspera && conversa.handoff_requested_at && (
          // Não é só cor: o texto diz o tempo, e quem não distingue vermelho de
          // cinza lê "3h" do mesmo jeito.
          <Badge variant={atrasada ? 'danger' : 'neutral'}>
            espera {esperaDesde(conversa.handoff_requested_at)}
          </Badge>
        )}
        {/*
          A acao primaria muda com a aba, porque o trabalho e outro. Na fila da
          especialista, quem abre a tela vai RESPONDER - "Retomar bot" ali e
          desistir, e nao pode ser o botao mais chamativo da linha. Na aba de
          pausadas e o contrario: devolver ao bot e o que se faz.
        */}
        <Button
          variant={mostraEspera ? 'primary' : 'ghost'}
          size="sm"
          onClick={() => onSelect(conversa.phone, nome)}
        >
          Ver conversa
        </Button>
        <Button
          variant={mostraEspera ? 'secondary' : 'primary'}
          size="sm"
          onClick={() => onResume(conversa.phone)}
          loading={resumeLoading}
        >
          Retomar bot
        </Button>
      </div>
    </li>
  )
}
