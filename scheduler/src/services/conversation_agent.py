import json
import os
import time
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

import boto3

from src.services.anthropic_service import AnthropicService, AnthropicError
from src.services.anthropic_service import DEFAULT_MODEL as MODELO_DO_AGENTE
from src.services.consumo import do_retorno as consumo_do_retorno
from src.services.consumo import registra_total as registra_consumo_total
from src.services.consumo import soma as soma_consumo
from src.services.ai_tools import ToolExecutor, get_tool_definitions
from src.services.bot_policy import entrega_por_instabilidade
from src.services.campanha import datas_da_campanha, esta_viva as campanha_viva
from src.services.fora_do_escopo import INSTRUCAO_DO_PROMPT as INSTRUCAO_FORA_DO_ESCOPO
from src.services.fora_do_escopo import TEXTO as TEXTO_FORA_DO_ESCOPO
from src.services.fora_do_escopo import detecta as procedimento_fora_do_escopo
from src.services.prompt_da_campanha import adapta as adapta_para_campanha
from src.services.prompt_da_campanha import pede_cadastro
from src.services import desambiguacao
from src.services import estado_comercial
from src.services import nivel_de_risco
from src.services import policy_do_faq
from src.services import skills
from src.services.busca_no_faq import busca as busca_no_faq
from src.services.identificacao_de_paciente import identificar as identificar_paciente
from src.services.identificacao_de_paciente import sem_passo_de_cadastro
from src.services.narracao import narra_a_pessoa
from src.services.valor_para_recorrente import (
    anuncia_valor,
    e_recorrente,
    pediu_valor,
    sem_valor_no_roteiro,
)
from src.services.calendario import bloco_de_contexto
from src.services.menor_de_idade import TEXTO as AVISO_DE_MENOR
from src.services.menor_de_idade import afirmacao_sem_respaldo as afirmacao_de_menor_sem_respaldo
from src.services.menor_de_idade import precisa_avisar as precisa_avisar_menor
from src.services.orientacoes_pos_sessao import texto as orientacoes_da_clinica
from src.services.preco_minimo import preco_minimo_por_area
from src.services.proveniencia import fatos_de_agenda, fatos_sem_origem
from src.services.recusa_repetida import CAMPO as CAMPO_DE_RECUSAS
from src.services.recusa_repetida import e_laco as recusa_em_laco
from src.services.roteador import exige_consulta, intencoes, tools_obrigatorias
from src.services.template_service import TemplateService

logger = logging.getLogger(__name__)

# Rodadas de ferramenta por mensagem. O caminho feliz de um agendamento ja
# gasta cinco (list_services, list_areas, calculate_discount,
# check_availability, get_time_slots) ANTES de ter o que responder; com 5 o
# bot estourava no meio e mandava como resposta o aviso que escreveu junto da
# ultima ferramenta ("vou ver os horarios") - e nada depois. Visto em prod em
# 08/10/2026 em duas conversas. Depois destas rodadas ha UMA chamada de
# fechamento, sem ferramentas, para responder com o que ja foi apurado.
MAX_AGENT_ITERATIONS = 10
MAX_HISTORY_PAIRS = 20
# O prazo vive em bot_policy: era a mesma regra escrita em cinco lugares,
# e regra duplicada diverge em silencio quando alguem muda so um deles.
from src.services.bot_policy import (
    MOTIVO_AFIRMOU_MENOR,
    MOTIVO_AGENDA_SEM_RESPALDO,
    MOTIVO_ESGOTOU,
    MOTIVO_SEM_RESPOSTA,
    MOTIVO_INCOMPREENSAO,
    TEXTO_DE_RISCO,
    MOTIVO_AREAS_EM_LACO,
    MOTIVO_FORA_DO_ESCOPO,
    MOTIVO_INSISTIU_CADASTRO,
    MOTIVO_PEDIDO,
    entrega_a_humano,
)

# Quantos resultados de tool a sessão carrega adiante para respaldar repetição
# de fato já consultado. Alto o bastante para uma negociação de data (a pessoa
# volta ao mesmo horário por vários turnos), baixo o bastante para não estourar
# o item do DynamoDB.
RESPALDO_GUARDADO = 16


# Mensagens sintéticas que fazem o agente falar sem ninguém ter escrito. Ficam
# aqui, e não no módulo de cada fluxo, porque quem precisa reconhecê-las é o
# agente - importar de volta criaria ciclo.
GATILHOS_SINTETICOS = ("__INICIAR_CONVERSA__", "__RETOMAR_CONVERSA__")

# Tools que mudam o mundo. Depois de uma delas, o agendamento existe no banco e
# a pessoa PRECISA saber - trocar a mensagem por "vou confirmar com uma
# especialista" a deixaria com uma sessão marcada que ela não sabe que tem.
TOOLS_COM_EFEITO = frozenset({
    "book_appointment",
    "reschedule_appointment",
    "cancel_appointment",
})

# As que deixam a pessoa com uma sessão marcada - e portanto com preparo a
# fazer. Cancelar não entra: quem cancelou não precisa raspar nada.
TOOLS_QUE_MARCAM_SESSAO = frozenset({
    "book_appointment",
    "reschedule_appointment",
})


def eh_gatilho_sintetico(conteudo):
    """A mensagem é um gatilho da clínica, e não fala de alguém?"""
    return (conteudo or "").strip() in GATILHOS_SINTETICOS


def limpar_gatilhos(history):
    """Tira os gatilhos do histórico antes de salvar.

    Gatilho não é fala de ninguém: persistido, reaparece como turno da pessoa na
    conversa seguinte. Removê-lo deixaria dois turnos de assistant colados, que a
    API da Anthropic recusa, então os vizinhos são unidos.
    """
    limpo = []
    for turno in history or []:
        conteudo = turno.get("content")
        if turno.get("role") == "user" and isinstance(conteudo, str) and eh_gatilho_sintetico(conteudo):
            continue
        if limpo and limpo[-1]["role"] == turno.get("role"):
            anterior, atual = limpo[-1].get("content"), conteudo
            if isinstance(anterior, str) and isinstance(atual, str):
                limpo[-1] = {"role": turno["role"], "content": anterior + chr(10) + atual}
            else:
                # Conteúdo em blocos (tool_use, thinking): concatena as listas.
                a = anterior if isinstance(anterior, list) else [{"type": "text", "text": str(anterior)}]
                b = atual if isinstance(atual, list) else [{"type": "text", "text": str(atual)}]
                limpo[-1] = {"role": turno["role"], "content": a + b}
            continue
        limpo.append(turno)
    return limpo


def foi_de_pessoa_da_clinica(event):
    """OUTBOUND digitado no celular, nao enviado pelo bot.

    O webhook marca `metadata.autor = HUMANO` desde a fase 3. Antes disso o
    sinal era a ausencia de providerMessageId num SENT (ver autoria_mensagem):
    o bot sempre guarda o id que o provider devolve.
    """
    if event.get("direction") != "OUTBOUND":
        return False
    meta = event.get("metadata") or {}
    if isinstance(meta, dict) and meta.get("autor") == "HUMANO":
        return True
    return event.get("status") == "SENT" and not event.get("providerMessageId")


def events_to_history(events):
    """Converte eventos de mensagem em turnos de conversa para o agente.

    Usado quando a sessão está sem `agent_history` mas o MessageEvents ainda tem a
    conversa (retenção de 90 dias). Só texto: blocos de tool_use não são
    reconstruídos, porque o resultado das ferramentas já está refletido no que foi
    dito. Turnos consecutivos do mesmo papel são unidos, porque a API da Anthropic
    exige alternância entre user e assistant.
    """
    history = []
    for event in events or []:
        content = (event.get("content") or "").strip()
        if not content:
            continue
        papel = "assistant" if event.get("direction") == "OUTBOUND" else "user"
        # Fala da ATENDENTE pelo celular nao e fala do bot. Virava turno
        # `assistant` e o bot "continuava" promessas que nao fez - desconto,
        # encaixe, excecao. Entra como turno do usuario, rotulada: o prompt
        # diz que e compromisso da clinica, nao dele. PRD 020 §3.4.
        if papel == "assistant" and foi_de_pessoa_da_clinica(event):
            papel = "user"
            content = f"[atendente da clínica]: {content}"
        if history and history[-1]["role"] == papel:
            history[-1]["content"] = f"{history[-1]['content']}\n{content}"
        else:
            history.append({"role": papel, "content": content})

    # A API rejeita histórico que começa com assistant.
    while history and history[0]["role"] == "assistant":
        history.pop(0)

    return history


class DecimalEncoder(json.JSONEncoder):
    """Handle Decimal types from DynamoDB."""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj == int(obj) else float(obj)
        return super().default(obj)


@dataclass
class OutgoingMessage:
    message_type: str  # text, buttons, list
    content: str
    buttons: Optional[List[Dict[str, str]]] = None
    sections: Optional[List[Dict]] = None
    button_text: Optional[str] = None


def _anexa_ao_turno_do_usuario(history, texto):
    """Anexa `texto` como fala do usuario sem criar dois turnos `user`
    seguidos (a API responde 400). Se o ultimo turno ja e do usuario em
    texto (um PARE anterior), concatena; se e lista (tool_results), vira um
    bloco de texto no fim da lista."""
    if history and history[-1].get("role") == "user":
        conteudo = history[-1].get("content")
        if isinstance(conteudo, str):
            history[-1]["content"] = conteudo + "\n\n" + texto
        elif isinstance(conteudo, list):
            history[-1]["content"] = list(conteudo) + [{"type": "text", "text": texto}]
        else:
            history[-1]["content"] = texto
        return
    history.append({"role": "user", "content": texto})


