import json
import os
import time
import logging
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

import boto3

from src.services.anthropic_service import AnthropicService, AnthropicError
from src.services.ai_tools import ToolExecutor, get_tool_definitions
from src.services.calendario import bloco_de_contexto
from src.services.proveniencia import fatos_de_agenda, fatos_sem_origem
from src.services.roteador import exige_consulta, intencoes, tools_obrigatorias
from src.services.template_service import TemplateService

logger = logging.getLogger(__name__)

MAX_AGENT_ITERATIONS = 5
MAX_HISTORY_PAIRS = 20
ATTENDANT_TTL_SECONDS = 24 * 60 * 60

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

        # 2. Check attendant mode
        if self._is_attendant_active(session):
            logger.info(f"[ConversationAgent] Attendant active for {phone}, skipping")
            return []

        # 3. Build system prompt
        system_prompt = self._build_system_prompt(clinic_id, phone)

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
        history.append({"role": "user", "content": user_content})

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
                        nome_tool, {}, context={"clinic_id": clinic_id, "phone": phone}
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

        if dados_consultados or bloco_calendario:
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
                + cabecalho_dados
                + f"═══ MENSAGEM DA PESSOA ═══\n{user_content}"
            )}

        tools = get_tool_definitions(format="anthropic")
        pending_buttons = None
        handoff_requested = False
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
        efeito_cometido = None

        try:
            for iteration in range(MAX_AGENT_ITERATIONS):
                logger.info(f"[ConversationAgent] Iteration {iteration + 1} for {phone}")

                # Consumido a cada volta: forçar sempre deixaria o modelo sem
                # como encerrar, já que toda resposta exigiria mais uma tool.
                forcar_tool = {"type": "any"} if forcar_proxima else None
                forcar_proxima = False
                if forcar_tool:
                    logger.info(f"[ConversationAgent] Consulta obrigatória para {phone}")

                response = self.anthropic.create_message(
                    system=system_prompt,
                    messages=history,
                    tools=tools,
                    max_tokens=1024,
                    tool_choice=forcar_tool,
                )

                # Parse response content blocks
                content_blocks = response.get("content", [])
                current_text_parts = []
                tool_uses = []

                for block in content_blocks:
                    if block["type"] == "text":
                        current_text_parts.append(block["text"])
                    elif block["type"] == "tool_use":
                        tool_uses.append(block)

                if current_text_parts:
                    text_parts = current_text_parts

                stop_reason = response.get("stop_reason", "end_turn")

                if not tool_uses:
                    # Resposta final: confere antes de aceitar. Data e horário
                    # afirmados sem respaldo não viram mensagem - mas a primeira
                    # reação é mandar consultar, não desistir da conversa.
                    texto_provisorio = "\n".join(current_text_parts).strip()
                    inventado = self._agenda_sem_respaldo(texto_provisorio, respaldo_das_tools)

                    # Efeito já cometido não se refaz: mandar consultar de novo
                    # convida o modelo a chamar book_appointment outra vez.
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
                        context={"clinic_id": clinic_id, "phone": phone},
                    )
                    respaldo_das_tools.append(result)

                    # Intercept special tools
                    if tool_use["name"] == "present_options" and result.get("presented"):
                        pending_buttons = result

                    if tool_use["name"] == "request_human_handoff" and result.get("handoff_requested"):
                        handoff_requested = True

                    if tool_use["name"] in TOOLS_COM_EFEITO and not result.get("error"):
                        efeito_cometido = tool_use["name"]

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use["id"],
                        "content": json.dumps(result, ensure_ascii=False, cls=DecimalEncoder),
                    })

                # Append assistant response + tool results for next iteration
                history.append({"role": "assistant", "content": content_blocks})
                history.append({"role": "user", "content": tool_results})

        except AnthropicError as e:
            logger.error(f"[ConversationAgent] Anthropic API error for {phone}: {e}")
            # Persist whatever history we have (including the user's just-arrived
            # message) so the next attempt has the full context. Without this,
            # the user's message is silently dropped and they have to repeat it.
            try:
                session["agent_history"] = self._truncate_history(limpar_gatilhos(history))
                session["mode"] = "agent"
                self._save_session(clinic_id, phone, session)
            except Exception as save_err:
                logger.error(f"[ConversationAgent] Failed to persist session after API error: {save_err}")
            return [OutgoingMessage(
                message_type="text",
                content="Desculpe, estou com dificuldades no momento. Tente novamente em instantes.",
            )]

        # 6. Handle handoff
        if handoff_requested:
            session["state"] = "HUMAN_HANDOFF"
            session["human_handoff_requested_at"] = int(time.time())
            session["attendant_active_until"] = int(time.time()) + ATTENDANT_TTL_SECONDS

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
                session["state"] = "HUMAN_HANDOFF"
                session["human_handoff_requested_at"] = int(time.time())
                session["attendant_active_until"] = int(time.time()) + ATTENDANT_TTL_SECONDS
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

        outgoing = self._build_outgoing(final_text, pending_buttons)

        # 8. Save history (truncated)
        session["agent_history"] = self._truncate_history(limpar_gatilhos(history))
        session["mode"] = "agent"
        # Guarda o que a conversa INTEIRA consultou, não só esta rodada: a
        # pessoa negocia data por vários turnos e o bot repete o mesmo fato
        # consultado. Cortado nos últimos RESPALDO_GUARDADO porque a sessão vive
        # no DynamoDB (limite de 400KB por item) e resultado de tool cresce
        # rápido - list_areas de uma clínica grande já são alguns KB.
        session["respaldo_anterior"] = self._convert_decimals(
            respaldo_das_tools[-RESPALDO_GUARDADO:]
        )
        self._save_session(clinic_id, phone, session)

        elapsed = time.time() - start_time
        logger.info(f"[ConversationAgent] Processed message for {phone} in {elapsed:.2f}s, {len(outgoing)} outgoing messages")

        return outgoing

    # ── System prompt ──

    def _build_system_prompt(self, clinic_id, phone):
        """Build the system prompt with clinic context."""
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
            "1. Toda dúvida sobre o procedimento começa com get_faq_answer. Você não tem\n"
            "   a base de conhecimento na memória: ela vem da tool, e só de lá.\n"
            "2. Responda com o que a tool devolveu. Pode resumir e adaptar o tom, nunca\n"
            "   acrescentar informação que não veio nela.\n"
            "3. Se get_faq_answer não devolver resposta, você NÃO SABE. Não complete com\n"
            "   conhecimento geral sobre depilação a laser, por mais seguro que pareça:\n"
            "   diga que vai confirmar com uma especialista e chame request_human_handoff.\n"
            "4. Isso vale mesmo para o que parece óbvio - intervalo entre sessões, número\n"
            "   de sessões, cuidados, contraindicações. Cada clínica tem o seu protocolo.\n"
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
            "\n═══ INSTRUÇÕES PÓS-AGENDAMENTO ═══\n"
            "Após confirmar um agendamento com book_appointment, SEMPRE chame "
            "get_pre_session_instructions para obter as instruções de cuidados pré-sessão. "
            "Se houver instruções, envie-as ao cliente."
        )

        return system_prompt

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

    def _build_outgoing(self, text, pending_buttons):
        """Convert agent output into OutgoingMessage list."""
        messages = []

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

    def _is_attendant_active(self, session):
        """Check if human attendant mode is active (TTL-based)."""
        active_until = session.get("attendant_active_until")
        if active_until and int(active_until) > int(time.time()):
            return True
        state = session.get("state")
        if state == "HUMAN_ATTENDANT_ACTIVE":
            # TTL expired — clear state
            session.pop("attendant_active_until", None)
            session["state"] = ""
        return False

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
