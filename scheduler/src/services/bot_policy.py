"""Decide se o bot responde automaticamente uma conversa.

Função pura, sem I/O: recebe a clínica, a sessão e o telefone, devolve sim ou não.
Fica fora do handler porque é a regra que muda a cada fase do rollout, e precisa
ser testável sem subir webhook.
"""
from typing import Dict, Optional

from src.services import atendimento

POLICY_ALL = "ALL"
POLICY_PILOT = "PILOT"
POLICY_LEADS_ONLY = "LEADS_ONLY"
POLICY_OFF = "OFF"

# Por que a conversa está pausada. O valor é informativo; o que importa é o
# campo existir - qualquer valor pausa.
PAUSA_ATENDENTE = "ATENDENTE"          # alguém da clínica respondeu
PAUSA_CONTATO_MANUAL = "CONTATO_MANUAL"  # marcaram "Já iniciada" no painel
PAUSA_CHAT_ANTERIOR = "CHAT_ANTERIOR"    # já havia conversa antes de nós
PAUSA_HANDOFF = "HANDOFF"                # o próprio bot pediu ajuda humana
PAUSA_INSTABILIDADE = "INSTABILIDADE"    # o sistema falhou; ninguém decidiu nada

CAMPO_DE_PAUSA = "bot_pausado_por"

# Quanto tempo uma conversa entregue a uma pessoa fica com ela. Decisão do
# André em 06/09/2026. A fonte e `atendimento.TTL_HUMANO`; isto e o nome antigo.
TTL_DO_ATENDIMENTO = atendimento.TTL_HUMANO

def esta_pausado(session: Optional[Dict]) -> bool:
    """A conversa foi entregue a uma pessoa e o bot não fala.

    NOME ANTIGO de `atendimento.esta_com_pessoa`. Nenhum chamador novo;
    sai na fase 3 do PRD 020.

    Duas naturezas de pausa, e elas vencem diferente porque dizem coisas
    diferentes:

    ATENDENTE e HANDOFF descrevem um ATENDIMENTO EM CURSO. Alguém está na
    conversa agora. Isso é verdade por um tempo e depois deixa de ser - por
    decisão do André em 06/09/2026, 24h. Sem prazo, uma conversa atendida uma
    vez ficaria morta para sempre e ninguém lembraria de reabrir.

    CONTATO_MANUAL e CHAT_ANTERIOR descrevem QUEM COMEÇOU a conversa. Isso não
    para de ser verdade amanhã. Se vencessem, o bot entraria no dia seguinte
    numa conversa que uma pessoa conduz - exatamente o dano que o botão "Já
    iniciada" existe para impedir.

    Em ambos os casos o "Retomar bot" no painel libera na hora.
    """
    return atendimento.esta_com_pessoa(session)


def should_bot_reply(clinic: Optional[Dict], session: Optional[Dict], phone: str) -> bool:
    """O bot deve responder automaticamente esta conversa?

    NOME ANTIGO de `atendimento.pode_responder`, que e a pergunta REATIVA.
    Quem vai falar primeiro (fila, campanha, retomada, lembrete) usa
    `atendimento.pode_iniciar`. Nenhum chamador novo; sai na fase 3.

    Desde a fase 2 inclui `clinic.bot_paused`, que os chamadores conferiam
    por fora - a regra inteira num lugar so.
    """
    return atendimento.pode_responder(clinic, session, phone)


# O MOTIVO da entrega, em vocabulário fechado. `bot_pausado_por` diz QUEM calou
# o bot (HANDOFF, ATENDENTE, INSTABILIDADE); isto diz POR QUÊ, e é o que o
# painel mostra para a recepção saber o que a conversa precisa antes de abri-la.
#
# O `reason` da tool request_human_handoff chegava e era descartado: o executor
# só devolvia o valor e ninguém gravava. A conversa ia para a fila sem dizer o
# que a pessoa queria, e a atendente descobria lendo a thread inteira.
CAMPO_DO_MOTIVO = "handoff_reason"

MOTIVO_FORA_DO_ESCOPO = "procedimento_fora_do_escopo"
MOTIVO_INSTABILIDADE = "instabilidade"
MOTIVO_PEDIDO = "pedido_da_paciente"
MOTIVO_SEM_RESPOSTA = "faq_sem_resposta"
MOTIVO_AREAS_EM_LACO = "areas_em_laco"
MOTIVO_AGENDA_SEM_RESPALDO = "agenda_sem_respaldo"
MOTIVO_AFIRMOU_MENOR = "afirmou_menor_sem_respaldo"
MOTIVO_INSISTIU_CADASTRO = "insistiu_em_cadastro"
MOTIVO_INCOMPREENSAO = "incompreensao"
MOTIVO_ESGOTOU = "esgotou_as_consultas"