MARCADOR_DA_FALA = "═══ MENSAGEM DA PESSOA ═══"


def fala_da_pessoa(conteudo):
    """So o que a pessoa escreveu, sem os blocos que o agente poe no turno
    dela (CALENDARIO, QUEM E, DADOS CONSULTADOS). As travas que leem a
    conversa procuram o que foi DITO: "valor" no bloco QUEM E nao e a pessoa
    perguntando o valor, e uma area num dado consultado nao e a pessoa
    pedindo a area."""
    if isinstance(conteudo, str) and MARCADOR_DA_FALA in conteudo:
        return conteudo.split(MARCADOR_DA_FALA, 1)[1].lstrip("\n")
    return conteudo


def _turnos_para_trava(history):
    """A conversa achatada em {role, content} de texto.

    O `history` do agente mistura texto, tool_use e tool_result num mesmo turno.
    A trava de areas so quer o que foi DITO - resultado de tool nao conta:
    achar a area no historico da paciente nao e o mesmo que perguntar a ela.
    """
    turnos = []
    for turno in history or []:
        conteudo = turno.get("content")
        if isinstance(conteudo, str):
            texto = fala_da_pessoa(conteudo) if turno.get("role") == "user" else conteudo
        elif isinstance(conteudo, list):
            texto = " ".join(
                b.get("text", "") for b in conteudo
                if isinstance(b, dict) and b.get("type") == "text"
            )
        else:
            texto = ""
        if texto.strip():
            turnos.append({"role": turno.get("role"), "content": texto})
    return turnos


class ConversationAgent:
    """
    LLM-based conversation agent that replaces the state machine.

    Same interface as ConversationEngine: process_message(clinic_id, incoming) -> List[OutgoingMessage]
    """

    def __init__(self, db, template_service, availability_engine,
                 appointment_service, provider, message_tracker):
        self.db = db
        self.template_service = template_service
        self.provider = provider
        self.message_tracker = message_tracker
        self.anthropic = AnthropicService()
        self.tool_executor = ToolExecutor(db, availability_engine, appointment_service)

        dynamodb = boto3.resource("dynamodb")
        self.sessions_table = dynamodb.Table(os.environ["CONVERSATION_SESSIONS_TABLE"])

    def _agenda_sem_respaldo(self, texto, respaldo_das_tools):
        """Data ou horário afirmados que nenhuma tool desta execução devolveu.

        Nunca levanta: uma falha na conferência não pode derrubar a resposta,
        senão o guardrail vira o motivo de o bot calar.
        """
        try:
            return fatos_de_agenda(fatos_sem_origem(texto, respaldo_das_tools))
        except Exception as e:
            logger.error(f"[Proveniencia] Falha ao conferir resposta: {e}")
            return set()

    def process_message(self, clinic_id, incoming):
        """
        Process an incoming WhatsApp message and return outgoing messages.

        This is the main entry point, matching ConversationEngine's interface.
        """
        phone = incoming.phone
        start_time = time.time()

        # 1. Load session
        session = self._load_session(clinic_id, phone)

        # 2. A porta de atendimento e de quem chama (webhook, cron, painel):
        # `atendimento.pode_responder` / `pode_iniciar`. Aqui so se registra
        # quem pulou a porta, para o defeito nao ser mudo.
        from src.services import atendimento as _atendimento
        if _atendimento.esta_com_pessoa(session):
            logger.error(
                f"[ConversationAgent] {phone}: chamado com a conversa em "
                f"{_atendimento.estado(session)} - quem chamou pulou a porta. Calando."
            )
            return []

        # 2b. Quem e a pessoa. Uma consulta por mensagem, antes de tudo: o
        # prompt, as tools e a trava de cadastro leem daqui. Ver
        # identificacao_de_paciente.
        inicio_identificacao = time.time()
        paciente = self._identifica_paciente(clinic_id, phone)
        cadastrada = bool(paciente.get("cadastro_completo"))
        # 2c. Estado comercial, derivado do que a identificacao ja trouxe
        # (PRD 020 §3.1): nenhuma consulta a mais. Medido por mensagem
        # enquanto a fase 7 nao despacha por ele (PRD §9.4).
        estado = estado_comercial.do_paciente(paciente)
        # 2d. O FAQ da clinica, uma consulta por mensagem: monta o `enum` da
        # tool get_faq_answer e serve o executor. Os itens que o modelo
        # escolher neste turno vao para `faq_entregues`, e viram bolhas
        # proprias na saida (policy_do_faq).
        itens_do_faq = policy_do_faq.itens(getattr(self, "db", None), clinic_id)
        faq_entregues = []
        logger.info(
            f"[EstadoComercial] {phone}: {estado} | identificacao em "
            f"{int((time.time() - inicio_identificacao) * 1000)}ms"
        )
        # 2e. A skill (fase 7): escolhida pelo estado comercial, decide as
        # tools que o modelo enxerga e o bloco de conduta do prompt. Por
        # estado e nao por intencao: o prefixo cacheado nao pode mudar a cada
        # mensagem. Ver skills.
        skill = skills.despacha(estado)
        logger.info(f"[Skill] {phone}: {skill.nome}")

        # 3. Build system prompt
        system_prompt = self._build_system_prompt(clinic_id, phone, session)
        if not campanha_viva(session):
            system_prompt += skill.bloco
        if cadastrada:
            # RETIRADO, nao contradito: o roteiro com texto pronto vence
            # qualquer "nao peca" colado no fim. Ver prompt_da_campanha.
            system_prompt = sem_passo_de_cadastro(system_prompt, paciente.get("nome", ""))
        # Quem ja e paciente nao ouve o valor ao confirmar - so se perguntar.
        # A campanha ja tem a propria regra e o proprio roteiro; fora dela,
        # vale para qualquer recorrente. Ver valor_para_recorrente.
        recorrente = e_recorrente(paciente) and not campanha_viva(session)
        if recorrente:
            system_prompt = sem_valor_no_roteiro(system_prompt)

        # 4. Load conversation history and append user message
        # Sanitize loaded history: sessions saved by older code versions may
        # start with an orphan tool_result block (no preceding tool_use), which
        # the Anthropic API rejects with 400.
        gatilho = eh_gatilho_sintetico(incoming.content)
        # Tudo que as tools devolveram ao longo da conversa, não só nesta
        # rodada. Uma janela de uma rodada era curta demais para conversa real:
        # a pessoa negocia data por vários turnos ("pode dia 27?", "e sábado?",
        # "então fica 23 mesmo") e o bot repete as MESMAS datas consultadas. Da
        # segunda repetição em diante o fato consultado virava "sem respaldo" e
        # a resposta era bloqueada.
        #
        # Isso não reabre o bug de origem: aquele era o modelo repetindo a
        # própria FALA. Resultado de tool é fato consultado, e a pré-carga mais
        # o tool_choice obrigatório já forçam reconsulta quando a intenção é
        # factual - o respaldo aqui é rede, não fonte.
        respaldo_das_tools = list(session.get("respaldo_anterior") or [])
        history = self._truncate_history(session.get("agent_history", []))
        if gatilho or not history:
            # Sessão sem histórico não significa conversa nova: a pessoa pode já ter
            # escrito antes de o bot assumir, ou a sessão pode ter expirado. O
            # MessageEvents guarda 90 dias, então dá para retomar de onde parou em
            # vez de recomeçar por cima de uma conversa em andamento.
            #
            # Num gatilho a reconstrução é obrigatória, mesmo com histórico na
            # sessão: com o bot pausado o webhook grava no MessageEvents mas não
            # chama o agente, então o agent_history está velho justamente nas
            # mensagens que motivaram a retomada. Uma cliente perguntou duas vezes
            # com o bot pausado e recebeu "tudo certo por aqui" ao retomar.
            do_events = self._truncate_history(self.rebuild_history_from_events(clinic_id, phone))
            history = do_events or history
        user_content = incoming.content or ""
        if incoming.button_id:
            user_content = incoming.button_text or incoming.button_id
        # Retomada por vencimento (fase 3): o cron deixou na sessao o contexto
        # (ha quantas horas ela espera, o que perguntou). Entra no turno do
        # gatilho, nao no system, pelo mesmo motivo do calendario: e volatil.
        contexto_de_retomada = (session.get("atendimento") or {}).get("retomada_contexto")
        if gatilho and contexto_de_retomada:
            user_content = f"{contexto_de_retomada}\n═══ GATILHO ═══\n{user_content}"
        history.append({"role": "user", "content": user_content})

        # ── Procedimento que o bot não atende ───────────────────────────
        # Antes do agente de propósito: a pergunta sobre botox nem chega ao
        # modelo, então não há como ele compor resposta a partir de um item de
        # FAQ de laser que casou "sessão" ou "preço". Ver fora_do_escopo.
        if not gatilho:
            config = self._config_fora_do_escopo(clinic_id)
            citado = procedimento_fora_do_escopo(user_content, config)
            if citado:
                logger.info(
                    f"[ForaDoEscopo] {phone}: citou {citado} -> especialista, "
                    f"sem passar pelo modelo"
                )
                return self._sai_antes_do_modelo(
                    session, clinic_id, phone, history, MOTIVO_FORA_DO_ESCOPO, TEXTO_FORA_DO_ESCOPO)

            # ── Nível 3: risco vence confiança (PRD 020 §4.3) ─────────────
            # Reclamação, reembolso, problema depois da sessão, questão
            # médica, ameaça: pessoa, antes de o modelo ler. Só o grupo
            # médico tem colisão com o FAQ: se a clínica escreveu sobre o
            # assunto (contraindicações), vale o FAQ. Ver nivel_de_risco.
            risco = nivel_de_risco.detecta(user_content, config)
            if risco:
                motivo, consulta = risco
                coberto = bool(consulta and busca_no_faq(consulta, itens_do_faq))
                if coberto:
                    logger.info(
                        f"[Risco] {phone}: {motivo}, mas o FAQ cobre; segue para o modelo"
                    )
                else:
                    logger.info(
                        f"[Risco] {phone}: {motivo} -> pessoa, sem passar pelo modelo "
                        f"| {user_content[:80]!r}"
                    )
                    return self._sai_antes_do_modelo(
                        session, clinic_id, phone, history, motivo, TEXTO_DE_RISCO)

        # 5. Agent loop
        # ── Pré-carga determinística ────────────────────────────────────
        # O agente decide sozinho quando consultar, e em 02/09/2026 decidiu que
        # não precisava: respondeu sobre um agendamento pelo que ele mesmo
        # dissera dias antes, já cancelado. Aqui a decisão sai do modelo: se a
        # pergunta é sobre agenda, preço ou disponibilidade, a consulta acontece
        # antes de ele escrever, e o resultado entra como fonte única.
        dados_consultados = []
        intencoes_detectadas = set() if gatilho else intencoes(user_content)
        if not gatilho:
            for nome_tool in tools_obrigatorias(intencoes_detectadas):
                try:
                    resultado = self.tool_executor.execute(
                        nome_tool, {}, context={"clinic_id": clinic_id, "phone": phone,
                                 "paciente": paciente,
                                 "estado_comercial": estado,
                                 "faq": itens_do_faq,
                                 "faq_entregues": faq_entregues,
                                 "session": session,
                                 "turnos": _turnos_para_trava(history)},
                    )
                    dados_consultados.append((nome_tool, resultado))
                    respaldo_das_tools.append(resultado)
                except Exception as e:
                    logger.error(f"[PreCarga] {nome_tool} falhou para {phone}: {e}")

        # ── Calendário ──────────────────────────────────────────────────
        # O modelo não tem relógio, e nada aqui dizia a data. Em 04/09/2026 a
        # pessoa pediu "agendar para amanhã" e o bot respondeu que não conseguia
        # calcular amanhã - correto pelas regras dele, e inútil para ela.
        #
        # As datas entram no respaldo porque são fato apurado, igual a resultado
        # de tool: sem isso, dizer "amanhã (05/09) não temos vaga" seria data
        # sem origem e a resposta cairia no bloqueio.
        bloco_calendario, datas_do_calendario = ("", [])
        if not gatilho:
            bloco_calendario, datas_do_calendario = bloco_de_contexto(user_content)
            respaldo_das_tools.append({"calendario": datas_do_calendario})

        # As datas da campanha tambem sao respaldo. Elas vem da sessao, gravadas
        # no ato do disparo, e o bloco de campanha as poe no prompt - sao fato
        # tao legitimo quanto resultado de tool.
        #
        # Sem isto, em 11/09/2026 o bot compos a resposta CERTA ("as datas sao
        # 23, 24 e 29; dia 25 nao temos") e a proveniencia a bloqueou por
        # "agenda sem respaldo", caindo no fallback de transferir para uma
        # especialista. A guarda barrou justamente quem estava certo.
        datas_da_campanha_aberta = datas_da_campanha(session)
        if datas_da_campanha_aberta:
            respaldo_das_tools.append({"campanha": datas_da_campanha_aberta})

        # Quem e a pessoa, para esta mensagem. Vai no turno da pessoa pelo
        # mesmo motivo do calendario (o prefixo cacheado nao muda), e sai do
        # historico antes de gravar (ver estado_comercial.sem_bloco).
        bloco_quem_e = estado_comercial.bloco(paciente, estado)

        if dados_consultados or bloco_calendario or bloco_quem_e:
            if dados_consultados:
                nomes = ", ".join(n for n, _ in dados_consultados)
                logger.info(f"[PreCarga] {phone}: {nomes}")
            blocos = ("\n\n").join(
                f"[{nome}]\n{json.dumps(self._convert_decimals(res), ensure_ascii=False, default=str)[:1500]}"
                for nome, res in dados_consultados
            )
            cabecalho_calendario = (
                f"═══ CALENDÁRIO ═══\n{bloco_calendario}\n"
                "Estas datas são o calendário, não a agenda: dizem que dia é, "
                "não que há vaga. Vaga só vem de check_availability.\n\n"
            ) if bloco_calendario else ""
            # O bloco vai no TURNO DA PESSOA, não no system prompt.
            #
            # O conteúdo muda a cada mensagem (são os dados desta consulta). No
            # system ele ficava dentro do prefixo cacheado, e mudar um byte do
            # prefixo invalida tudo depois dele - o cache morria a cada mensagem
            # e pagávamos os ~17k chars de prompt inteiros de novo.
            #
            # Aqui embaixo o prefixo (tools + system) fica byte-idêntico durante
            # a conversa toda, e o dado volátil vive depois do breakpoint.
            cabecalho_dados = (
                "═══ DADOS CONSULTADOS AGORA ═══\n"
                "Consultei o banco antes de te passar esta conversa. O que está "
                "abaixo é o estado real neste momento e é a ÚNICA fonte válida "
                "sobre agenda, preço e disponibilidade. O que não estiver aqui, "
                "você não sabe - nem que tenha dito antes nesta conversa.\n\n"
                + blocos + "\n\n"
            ) if dados_consultados else ""
            history[-1] = {"role": "user", "content": (
                cabecalho_calendario
                + (bloco_quem_e + "\n\n" if bloco_quem_e else "")
                + cabecalho_dados
                + f"═══ MENSAGEM DA PESSOA ═══\n{user_content}"
            )}

        tools = skill.filtra(get_tool_definitions(format="anthropic", faq=itens_do_faq))
        pending_buttons = None
        handoff_requested = False
        # O MOTIVO que a tool recebeu. Era descartado, e a conversa chegava à
        # fila do painel sem dizer o que a pessoa queria. Ver bot_policy.
        motivo_do_handoff = MOTIVO_PEDIDO
        text_parts = []
        # Perguntou sobre agenda? Então a primeira jogada é consultar, não
        # escrever. Deixar a escolha com o modelo fez o bot listar nove horários
        # da manhã com tools=0, mesmo com o prompt mandando consultar - duas
        # vezes no mesmo dia. Ele escolhe QUAL tool; não escolhe se consulta.
        # Consultar é o padrão; não consultar é a exceção. O desenho anterior
        # forçava só quando o regex reconhecia o assunto, e a lista de assuntos
        # factuais não tem fim: "E horários à tarde?" não casava com nada e o
        # bot inventou dez horários. Agora a lista curta é a de conversa fiada.
        forcar_proxima = exige_consulta(user_content) and not gatilho
        ja_refez = False
        ja_refez_cadastro = False
        ja_refez_narracao = False
        ja_refez_valor = False
        em_campanha = campanha_viva(session)
        # O contador do quebra-laço atravessa turnos: cada pergunta da trava é
        # uma mensagem nova, e um contador de uma rodada só veria a primeira
        # recusa. Ver recusa_repetida.
        recusas_da_conversa = dict(session.get(CAMPO_DE_RECUSAS) or {})
        laco_de_recusa = False
        efeito_cometido = None
        esgotou = False
        esclarecimento_pedido = False
        esgotou_esclarecimento = False
        efeito_gravado = {}
        consumo_da_mensagem = {}
        chamadas_ao_modelo = 0

        try:
            for iteration in range(MAX_AGENT_ITERATIONS + 1):
                logger.info(f"[ConversationAgent] Iteration {iteration + 1} for {phone}")

                # Ultima volta: fechamento. Sem ferramentas, o modelo responde
                # com o que as consultas ja devolveram. Se ainda nao der, a
                # conversa vai para uma pessoa (abaixo, no `else` do laco).
                fechando = iteration == MAX_AGENT_ITERATIONS
                if fechando:
                    logger.warning(
                        f"[Esgotado] {phone}: {MAX_AGENT_ITERATIONS} rodadas de ferramenta; "
                        f"pedindo fechamento sem ferramentas"
                    )
                    _anexa_ao_turno_do_usuario(history, (
                        "PARE. Voce ja fez todas as consultas que podia nesta rodada. "
                        "Responda AGORA a pessoa, com o que as consultas devolveram "
                        "(horarios, valores, areas). Nao anuncie o que vai fazer. Se "
                        "faltar algo, diga que vai confirmar com a equipe e ja retorna."
                    ))
                    forcar_proxima = False

                # Consumido a cada volta: forçar sempre deixaria o modelo sem
                # como encerrar, já que toda resposta exigiria mais uma tool.
                forcar_tool = {"type": "any"} if forcar_proxima else None
                forcar_proxima = False
                if fechando:
                    forcar_tool = {"type": "none"}
                if forcar_tool:
                    logger.info(f"[ConversationAgent] Consulta obrigatória para {phone}")

                response = self.anthropic.create_message(
                    system=system_prompt,
                    messages=history,
                    tools=tools,
                    max_tokens=1024,
                    tool_choice=forcar_tool,
                )

                # O consumo desta chamada, somado ao da mensagem. Cada chamada
                # já se registra sozinha em anthropic_service; aqui monta-se o
                # total, que é o número que responde "quanto custou atender
                # esta pessoa". Ver consumo.py.
                consumo_da_mensagem = soma_consumo(
                    consumo_da_mensagem, consumo_do_retorno(response)
                )
                chamadas_ao_modelo += 1

                # Parse response content blocks
                content_blocks = response.get("content", [])
                current_text_parts = []
                tool_uses = []

                for block in content_blocks:
                    if block["type"] == "text":
                        current_text_parts.append(block["text"])
                    elif block["type"] == "tool_use":
                        tool_uses.append(block)

                # Texto escrito JUNTO de uma ferramenta e narracao de intencao
                # ("agora vamos ver os horarios"), nao resposta. Fica como
                # ultimo recurso para o caso de o fechamento vir vazio depois
                # de present_options; nunca e a resposta de um turno que
                # estourou (ver o `else` do laco).
                if current_text_parts:
                    text_parts = current_text_parts
                if fechando and tool_uses:
                    # Pediu-se sem ferramentas e veio ferramenta: nao executa.
                    # O historico fica valido (sem tool_use pendente) porque o
                    # bloco nao e anexado.
                    logger.error(f"[Esgotado] {phone}: o fechamento ainda pediu ferramenta; calando")
                    text_parts = []
                    tool_uses = []
                    esgotou = True
                    break

                stop_reason = response.get("stop_reason", "end_turn")

                if not tool_uses:
                    # Resposta final: confere antes de aceitar. Data e horário
                    # afirmados sem respaldo não viram mensagem - mas a primeira
                    # reação é mandar consultar, não desistir da conversa.
                    texto_provisorio = "\n".join(current_text_parts).strip()
                    inventado = self._agenda_sem_respaldo(texto_provisorio, respaldo_das_tools)

                    # Efeito já cometido não se refaz: mandar consultar de novo
                    # convida o modelo a chamar book_appointment outra vez.
                    # Pedir cadastro a quem ja e cadastrada e o erro mais
                    # visivel deste fluxo. Retirar o roteiro do prompt reduz a
                    # chance; esta trava e o que garante.
                    cadastro = (
                        pede_cadastro(texto_provisorio)
                        if (em_campanha or cadastrada) else []
                    )
                    if cadastro and not ja_refez_cadastro and not efeito_cometido:
                        ja_refez_cadastro = True
                        logger.warning(
                            f"[Cadastro] {phone} pediu cadastro ({cadastro}) a paciente "
                            f"ja cadastrada; refazendo"
                        )
                        history.append({"role": "assistant", "content": content_blocks})
                        history.append({"role": "user", "content": (
                            "PARE. Esta pessoa JA E PACIENTE CADASTRADA e voce acabou de "
                            "pedir dado de cadastro a ela. Nao peca nome, CPF, data de "
                            "nascimento nem e-mail: a clinica ja tem tudo isso, e o nome "
                            "dela esta no seu contexto. Reescreva a mensagem sem esse "
                            "pedido, seguindo de onde a conversa estava."
                        )})
                        text_parts = []
                        continue

                    # O modelo escreveu o raciocinio como resposta: "ela
                    # mencionou exatamente a Virilha Completa + anus" chegou a
                    # paciente em 06/10/2026. Uma vez em 3020 mensagens, mas
                    # uma vez na conversa de alguem. Mandar reescrever falando
                    # COM ela; se insistir, segue (nao e erro de fato, e de
                    # forma) e fica no log.
                    narrado = narra_a_pessoa(texto_provisorio)
                    if narrado and not ja_refez_narracao and not efeito_cometido:
                        ja_refez_narracao = True
                        logger.warning(
                            f"[Narracao] {phone} narrou a pessoa em terceira pessoa "
                            f"({narrado!r}); refazendo"
                        )
                        history.append({"role": "assistant", "content": content_blocks})
                        history.append({"role": "user", "content": (
                            "PARE. Voce escreveu sobre a pessoa em terceira pessoa "
                            f"({narrado!r}), como se raciocinasse em voz alta para "
                            "outra pessoa. Quem le e ela. Reescreva a mesma resposta "
                            "falando diretamente com ela, sem narrar o que ela disse "
                            "nem o que voce concluiu - so o que ela precisa saber ou "
                            "responder."
                        )})
                        text_parts = []
                        continue
                    elif narrado:
                        logger.error(
                            f"[Narracao] {phone} insistiu em narrar ({narrado!r}); "
                            f"resposta segue | {texto_provisorio[:160]!r}"
                        )

                    # Paciente recorrente nao ouve valor sem ter perguntado.
                    # Retirar do roteiro reduz a chance; a trava garante uma
                    # reescrita. Se insistir, segue com log - e forma, nao fato.
                    valor = (
                        anuncia_valor(texto_provisorio)
                        if recorrente and not pediu_valor(_turnos_para_trava(history)) else None
                    )
                    if valor and not ja_refez_valor and not efeito_cometido:
                        ja_refez_valor = True
                        logger.warning(
                            f"[Valor] {phone} anunciou valor ({valor!r}) a paciente "
                            f"recorrente que nao perguntou; refazendo"
                        )
                        history.append({"role": "assistant", "content": content_blocks})
                        history.append({"role": "user", "content": (
                            "PARE. Esta pessoa JA E PACIENTE e nao perguntou o valor. "
                            "Nao anuncie valor, total nem desconto ao confirmar: "
                            "reescreva a mesma mensagem so com areas, data e horario. "
                            "Se ela perguntar o valor depois, ai sim responda."
                        )})
                        text_parts = []
                        continue
                    elif valor:
                        logger.error(
                            f"[Valor] {phone} insistiu em anunciar valor ({valor!r}); "
                            f"resposta segue | {texto_provisorio[:160]!r}"
                        )

                    if inventado and not ja_refez and not efeito_cometido:
                        ja_refez = True
                        logger.warning(
                            f"[Proveniencia] {phone} afirmou {sorted(inventado)} sem consultar; "
                            f"refazendo com consulta obrigatória"
                        )
                        history.append({"role": "assistant", "content": content_blocks})
                        history.append({"role": "user", "content": (
                            "PARE. Você acabou de afirmar data ou horário que não veio de "
                            "nenhuma tool nesta conversa. Não repita, não deduza a partir de "
                            "horários que você mesma deu antes e não complete a lista. "
                            "Chame agora a tool que traz esse dado e responda apenas com o "
                            "que ela devolver."
                        )})
                        forcar_proxima = True
                        text_parts = []
                        continue

                    history.append({"role": "assistant", "content": content_blocks})
                    break

                # Execute tool calls
                tool_results = []
                for tool_use in tool_uses:
                    result = self.tool_executor.execute(
                        tool_use["name"],
                        tool_use["input"],
                        context={"clinic_id": clinic_id, "phone": phone,
                                 "paciente": paciente,
                                 "estado_comercial": estado,
                                 "faq": itens_do_faq,
                                 "faq_entregues": faq_entregues,
                                 "session": session,
                                 "turnos": _turnos_para_trava(history)},
                    )
                    respaldo_das_tools.append(result)

                    # Intercept special tools
                    if tool_use["name"] == "present_options" and result.get("presented"):
                        pending_buttons = result
                    # Fase 6: a pergunta de esclarecimento e botoes com texto
                    # fixo; o que o modelo escrever junto e descartado. Vinda
                    # de pedir_esclarecimento ou de um handoff por
                    # incompreensao convertido em pergunta.
                    if result.get("esclarecimento"):
                        pending_buttons = result
                        esclarecimento_pedido = True
                    if result.get("handoff_requested") and tool_use["name"] == desambiguacao.NOME_DA_TOOL:
                        handoff_requested = True
                        motivo_do_handoff = result.get("reason") or MOTIVO_INCOMPREENSAO
                        esgotou_esclarecimento = True

                    if tool_use["name"] == "request_human_handoff" and result.get("handoff_requested"):
                        handoff_requested = True
                        motivo_do_handoff = result.get("reason") or MOTIVO_PEDIDO

                    # Trava que recusa o mesmo duas vezes não está protegendo,
                    # está presa: a resposta da paciente não destrava, e
                    # perguntar de novo é pedir que ela conserte um bug nosso.
                    if recusa_em_laco(recusas_da_conversa, result, phone):
                        laco_de_recusa = True

                    if tool_use["name"] in TOOLS_COM_EFEITO and not result.get("error"):
                        efeito_cometido = tool_use["name"]
                        # A data e o id do que foi gravado: quem decide sobre o
                        # aviso de menor de idade precisa da data DA SESSÃO, e
                        # do id para não contar o próprio agendamento como
                        # histórico. Ver menor_de_idade.
                        efeito_gravado = result

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use["id"],
                        "content": json.dumps(result, ensure_ascii=False, cls=DecimalEncoder),
                    })

                # Append assistant response + tool results for next iteration
                history.append({"role": "assistant", "content": content_blocks})
                history.append({"role": "user", "content": tool_results})

                # Os dois append acima vêm antes do break de propósito: o
                # tool_result precisa fechar o tool_use, senão o histórico
                # salvo fica inválido e a próxima mensagem da conversa morre
                # num 400 da API.
                if laco_de_recusa:
                    break
            else:
                # Nenhum `break`: as rodadas acabaram e o fechamento nao
                # produziu resposta aceita.
                esgotou = True

            if esgotou:
                # Narracao de intencao NAO e resposta; a pessoa fica com uma
                # atendente e a fila ve a pendencia.
                logger.error(
                    f"[Esgotado] {phone}: sem resposta apos {MAX_AGENT_ITERATIONS} rodadas "
                    f"e o fechamento; avisa que uma especialista confirma e entrega"
                )
                # Como nos outros bloqueios: a pessoa ouve que alguem vai
                # confirmar, em vez de silencio ate a recepcao ver a fila.
                text_parts = [
                    "Deixa eu confirmar isso certinho com uma especialista "
                    "para não te passar nada errado. Já te falo 😊"
                ]
                pending_buttons = None
                handoff_requested = True
                motivo_do_handoff = MOTIVO_ESGOTOU

        except AnthropicError as e:
            logger.error(f"[ConversationAgent] Anthropic API error for {phone}: {e}")
            # A paciente NÃO recebe nada. Ver bot_policy.entrega_por_instabilidade:
            # até 15/09/2026 saía daqui "estou com dificuldades, tente de novo",
            # que não ajuda ninguém e ainda convida a tentar contra um sistema
            # que vai falhar igual. Agora a conversa vai para uma pessoa.
            try:
                session["agent_history"] = self._truncate_history(
                    estado_comercial.sem_bloco(limpar_gatilhos(history)))
                session["mode"] = "agent"
                entrega_por_instabilidade(session)
                self._save_session(clinic_id, phone, session)
                logger.error(
                    f"[Instabilidade] {phone}: bot calado e conversa entregue a "
                    f"uma pessoa. A paciente está sem resposta."
                )
            except Exception as save_err:
                # Sem a sessão salva ninguém fica sabendo - por isso o log é ERROR
                # e não warning. Calar continua certo: a mensagem ruim seria pior.
                logger.error(
                    f"[Instabilidade] {phone}: falha ao registrar a pausa após o "
                    f"erro de API: {save_err}"
                )
            return []

        # Fase 6: intencao resolvida zera o contador de esclarecimento; a
        # pergunta sai com o texto fixo, sem a fala do modelo por cima; e
        # esgotar as tentativas e handoff com um texto que diz o que vem.
        if efeito_cometido or faq_entregues:
            desambiguacao.zera(session)
        if esclarecimento_pedido:
            if "\n".join(text_parts).strip():
                logger.info(f"[Desambiguacao] {phone}: descartei a fala do modelo junto da pergunta")
            text_parts = []
        if esgotou_esclarecimento and not "\n".join(text_parts).strip():
            text_parts = [desambiguacao.TEXTO_DE_ESGOTAMENTO]

        # 6. Handle handoff
        if handoff_requested:
            entrega_a_humano(session, motivo_do_handoff)
            # A pendencia e o que o bot nao conseguiu atender; vira tarefa
            # para uma pessoa (PRD 020 §3.6). Sem isto HUMAN_PENDING seria
            # conversa esquecida com cara de resolvida.
            self._abre_pendencia(session, clinic_id, phone, motivo_do_handoff)

        # 7. Build outgoing messages
        final_text = self._fix_whatsapp_bold("\n".join(text_parts).strip())
        # Modelo no meio, determinismo em volta. O prompt já proíbe afirmar
        # data, preço ou status sem consultar - e em 02/09/2026 o bot disse que
        # um agendamento cancelado estava confirmado mesmo assim, relendo a
        # própria mensagem de três dias antes. Instrução não segura isso.
        #
        # Data e horário sem respaldo BLOQUEIAM a resposta. Em 02/09/2026, à
        # pergunta "E horários à tarde?", o agente listou dez horários sem
        # chamar tool nenhuma - extrapolou da lista da noite que ele mesmo
        # dera minutos antes. O modo observação só registrou.
        #
        # Só data e horário derrubam a mensagem. Preço, duração e status
        # continuam apenas registrados: erram para o lado do constrangimento,
        # não o da paciente que vem num dia que não existe.
        # A trava recusou a mesma coisa duas vezes. A paciente já respondeu o que
        # foi perguntado, e responder de novo não vai mudar nada: quem não
        # destrava é o nosso catálogo ou a nossa regra. Entregar a conversa aqui
        # custa uma atendente; insistir custou, em 16/09/2026, uma hora e meia
        # da paciente e um pedido de desculpas da clínica. Ver recusa_repetida.
        if laco_de_recusa:
            final_text = (
                "Deixa eu confirmar essas áreas certinho com uma especialista "
                "para não te passar nada errado. Já te falo 😊"
            )
            pending_buttons = None
            handoff_requested = True
            entrega_a_humano(session, MOTIVO_AREAS_EM_LACO)

        # Ultima rede do pedido de cadastro. So chega aqui quem ja levou um PARE
        # explicito e insistiu. Rarissimo por construcao - o roteiro nem esta
        # mais no prompt - mas pedir CPF a uma paciente cadastrada e o erro que
        # nao pode sair daqui de jeito nenhum.
        if em_campanha or cadastrada:
            insistiu = pede_cadastro(final_text)
            if insistiu:
                logger.error(
                    f"[Cadastro] BLOQUEADO {phone}: insistiu em pedir cadastro "
                    f"{insistiu} depois do PARE | resposta={final_text[:200]!r}"
                )
                final_text = (
                    "Perfeito! Vou confirmar os detalhes com uma especialista e "
                    "ja te retorno 😊"
                )
                pending_buttons = None
                handoff_requested = True
                entrega_a_humano(session, MOTIVO_INSISTIU_CADASTRO)

        # A restrição do menor de idade é afirmação sobre a pessoa, não sobre a
        # agenda - fatos_sem_origem não a enxerga. Sem esta trava, "você precisa
        # de responsável legal" chega a uma adulta e nada impede. Ver
        # menor_de_idade.
        try:
            if afirmacao_de_menor_sem_respaldo(final_text, respaldo_das_tools):
                logger.error(
                    f"[MenorDeIdade] BLOQUEADO {phone}: afirmou a restrição de menor "
                    f"sem nenhuma tool ter confirmado a idade | "
                    f"resposta={final_text[:200]!r}"
                )
                final_text = (
                    "Deixa eu confirmar uma informação aqui certinho para não te "
                    "passar nada errado. Já te falo 😊"
                )
                pending_buttons = None
                handoff_requested = True
                entrega_a_humano(session, MOTIVO_AFIRMOU_MENOR)
        except Exception as e:
            logger.error(f"[MenorDeIdade] Falha ao conferir a resposta de {phone}: {e}")

        try:
            sem_origem = fatos_sem_origem(final_text, respaldo_das_tools)
            inventado = fatos_de_agenda(sem_origem)

            if inventado:
                logger.error(
                    f"[Proveniencia] BLOQUEADO {phone}: agenda sem respaldo "
                    f"{sorted(inventado)} | tools={len(respaldo_das_tools)} "
                    f"| refez={ja_refez} | resposta={final_text[:200]!r}"
                )
                # Só chega aqui quem já foi mandado consultar e mesmo assim
                # inventou de novo. Aí a especialista é o caminho certo: a
                # alternativa é ficar tentando enquanto a pessoa espera.
                #
                # Mas se uma tool já mudou o mundo nesta execução, a mensagem
                # não pode fingir que nada aconteceu: o agendamento existe no
                # banco, e sumir com ele deixaria a pessoa sem saber que tem
                # uma sessão marcada. "Efeito só no fim" - quando o efeito
                # escapa para o meio, a mensagem tem que contá-lo.
                if efeito_cometido:
                    logger.error(
                        f"[Proveniencia] {phone}: bloqueio APÓS {efeito_cometido} já "
                        f"executado. A ação está no banco e a mensagem foi trocada."
                    )
                    final_text = (
                        "Registrei aqui e uma especialista vai te confirmar os "
                        "detalhes em instantes, para não te passar nada errado 😊"
                    )
                else:
                    final_text = (
                        "Deixa eu confirmar os horários certinho com uma especialista "
                        "para não te passar nada errado. Já te falo 😊"
                    )
                pending_buttons = None
                handoff_requested = True
                # A pausa nao vence: so o "Retomar bot" no painel a remove.
                entrega_a_humano(session, MOTIVO_AGENDA_SEM_RESPALDO)
            elif sem_origem:
                logger.warning(
                    f"[Proveniencia] {phone} afirmou sem respaldo: {sorted(sem_origem)} "
                    f"| tools={len(respaldo_das_tools)} | resposta={final_text[:120]!r}"
                )
            else:
                logger.info(f"[Proveniencia] {phone} ok | tools={len(respaldo_das_tools)}")
        except Exception as e:
            # A conferência nunca pode derrubar o atendimento: falhando ela, a
            # resposta segue como estava, que é o comportamento de antes dela.
            logger.error(f"[Proveniencia] Falha ao conferir resposta de {phone}: {e}")

        # O FAQ escolhido vai em bolha propria, byte a byte; a fala do modelo,
        # se repete o item, cai. Mais de dois itens num turno e pergunta
        # confusa: pessoa, sem o modelo desempatar (PRD 020 §4.3).
        if len(faq_entregues) > policy_do_faq.MAX_ITENS_POR_TURNO:
            logger.warning(
                f"[FAQ] {phone}: {len(faq_entregues)} itens num turno "
                f"({[i['question_key'] for i in faq_entregues]}); pergunta confusa, vai a pessoa"
            )
            faq_entregues = []
            final_text = (
                "Deixa eu confirmar isso certinho com uma especialista "
                "para não te passar nada errado. Já te falo 😊"
            )
            pending_buttons = None
            handoff_requested = True
            entrega_a_humano(session, MOTIVO_SEM_RESPOSTA)
        elif faq_entregues:
            final_text = policy_do_faq.fala_sem_o_item(final_text, faq_entregues, phone)

        outgoing = self._build_outgoing(final_text, pending_buttons, faq_entregues)

        # O aviso pré-sessão sai daqui, não da boca do modelo: são 15 linhas com
        # contraindicação médica que têm de chegar palavra por palavra. Ver
        # orientacoes_pos_sessao. Vale para agendamento novo e remarcação - quem
        # remarcou vai à sessão do mesmo jeito e precisa se preparar igual.
        # O aviso do menor de idade vem ANTES do de preparo: saber se pode fazer
        # a sessão vale mais do que saber como se preparar para ela. Só no fluxo
        # de lead - na campanha estão pacientes que já estrearam. Ver
        # menor_de_idade.
        if efeito_cometido == "book_appointment" and not em_campanha:
            try:
                if precisa_avisar_menor(
                    self.db, clinic_id, phone,
                    efeito_gravado.get("date"),
                    efeito_gravado.get("appointment_id"),
                ):
                    outgoing.append(OutgoingMessage(
                        message_type="text", content=AVISO_DE_MENOR,
                    ))
            except Exception as e:
                # O agendamento existe e a pessoa precisa saber disso. Falhar a
                # resposta inteira por causa do aviso seria trocar o essencial
                # pelo complemento - e o aviso ainda pode ser dado pela clínica.
                logger.error(f"[MenorDeIdade] Falha ao decidir o aviso de {phone}: {e}")

        if efeito_cometido in TOOLS_QUE_MARCAM_SESSAO:
            outgoing.append(OutgoingMessage(
                message_type="text",
                content=orientacoes_da_clinica(self.template_service, clinic_id),
            ))
            logger.info(
                f"[OrientacoesPosSessao] {phone}: aviso pré-sessão anexado "
                f"após {efeito_cometido}"
            )

        # 8. Save history (truncated)
        session["agent_history"] = self._truncate_history(
            estado_comercial.sem_bloco(limpar_gatilhos(history)))
        session["mode"] = "agent"
        # Guarda o que a conversa INTEIRA consultou, não só esta rodada: a
        # pessoa negocia data por vários turnos e o bot repete o mesmo fato
        # consultado. Cortado nos últimos RESPALDO_GUARDADO porque a sessão vive
        # no DynamoDB (limite de 400KB por item) e resultado de tool cresce
        # rápido - list_areas de uma clínica grande já são alguns KB.
        session["respaldo_anterior"] = self._convert_decimals(
            respaldo_das_tools[-RESPALDO_GUARDADO:]
        )
        # Quem agrupa a rajada precisa saber se esta rodada gravou algo no
        # banco. Se gravou, a resposta vai mesmo que a pessoa tenha escrito no
        # meio: um agendamento existe e ela precisa saber. Se nao gravou, a
        # resposta pode ser descartada em favor da rajada completa.
        #
        # Handoff E efeito: a pausa ja esta gravada nesta sessao. Em
        # 06/10/2026 o agente pediu especialista, a paciente escreveu durante o
        # processamento, o agregador descartou a MENSAGEM e manteve a PAUSA -
        # a rodada seguinte viu "atendente ativa" e calou. Ela ficou tres horas
        # sem resposta nenhuma, e ninguem lhe disse que alguem viria.
        session["efeito_na_ultima_rodada"] = bool(efeito_cometido) or bool(handoff_requested)
        session[CAMPO_DE_RECUSAS] = recusas_da_conversa
        self._save_session(clinic_id, phone, session)

        if chamadas_ao_modelo:
            registra_consumo_total(
                consumo_da_mensagem, MODELO_DO_AGENTE, phone, chamadas_ao_modelo
            )

        elapsed = time.time() - start_time
        logger.info(f"[ConversationAgent] Processed message for {phone} in {elapsed:.2f}s, {len(outgoing)} outgoing messages")

        return outgoing

    # ── System prompt ──

    def _config_fora_do_escopo(self, clinic_id):
        """Só as colunas de termos extras (fora do escopo e risco), não a
        clínica inteira.

        Consulta própria porque a guarda roda ANTES do prompt ser montado - é
        justamente o ponto: a mensagem não chega ao modelo. Uma linha por
        mensagem recebida, contra o risco de responder preço de laser a quem
        perguntou de injetável.

        Falha vira dict vazio: sem os termos da clínica a lista do código ainda
        barra o que ela nomeia, e isso é melhor do que derrubar a conversa.
        """
        try:
            linhas = self.db.execute_query(
                "SELECT bot_procedimentos_fora_do_escopo, bot_termos_de_risco "
                "FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
                (clinic_id,),
            )
            return linhas[0] if linhas else {}
        except Exception as e:
            logger.warning(
                f"[ForaDoEscopo] não li os termos de {clinic_id}: {e}"
            )
            return {}

    def _build_system_prompt(self, clinic_id, phone, session=None):
        """Build the system prompt with clinic context.

        `session` entra por causa da campanha de reagendamento: o MODO da
        conversa e lido do banco, nunca inferido pelo modelo. Modelo inferindo
        em que fluxo esta pode trocar de fluxo no meio, e o erro chega a
        paciente como "o bot me pediu o CPF de novo".
        """
        # Get clinic info
        clinic_rows = self.db.execute_query(
            "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,),
        )
        clinic = clinic_rows[0] if clinic_rows else {}

        # Check if single service clinic
        service_rows = self.db.execute_query(
            "SELECT id, name FROM scheduler.services WHERE clinic_id = %s AND active = true",
            (clinic_id,),
        )
        single_service_hint = ""
        if len(service_rows) == 1:
            single_service_hint = (
                f"Esta clínica oferece APENAS 1 serviço: {service_rows[0]['name']}. "
                f"Pule a etapa de seleção de serviço e vá direto para áreas."
            )

        # Get discount rules for context
        discount_context = ""
        rules_rows = self.db.execute_query(
            "SELECT * FROM scheduler.discount_rules WHERE clinic_id = %s AND is_active = TRUE",
            (clinic_id,),
        )
        if rules_rows:
            rules = rules_rows[0]
            discount_context = (
                f"\n═══ DESCONTOS ═══\n"
                f"Regras vigentes (apenas para seu contexto):\n"
                f"• Primeira sessão: {rules['first_session_discount_pct']}%\n"
                f"• {rules['tier_2_min_areas']}-{rules['tier_2_max_areas']} áreas: {rules['tier_2_discount_pct']}%\n"
                f"• {rules['tier_3_min_areas']}+ áreas: {rules['tier_3_discount_pct']}%\n"
                f"\n"
                f"REGRAS CRÍTICAS (NÃO QUEBRE):\n"
                f"1. Descontos são MUTUAMENTE EXCLUSIVOS — nunca cumulativos. "
                f"A tool calculate_discount aplica APENAS UM desconto: o de primeira sessão (se aplicável) "
                f"OU o de faixa de áreas, jamais os dois juntos.\n"
                f"2. NUNCA cite uma porcentagem de desconto, valor com desconto, ou qualquer "
                f"número de desconto sem ter chamado calculate_discount ANTES nesta mesma mensagem. "
                f"Se ainda não chamou, chame antes de responder.\n"
                f"3. Chame calculate_discount em DOIS momentos do fluxo:\n"
                f"   (a) Logo após a paciente confirmar as áreas, ANTES de mostrar o subtotal e perguntar sobre data. "
                f"Apresente o resultado como: 'Total: ~De {{original}}~ por *{{final}}* ({{discount_pct}}% de desconto — {{motivo amigável}})'. "
                f"Se discount_pct=0, mostre apenas 'Total: *{{final}}*'.\n"
                f"   (b) Novamente no resumo final do agendamento (etapa 6), passando os mesmos valores para book_appointment.\n"
                f"4. Os valores 'De X por Y' devem vir EXATAMENTE de original_price_display e discounted_price_display "
                f"retornados pela tool. Não recalcule manualmente.\n"
                f"5. Não explique por que outras regras de desconto não se aplicaram. Apenas anuncie "
                f"o resultado retornado pela tool. A tool já escolhe a melhor opção para a paciente "
                f"(maior desconto aplicável entre todas as regras vigentes)."
            )

        variables = {
            "clinic_display_name": clinic.get("display_name") or clinic.get("name", "Clínica"),
            "clinic_address": clinic.get("address") or "",
            "clinic_phone": clinic.get("phone") or "",
            "collected_data_summary": "",
            "single_service_hint": single_service_hint,
            # O valor vem do banco, nao do texto do prompt. Ver preco_minimo.py:
            # numero escrito no template envelhece calado quando a tabela muda.
            "preco_minimo": preco_minimo_por_area(self.db, clinic_id),
        }

        system_prompt = self.template_service.get_and_render(clinic_id, "AI_SYSTEM_PROMPT", variables)
        system_prompt += discount_context

        # O FAQ SAIU DAQUI de propósito.
        #
        # Despejar a base inteira no prompt fazia com que responder de memória
        # fosse o caminho normal: para toda dúvida, `tools=0` era o esperado, e
        # com isso não havia como distinguir "repetiu o FAQ" de "completou o FAQ
        # com o que parecia plausível". O verificador ficava cego justamente na
        # maior classe de respostas.
        #
        # Agora get_faq_answer é o único caminho até a resposta. Custa uma
        # rodada de latência por dúvida e devolve o sinal: sem tool, sem fato.
        system_prompt += (
            "\n═══ COMO RESPONDER DÚVIDAS ═══\n"
            "1. Toda dúvida sobre o procedimento é respondida por get_faq_answer. Você não\n"
            "   tem a base de conhecimento na memória: ela está na lista de itens da tool,\n"
            "   e só lá. Escolha o item que responde a dúvida.\n"
            "2. O texto do item vai para a pessoa AUTOMATICAMENTE, como mensagem própria,\n"
            "   exatamente como a clínica escreveu. NÃO o repita, NÃO o resuma, NÃO o\n"
            "   reformule na sua resposta. Se ela perguntou outra coisa na mesma mensagem,\n"
            "   responda só essa outra coisa; se não, não escreva nada.\n"
            "3. Se nenhum item da lista responde a dúvida, você NÃO SABE. Não complete com\n"
            "   conhecimento geral sobre depilação a laser, por mais seguro que pareça:\n"
            "   diga que vai confirmar com uma especialista e chame request_human_handoff.\n"
            "4. Isso vale mesmo para o que parece óbvio - intervalo entre sessões, número\n"
            "   de sessões, cuidados, contraindicações. Cada clínica tem o seu protocolo.\n"
        )

        # Segunda rede do fora_do_escopo. A lista determinística barra o que ela
        # nomeia; isto cobre o procedimento que a clínica vende e ninguém
        # cadastrou - e vem DEPOIS do bloco de dúvidas de propósito, porque
        # precisa vencer o "toda dúvida começa com get_faq_answer".
        system_prompt += INSTRUCAO_FORA_DO_ESCOPO

        # Fase 6 (PRD 020 §4.1): perguntar antes de desistir. A pergunta e
        # texto fixo com botoes (desambiguacao); o modelo so escolhe as opcoes.
        system_prompt += (
            "\n═══ QUANDO NÃO ENTENDER ═══\n"
            "1. Se não dá para saber o que ela quer (agendar, remarcar, cancelar ou\n"
            "   tirar dúvida) e a mensagem não ajuda, chame pedir_esclarecimento com as\n"
            "   opções plausíveis. A pergunta vai com botões, em texto fixo: não a\n"
            "   escreva você.\n"
            "2. Não chame request_human_handoff por não ter entendido: a tool de\n"
            "   esclarecimento decide quando desistir e chamar uma pessoa.\n"
        )

        system_prompt += (
            "\n═══ FALA DA ATENDENTE ═══\n"
            "No historico, turnos que comecam com [atendente da clinica]: foram\n"
            "escritos por uma pessoa da clinica, nao por voce. Sao compromissos da\n"
            "clinica: nao os repita como seus, nao os contradiga e nao os estenda\n"
            "(se ela prometeu um desconto ou um encaixe, nao invente outro).\n"
        )

        # Regra de datas: fica aqui, no prefixo cacheado, porque é estática. O
        # que muda por mensagem é o bloco CALENDÁRIO, que entra no turno da
        # pessoa. Sem esta regra o agente tinha a data e ainda assim não sabia o
        # que fazer quando a data pedida não tinha vaga.
        system_prompt += (
            "\n═══ DATAS ═══\n"
            "1. Toda mensagem traz um bloco CALENDÁRIO com a data de hoje e o que as\n"
            "   referências da pessoa significam (\"amanhã\", \"sexta\", \"semana que vem\").\n"
            "   Use-o. Nunca diga que não consegue calcular uma data.\n"
            "2. O calendário diz que dia é, não que há vaga. Disponibilidade vem de\n"
            "   check_availability, sempre.\n"
            "3. Se a data que a pessoa pediu NÃO estiver entre as datas disponíveis:\n"
            "   diga que naquele dia não há agenda, nomeando o dia como ela falou e\n"
            "   com a data ao lado, e ofereça as datas que existem.\n"
            "   Exemplo: 'Amanhã (05/09) não temos horário. As datas mais próximas\n"
            "   são: quarta, 23/09 e quinta, 24/09. Alguma dessas serve?'\n"
            "4. Não empurre a pessoa de volta para a lista sem responder o que ela\n"
            "   perguntou. 'Escolha uma data da lista' não é resposta para 'tem\n"
            "   amanhã?' - a resposta é sim ou não, e então as opções.\n"
        )

        system_prompt += (
            "\n═══ ÁREAS ═══\n"
            "1. As áreas são escolha da paciente. NUNCA escolha por ela, nem para\n"
            "   'adiantar', nem porque pareciam prováveis, nem porque você as viu no\n"
            "   histórico dela.\n"
            "2. Antes de get_time_slots, calculate_discount ou book_appointment, as\n"
            "   áreas precisam ter sido ditas nesta conversa: ou ela pediu, ou você\n"
            "   perguntou e ela respondeu. As tools RECUSAM área que não passou por\n"
            "   isso, e devolvem o que fazer.\n"
            "3. Você NÃO consulta o histórico de áreas da paciente, e não tem tool para\n"
            "   isso. O que ela tratou antes não diz o que ela quer agora: pergunte.\n"
            "4. Horário depende de área: a duração da sessão vem das áreas. Passar\n"
            "   horários antes de saber as áreas é passar horário errado.\n"
            "5. Dois nomes populares cobrem mais de uma área, e a paciente costuma\n"
            "   usá-los achando que está sendo específica. Antes de seguir, PERGUNTE:\n"
            "   - barriga ou abdômen: confirme se ela não está se referindo à LINHA\n"
            "     ALBA (a faixa vertical no centro da barriga).\n"
            "   - virilha, em qualquer variação: ofereça incluir a região do ÂNUS\n"
            "     (perianal). Vale também para 'virilha completa' - muita gente chama\n"
            "     de completa a que já inclui o períneo.\n"
            "   Faça a pergunta e espere a resposta dela. As tools RECUSAM essas\n"
            "   áreas enquanto o assunto não aparecer na conversa.\n"
        )
        system_prompt += (
            "\n═══ INSTRUÇÕES PÓS-AGENDAMENTO ═══\n"
            "Confirmado o agendamento (ou a remarcação), o sistema envia SOZINHO, logo\n"
            "depois da sua mensagem, o aviso de preparo pré-sessão da clínica.\n"
            "1. Você NÃO escreve esse aviso e NÃO o resume. Ele já vai, inteiro.\n"
            "2. Sua mensagem de confirmação termina normalmente. Não diga 'seguem as\n"
            "   orientações abaixo' nem anuncie o que vem - apenas confirme.\n"
            "3. Se ela perguntar sobre preparo DEPOIS de receber o aviso, aí sim\n"
            "   responda, via get_faq_answer como qualquer outra dúvida."
        )

        # Só no fluxo de lead. Quem vem pela campanha já é paciente cadastrada:
        # a primeira sessão dela já aconteceu, e a exigência não se aplica.
        # Ver menor_de_idade.
        if not campanha_viva(session):
            system_prompt += (
                "\n═══ IDADE DA PACIENTE ═══\n"
                "1. Você NÃO calcula idade. Nunca. Se a pessoa disser a data de\n"
                "   nascimento, disser a idade, ou der qualquer sinal de ser menor\n"
                "   (\"tenho 16\", \"minha mãe vai junto\", \"estou no ensino médio\"),\n"
                "   chame calculate_patient_age. Ela responde a idade NA DATA DA\n"
                "   SESSÃO, que é o que importa - quem faz 18 antes da sessão chega\n"
                "   maior de idade.\n"
                "2. Se a tool devolver is_minor=true, diga a ela, com suas palavras,\n"
                "   que a PRIMEIRA sessão só acontece de uma destas duas formas:\n"
                "   - com um responsável legal acompanhando no dia; ou\n"
                "   - com autorização formal do responsável legal, assinada\n"
                "     digitalmente pelo Gov.br.\n"
                "   Diga também que isso vale só para a primeira sessão.\n"
                "3. Isso NÃO impede o agendamento. Ela pode escolher data e horário\n"
                "   normalmente - a exigência é sobre o dia da sessão, não sobre\n"
                "   marcar. Não transfira para humano por causa disso.\n"
                "4. Se a tool disser que não há data de nascimento, pergunte a data\n"
                "   de nascimento antes de seguir. Não presuma que é maior de idade.\n"
            )

        bloco_da_campanha = self._bloco_da_campanha(clinic_id, phone, session)
        if bloco_da_campanha:
            # Tira o roteiro de lead ANTES de acrescentar o da campanha. Antes
            # isto era so acrescimo, e o roteiro antigo continuava la: em
            # 11/09/2026 o bot reproduziu palavra por palavra o passo 6 dele,
            # pedindo CPF a uma paciente cadastrada.
            system_prompt = adapta_para_campanha(system_prompt)
        system_prompt += bloco_da_campanha

        return system_prompt

    def _bloco_da_campanha(self, clinic_id, phone, session):
        """O que muda quando a conversa e de campanha - e nada quando nao e.

        Fica no FIM do prompt de proposito: tudo acima e identico nos dois
        fluxos, entao o prefixo continua compartilhado e o cache do Anthropic
        segue valendo. Dentro de uma conversa o bloco nao muda (mesma paciente,
        mesmas datas), entao ele tambem nao invalida cache entre turnos.
        """
        if not campanha_viva(session):
            return ""

        datas = datas_da_campanha(session)
        nome = ""
        try:
            linhas = self.db.execute_query(
                "SELECT name FROM scheduler.patients "
                "WHERE clinic_id = %s AND phone = %s AND deleted_at IS NULL LIMIT 1",
                (clinic_id, phone),
            )
            if linhas:
                nome = (linhas[0].get("name") or "").strip()
        except Exception as e:
            # Sem o nome o bot so evita chama-la pelo nome. Derrubar a conversa
            # por causa disso seria trocar o essencial pelo enfeite.
            logger.error(f"[Campanha] Nao consegui ler o cadastro de {phone}: {e}")

        linha_nome = f"Nome dela (do cadastro): {nome}\n" if nome else ""

        return (
            "\n═══ CONVERSA DE CAMPANHA ═══\n"
            "Esta pessoa JÁ É PACIENTE CADASTRADA e acabou de receber de nós a\n"
            "mensagem com as datas abertas. A conversa começou por nossa iniciativa,\n"
            "não pela dela.\n"
            f"{linha_nome}"
            f"Datas que anunciamos a ela: {', '.join(datas)}\n"
            "\n"
            "O que muda nesta conversa:\n"
            "1. NÃO dê boas-vindas e não se apresente. A conversa já está em andamento.\n"
            "2. NUNCA peça nome, CPF, data de nascimento ou e-mail. Já temos o cadastro\n"
            "   dela. Pedir de novo é o erro mais visível que você pode cometer aqui.\n"
            "3. NÃO anuncie preço, total nem desconto. Só fale de valor se ELA perguntar.\n"
            "4. Comece pelas ÁREAS, antes de qualquer horário: pergunte quais áreas\n"
            "   ela quer tratar DESTA VEZ. Sempre pergunte, mesmo que ela já seja\n"
            "   cliente antiga - o que ela fez da última vez não diz o que ela quer\n"
            "   agora, e supor por ela já custou caro aqui.\n"
            "   Só depois da resposta dela vá para os horários.\n"
            "5. Ofereça APENAS as datas anunciadas acima. Confirme os horários com\n"
            "   check_availability e get_time_slots, como sempre.\n"
            "6. Ao fechar, apenas confirme: o aviso de preparo pré-sessão é enviado\n"
            "   pelo sistema, como em qualquer agendamento.\n"
            "\n"
            "Continua valendo tudo o mais: calculate_discount antes de book_appointment\n"
            "(o preço gravado tem de estar certo, mesmo sem ser anunciado), get_faq_answer\n"
            "para dúvidas, e nunca afirmar data ou horário que não veio de uma tool.\n"
        )

    # ── WhatsApp formatting fix ──

    @staticmethod
    def _fix_whatsapp_bold(text: str) -> str:
        """Fix bold formatting for WhatsApp.

        WhatsApp uses *text* for bold. Common LLM issues:
        - *text*! → should be *text!*  (punctuation outside asterisk)
        - **text** → should be *text*  (double asterisks from Markdown)
        """
        import re
        # Fix double asterisks → single: **text** → *text*
        text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)
        # Fix punctuation after closing asterisk: *text*! → *text!*
        text = re.sub(r'\*([^*]+)\*([.!?,;:]+)', r'*\1\2*', text)
        return text

    # ── Outgoing message builder ──

    @staticmethod
    def _junta_texto(mensagem_das_opcoes, texto_final):
        """As duas falas do modelo quando ele oferece opções, sem perder nenhuma.

        Era `texto_final or mensagem_das_opcoes`: escrevendo os dois, o texto
        final ganhava e a mensagem das opções sumia. Quase sempre dava no mesmo
        porque o modelo repetia a mesma frase nos dois lugares - mas quando ele
        responde numa e conduz na outra, o que sumia era a resposta:

            opções: "Amanhã (05/09) não temos horário. As próximas datas são:"
            final:  "Alguma dessas fica boa pra você?"

        A paciente recebia só a segunda. O padrão "responde e então oferece" era
        impossível de entregar.
        """
        primeira = (mensagem_das_opcoes or "").strip()
        segunda = (texto_final or "").strip()
        if not primeira or not segunda:
            return primeira or segunda
        # Repetiu a mesma frase nos dois lugares: manda a mais completa, não as
        # duas coladas.
        if primeira in segunda:
            return segunda
        if segunda in primeira:
            return primeira
        return f"{primeira}\n\n{segunda}"

    def _build_outgoing(self, text, pending_buttons, faq_entregues=None):
        """Convert agent output into OutgoingMessage list.

        `faq_entregues`: itens do FAQ escolhidos neste turno. Cada um vira
        uma mensagem propria, com o texto da clinica byte a byte, ANTES da
        fala do modelo - nunca na mesma bolha (policy_do_faq).
        """
        messages = []
        for item in faq_entregues or []:
            messages.append(OutgoingMessage(message_type="text", content=item["answer"]))

        if pending_buttons:
            options = pending_buttons.get("options", [])
            button_message = pending_buttons.get("message", "")
            display_text = self._junta_texto(button_message, text)

            if len(options) <= 3:
                # WhatsApp supports up to 3 inline buttons
                buttons = [{"id": opt["id"], "label": opt["label"][:24]} for opt in options]
                messages.append(OutgoingMessage(
                    message_type="buttons",
                    content=display_text,
                    buttons=buttons,
                ))
            else:
                # Too many for buttons — format as numbered list in text
                numbered = "\n".join(
                    f"{i+1}. {opt['label']}" for i, opt in enumerate(options)
                )
                full_text = f"{display_text}\n\n{numbered}" if display_text else numbered
                messages.append(OutgoingMessage(
                    message_type="text",
                    content=full_text,
                ))
        elif text:
            messages.append(OutgoingMessage(
                message_type="text",
                content=text,
            ))

        return messages

    # ── Session management ──

    def _load_session(self, clinic_id, phone):
        try:
            response = self.sessions_table.get_item(
                Key={"pk": f"CLINIC#{clinic_id}", "sk": f"PHONE#{phone}"}
            )
            item = response.get("Item")
            if item:
                session = item.get("session", {})
                # DynamoDB returns Decimal — convert to native Python types
                session = self._convert_decimals(session)
                logger.info(f"[ConversationAgent] Session loaded for {phone}, mode={session.get('mode')}")
                return session
        except Exception as e:
            logger.error(f"[ConversationAgent] Error loading session for {phone}: {e}")
        return {}

    def _save_session(self, clinic_id, phone, session):
        try:
            now = int(time.time())
            self.sessions_table.put_item(
                Item={
                    "pk": f"CLINIC#{clinic_id}",
                    "sk": f"PHONE#{phone}",
                    "session": session,
                    "clinicId": clinic_id,
                    "phone": phone,
                    "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                }
            )
        except Exception as e:
            logger.error(f"[ConversationAgent] Error saving session for {phone}: {e}")

    def _sai_antes_do_modelo(self, session, clinic_id, phone, history, motivo, texto):
        """A conversa vai para uma pessoa sem o modelo ler a mensagem: grava
        o historico, entrega, abre a pendencia (a fila precisa ver) e responde
        o texto fixo. Usado pelo fora_do_escopo e pelo nivel 3."""
        session["agent_history"] = self._truncate_history(history)
        session["mode"] = "agent"
        entrega_a_humano(session, motivo)
        self._abre_pendencia(session, clinic_id, phone, motivo)
        self._save_session(clinic_id, phone, session)
        return self._build_outgoing(texto, None)

    def _abre_pendencia(self, session, clinic_id, phone, motivo):
        """Grava a intencao pendente no bloco e abre a tarefa. Nunca levanta."""
        try:
            from src.services import atendimento as _atendimento
            from src.services import tarefas as _tarefas

            intencao = motivo or "handoff"
            b = _atendimento.bloco(session)
            b["pending_intent"] = intencao
            b["pending_since"] = b.get("pending_since") or int(time.time())
            tarefa = _tarefas.abre(self.db, clinic_id, phone, intencao, motivo or "")
            if tarefa:
                b["pending_task_id"] = tarefa
            _atendimento._comete(session, b)
        except Exception as e:
            logger.error(f"[Tarefas] {phone}: nao abri a pendencia do handoff: {e}")

    def _identifica_paciente(self, clinic_id, phone):
        """Nunca levanta: sem identificacao o fluxo e o de lead, que pergunta."""
        try:
            return identificar_paciente(self.db, clinic_id, phone) or {}
        except Exception as e:
            logger.error(f"[Identificacao] {phone}: {e}")
            return {}

    @staticmethod
    def _convert_decimals(obj):
        """Recursively convert Decimal to int/float for JSON serialization."""
        if isinstance(obj, Decimal):
            return int(obj) if obj == int(obj) else float(obj)
        if isinstance(obj, dict):
            return {k: ConversationAgent._convert_decimals(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [ConversationAgent._convert_decimals(i) for i in obj]
        return obj

    def rebuild_history_from_events(self, clinic_id, phone, limit=20):
        """Reconstrói o histórico do MessageEvents quando a sessão está vazia."""
        try:
            eventos = self.message_tracker.get_conversation_messages(clinic_id, phone, limit=limit)
            history = events_to_history(eventos)
            if history:
                logger.info(
                    f"[ConversationAgent] Histórico reconstruído do MessageEvents para {phone}: "
                    f"{len(history)} turnos"
                )
            return history
        except Exception as e:
            logger.warning(f"[ConversationAgent] Falha ao reconstruir histórico de {phone}: {e}")
            return []

    def _truncate_history(self, history):
        """Keep the last MAX_HISTORY_PAIRS message pairs to stay within DynamoDB limits.

        Ensures the truncated history never starts with a tool_result (user message
        referencing a tool_use in a now-removed assistant message), which would cause
        Anthropic API error 400.
        """
        max_items = MAX_HISTORY_PAIRS * 2
        if len(history) > max_items:
            history = history[-max_items:]

        # Strip leading messages until we reach a plain user text message.
        # A valid conversation must start with a user message whose content is
        # a string (not a list of tool_result blocks).
        while history:
            first = history[0]
            if first.get("role") == "user":
                content = first.get("content")
                # Plain text user message — valid start
                if isinstance(content, str):
                    break
                # List content could be tool_results — check
                if isinstance(content, list) and any(
                    block.get("type") == "tool_result" for block in content
                ):
                    # Orphaned tool_result — remove it
                    history.pop(0)
                    continue
                break
            # Assistant message without preceding user message — remove it
            history.pop(0)

        return history