# Como a recepção lê cada motivo. Fica aqui, e não na tela, porque é a mesma
# régua de [status_da_conversa]: regra que mora em dois lugares diverge calada.
MOTIVOS_LEGIVEIS = {
    MOTIVO_FORA_DO_ESCOPO: "Perguntou sobre outro procedimento",
    MOTIVO_INSTABILIDADE: "Falha no sistema - ninguém respondeu",
    MOTIVO_PEDIDO: "Pediu para falar com uma pessoa",
    MOTIVO_SEM_RESPOSTA: "Dúvida que não está no FAQ",
    MOTIVO_AREAS_EM_LACO: "As áreas não fecharam",
    MOTIVO_AGENDA_SEM_RESPALDO: "O bot errou a agenda",
    MOTIVO_AFIRMOU_MENOR: "O bot errou sobre a idade",
    MOTIVO_INSISTIU_CADASTRO: "O bot insistiu em cadastro",
    MOTIVO_INCOMPREENSAO: "O bot não entendeu",
    MOTIVO_ESGOTOU: "O bot não conseguiu responder (esgotou as consultas)",
}

# Os que o MODELO pode escolher. Os outros são escritos pelo código quando uma
# trava dispara - instabilidade, agenda sem respaldo, áreas em laço - e o modelo
# não tem como saber que disparou. Oferecê-los na tool seria convidá-lo a
# rotular a conversa de um jeito que a fila do painel leria como falha nossa.
MOTIVOS_DO_MODELO = (
    MOTIVO_FORA_DO_ESCOPO,
    MOTIVO_SEM_RESPOSTA,
    MOTIVO_PEDIDO,
    MOTIVO_INCOMPREENSAO,
)


def motivo_do_handoff_legivel(session: Optional[Dict]) -> str:
    """O motivo em português, ou vazio quando a conversa não foi entregue."""
    motivo = (session or {}).get(CAMPO_DO_MOTIVO)
    if not motivo:
        return ""
    return MOTIVOS_LEGIVEIS.get(motivo, str(motivo))


def entrega_a_humano(
    session: Optional[Dict],
    motivo: str,
    pausa: str = PAUSA_HANDOFF,
    agora: Optional[int] = None,
) -> Dict:
    """Cala o bot e põe a conversa na fila de quem atende.

    Este bloco de quatro campos estava copiado em sete lugares - seis no
    [conversation_agent] e um aqui - e os sete tinham de concordar sobre o que
    significa "entregue". Divergência aí é silenciosa: uma cópia que esquecesse
    `attendant_active_until` deixaria o bot voltar a responder por cima da
    atendente, e ninguém veria até a paciente receber duas respostas.

    O `motivo` é obrigatório porque a fila do painel existe para ser triada: uma
    lista de telefones sem motivo obriga a abrir cada conversa para descobrir o
    que ela quer.
    """
    return atendimento.entrega_a_humano(session, por=pausa, motivo=motivo, agora=agora)


def entrega_por_instabilidade(session: Optional[Dict], agora: Optional[int] = None) -> Dict:
    """Cala o bot e passa a conversa para uma pessoa, porque o sistema falhou.

    Em 14 e 15/09/2026, com a conta da Anthropic sem saldo, o bot respondeu
    "Desculpe, estou com dificuldades no momento. Tente novamente em instantes."
    a quem escreveu. É a pior resposta possível: não ajuda a paciente, expõe que
    o problema é nosso, e ainda a convida a tentar de novo - contra um sistema
    que vai falhar igual. Numa das conversas, a atendente respondeu à mão duas
    horas depois; nas outras, ninguém respondeu.

    Regra do André, 15/09/2026: mensagem de instabilidade NUNCA chega ao
    cliente. O bot cala, e a conversa vira uma pessoa esperando resposta - que
    é exatamente o que a clínica já sabe tratar.

    Calar sem pausar seria pior do que a mensagem ruim: a paciente ficaria sem
    resposta e ninguém saberia. A pausa é o que põe a conversa na frente de um
    atendente, com o mesmo prazo e o mesmo "Retomar bot" de qualquer
    atendimento humano.

    O motivo é próprio, e não HANDOFF, porque as duas coisas não são a mesma:
    HANDOFF é o bot decidindo que precisa de ajuda, INSTABILIDADE é ele não ter
    conseguido decidir nada. Só separadas dá para medir quanto de transferência
    é falha nossa.
    """
    return entrega_a_humano(
        session, MOTIVO_INSTABILIDADE, pausa=PAUSA_INSTABILIDADE, agora=agora
    )
