# -*- coding: utf-8 -*-
"""EVALUATION: o agente inteiro, contra conversas reais, com nota comparavel.

Por que existe
--------------
Todo buraco encontrado em 02-03/09/2026 apareceu porque alguem mandou mensagem
no WhatsApp e leu log depois. Quatro vezes seguidas: agendamento cancelado dado
como confirmado, duracao inventada, horarios da tarde inventados, horarios da
manha inventados. Testes unitarios passavam em todas.

Isso e o oposto de regressao detectavel. O eval troca "testei no WhatsApp" por
um numero que da para comparar entre execucoes.

O que ele faz
-------------
Replaya conversas REAIS (tests/evaluation/corpus/conversas.json) pelo agente de
verdade, com as tools mockadas e o modelo real. Tools mockadas porque o que esta
sob teste e a decisao do agente, nao o banco; modelo real porque a decisao E do
modelo - mockar o modelo mediria o mock.

Invariantes
-----------
  I1  agenda sem respaldo   data ou horario que nenhuma tool devolveu
  I2  fato sem consulta     afirmacao factual com zero tools na rodada
  I3  bloqueio disparado    o guardrail derrubou a resposta (custo da rede)
  I4  fuga pela saida       sem_consulta_necessaria numa pergunta factual

I1 e I2 sao defeito. I3 e I4 sao CUSTO: I3 alto significa guardrail salvando
demais (modelo ruim ou prompt fraco), I4 alto significa que a saida virou
desculpa. Nenhum dos quatro deve piorar quando o prompt encolher ou o modelo
ficar mais barato - e para isso que a nota existe.

Uso
---
    python -X utf8 tests/evaluation/eval_fluxo_agente.py --nome baseline
    python -X utf8 tests/evaluation/eval_fluxo_agente.py --nome haiku --conversas 10
    python -X utf8 tests/evaluation/eval_fluxo_agente.py --comparar baseline haiku

Custa dinheiro: uma execucao completa sao ~226 turnos x 2-4 chamadas de modelo.
Comece com --conversas 5 para conferir a mecanica.
"""
import argparse
import json
import os
import sys
import time
from collections import Counter

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, RAIZ)

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "eval-sem-dynamo")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "eval-sem-dynamo")

from tests.evaluation.corpus_conversas import carrega  # noqa: E402
from src.providers.whatsapp_provider import IncomingMessage  # noqa: E402
from src.services.conversation_agent import RESPALDO_GUARDADO, ConversationAgent  # noqa: E402
from src.services.proveniencia import fatos_de_agenda, fatos_sem_origem, fatos_sensiveis  # noqa: E402

RESULTADOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resultados")

# ── Tools mockadas ───────────────────────────────────────────────────────
# Os formatos sao os que as tools de verdade devolvem. Formato inventado aqui
# faria o eval aprovar um agente que quebra em producao - foi exatamente esse o
# erro que fez um teste passar sem provar nada em 02/09.
SERVICO = "e5c550d6-6deb-434b-b42d-13137af071a8"

FIXTURES = {
    "list_services": {
        "services": [{"id": SERVICO, "name": "Depilação a Laser",
                      "duration_minutes": 15, "price_cents": 6500}],
        "single_service": True,
    },
    "list_areas": {"areas": [
        {"service_id": SERVICO, "area_id": "a-axilas", "service_name": "Depilação a Laser",
         "area_name": "Axilas", "price_display": "R$ 65.00", "price_cents": 6500},
        {"service_id": SERVICO, "area_id": "a-virilha", "service_name": "Depilação a Laser",
         "area_name": "Virilha Completa", "price_display": "R$ 120.00", "price_cents": 12000},
        {"service_id": SERVICO, "area_id": "a-buco", "service_name": "Depilação a Laser",
         "area_name": "Buço", "price_display": "R$ 65.00", "price_cents": 6500},
    ]},
    "check_availability": {"available_dates": [
        {"date": "2026-09-23", "label": "Quarta, 23 de setembro"},
        {"date": "2026-09-30", "label": "Quarta, 30 de setembro"},
    ]},
    "get_time_slots": {
        "date": "2026-09-23", "date_label": "Quarta, 23 de setembro",
        "available_slots": ["07:45", "09:15", "14:30", "18:00"],
    },
    "calculate_duration": {"total_duration_minutes": 20, "area_count": 2},
    "calculate_discount": {
        "discount_pct": 10, "discount_reason": "tier_2",
        "original_price_cents": 18500, "discounted_price_cents": 16650,
        "original_price_display": "R$ 185.00", "price_display": "R$ 166.50",
    },
    "lookup_appointments": {"appointments": []},
    "get_faq_answer": {"answers": [
        {"question": "Dói?", "answer": "O Soprano Ice tem ponteira de safira com "
         "resfriamento; a maioria descreve como morno e confortável."},
    ]},
    "get_clinic_info": {"name": "Clínica Essência", "address": "Rua Augusta, 2709"},
    "get_pre_session_instructions": {"instructions": "Não se expor ao sol por 48h."},
    "book_appointment": {
        "success": True, "appointment_id": "eval-0001", "date": "2026-09-23",
        "time": "07:45", "full_name": "Fulana", "total_duration_minutes": 20,
        "status": "CONFIRMED",
    },
    "sem_consulta_necessaria": {},
    "present_options": {"presented": False},
    "request_human_handoff": {"handoff_requested": True},
}

SEM_CONSULTA = "sem_consulta_necessaria"


class ToolsMockadas:
    def __init__(self):
        self.chamadas = []

    def execute(self, nome, args, context=None):
        self.chamadas.append(nome)
        return FIXTURES.get(nome, {"error": f"tool sem fixture no eval: {nome}"})


def garante_chave():
    """Busca ANTHROPIC_API_KEY no SSM quando nao esta no ambiente.

    Sem isso o eval roda inteiro contra 401 e so descobre no fim. Erra cedo e
    com a causa nomeada em vez de tarde e com nota invalida.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    try:
        import boto3
        ssm = boto3.Session(profile_name="dev-andre", region_name="us-east-1").client("ssm")
        os.environ["ANTHROPIC_API_KEY"] = ssm.get_parameter(
            Name="/prod/ANTHROPIC_API_KEY", WithDecryption=True
        )["Parameter"]["Value"]
        print("[eval] chave lida do SSM (/prod/ANTHROPIC_API_KEY)")
    except Exception as e:
        raise SystemExit(
            f"ANTHROPIC_API_KEY ausente e o SSM falhou: {e}\n"
            "Exporte a chave ou confira o perfil AWS antes de rodar o eval."
        )


class AnthropicMedido:
    """O cliente real, com contabilidade de tokens e chamadas por volta."""

    def __init__(self):
        garante_chave()
        from src.services.anthropic_service import AnthropicService
        self._real = AnthropicService()
        self.chamadas = 0
        self.erros = 0
        self.primeiro_erro = None
        self.tokens_in = 0
        self.tokens_out = 0
        self.tokens_cache_read = 0

    def create_message(self, system, messages, tools, max_tokens, tool_choice=None):
        self.chamadas += 1
        try:
            r = self._real.create_message(
                system=system, messages=messages, tools=tools,
                max_tokens=max_tokens, tool_choice=tool_choice,
            )
        except Exception as e:
            # Contado, nao engolido. O agente trata AnthropicError internamente e
            # devolve "estou com dificuldades" - do lado de fora isso parece um
            # turno normal, e o eval reportaria zero violacao por nao ter medido
            # nada. Eval que da verde sem medir e pior que eval nenhum.
            self.erros += 1
            if self.primeiro_erro is None:
                self.primeiro_erro = str(e)[:200]
            raise
        u = r.get("usage") or {}
        self.tokens_in += u.get("input_tokens", 0)
        self.tokens_out += u.get("output_tokens", 0)
        self.tokens_cache_read += u.get("cache_read_input_tokens", 0)
        return r


class DbFalso:
    """O agente toca o banco para montar o prompt. Aqui isso e fixture.

    O system prompt NAO e fixture: vem do prompt sob teste. Sem isso o
    TemplateService cai em DEFAULT_TEMPLATES - 6.115 chars de um texto que nao
    esta em producao - e o eval mede um agente que ninguem deploya.
    """

    def __init__(self, prompt):
        self._prompt = prompt

    def execute_query(self, query, params=None):
        q = query.lower()
        if "message_templates" in q:
            return [{"template_key": "AI_SYSTEM_PROMPT",
                     "content": self._prompt, "buttons": None}]
        if "from scheduler.clinics" in q:
            return [{"clinic_id": "eval", "name": "Clínica Essência",
                     "display_name": "Clínica Essência", "phone": "+5511999999999",
                     "address": "Rua Augusta, 2709", "use_agent": True}]
        if "from scheduler.services" in q:
            return [{"id": SERVICO, "name": "Depilação a Laser"}]
        if "discount_rules" in q:
            return [{"first_session_discount_pct": 0, "tier_2_min_areas": 2,
                     "tier_2_max_areas": 4, "tier_2_discount_pct": 10,
                     "tier_3_min_areas": 5, "tier_3_discount_pct": 15,
                     "is_active": True}]
        if "faq_items" in q:
            return []
        return []

    def execute_write(self, *a, **k):
        return 1


def carrega_prompt(caminho=None):
    """O prompt sob teste: de um arquivo, ou o que esta em producao.

    O arquivo permite medir uma versao ANTES de grava-la no banco - medir
    primeiro, aplicar depois.
    """
    if caminho:
        with open(caminho, encoding="utf-8") as f:
            return f.read()

    import boto3
    from src.services.db.postgres import PostgresService

    sessao = boto3.Session(profile_name="dev-andre", region_name="us-east-1")
    ssm = sessao.client("ssm")
    for env, param in [("RDS_HOST", "SUPABASE_DB_HOST"), ("RDS_PORT", "SUPABASE_DB_PORT"),
                       ("RDS_DATABASE", "SUPABASE_DB_NAME"), ("RDS_USERNAME", "SUPABASE_DB_USER"),
                       ("RDS_PASSWORD", "SUPABASE_DB_PASSWORD")]:
        os.environ[env] = ssm.get_parameter(
            Name=f"/prod/{param}", WithDecryption=True)["Parameter"]["Value"]

    linhas = PostgresService().execute_query(
        "SELECT content FROM scheduler.message_templates "
        "WHERE clinic_id=%s AND template_key='AI_SYSTEM_PROMPT'",
        ("clinicaessenciaestetica-9668a4",))
    if not linhas:
        raise SystemExit("Prompt de producao nao encontrado no banco.")
    return linhas[0]["content"]


def monta_agente(anthropic, tools, prompt):
    """ConversationAgent real, sem AWS e sem Postgres.

    __init__ abre DynamoDB e o cliente HTTP, entao o objeto e criado direto e
    so o que o fluxo toca e preenchido. A sessao vive em memoria: cada conversa
    do corpus comeca limpa, como uma pessoa nova escrevendo.
    """
    agente = object.__new__(ConversationAgent)
    agente.db = DbFalso(prompt)
    agente.tool_executor = tools
    agente.anthropic = anthropic
    agente.sessao = {}
    agente._load_session = lambda c, p: agente.sessao
    agente._save_session = lambda c, p, s: agente.sessao.update(s)
    agente._is_attendant_active = lambda s: False
    # Sem MessageEvents: o corpus JA e a conversa, reconstruir duplicaria turnos.
    agente.rebuild_history_from_events = lambda c, p: []

    from src.services.template_service import TemplateService
    agente.template_service = TemplateService(agente.db)
    return agente


HANDOFF_PEDIDO = "request_human_handoff"


def avalia_turno(texto, tools_da_rodada, tools_da_conversa, estado_antes, estado_depois):
    """Os quatro invariantes, para uma resposta.

    I3 conta a TRANSICAO para HUMAN_HANDOFF, nao o estado: o estado fica na
    sessao, e medir o estado marcaria como bloqueio todos os turnos seguintes
    ao primeiro. Na primeira versao uma conversa com um bloqueio no turno 6
    contava 6 violacoes.

    E so conta bloqueio do GUARDRAIL: quando o proprio modelo chama
    request_human_handoff a transferencia e acerto dele, nao custo da rede.
    """
    # I1 confere contra a MESMA janela que o agente usa (RESPALDO_GUARDADO
    # resultados carregados pela sessao), nao so contra a rodada. Medir uma
    # janela mais estrita que a de producao contava violacao onde o agente nao
    # bloquearia - a regua tem que ser a mesma coisa que o codigo faz.
    respaldo = [FIXTURES.get(n, {}) for n in tools_da_conversa[-RESPALDO_GUARDADO:]]
    sem_origem = fatos_sem_origem(texto, respaldo)

    consultou = [t for t in tools_da_rodada if t != SEM_CONSULTA]
    afirmou_fato = bool(fatos_sensiveis(texto))
    virou_handoff = estado_antes != "HUMAN_HANDOFF" and estado_depois == "HUMAN_HANDOFF"

    return {
        "I1_agenda_sem_respaldo": sorted(fatos_de_agenda(sem_origem)),
        "I2_fato_sem_consulta": afirmou_fato and not consultou,
        "I3_bloqueio": virou_handoff and HANDOFF_PEDIDO not in tools_da_rodada,
        "I4_fuga_pela_saida": SEM_CONSULTA in tools_da_rodada and afirmou_fato,
        "tools": consultou,
        "handoff_pedido_pelo_modelo": virou_handoff and HANDOFF_PEDIDO in tools_da_rodada,
    }


def roda(conversas, verboso, prompt):
    achados = []
    tipos = Counter()
    anthropic = AnthropicMedido()
    inicio = time.time()

    for c in conversas:
        tools = ToolsMockadas()
        agente = monta_agente(anthropic, tools, prompt)
        if verboso:
            print(f"\n=== {c['id']} ===")

        for n, texto_usuario in enumerate(c["turnos"]):
            antes = len(tools.chamadas)
            estado_antes = agente.sessao.get("state")
            entrada = IncomingMessage(
                message_id=f"{c['id']}-{n}", phone="5511900000000",
                sender_name="Eval", timestamp=0, message_type="TEXT",
                content=texto_usuario,
            )
            try:
                saida = agente.process_message("eval", entrada)
            except Exception as e:
                print(f"  [FALHA] {c['id']} turno {n}: {e}")
                tipos["falha_execucao"] += 1
                break

            resposta = " ".join(m.content for m in saida)
            v = avalia_turno(resposta, tools.chamadas[antes:], tools.chamadas,
                             estado_antes, agente.sessao.get("state"))
            if v["handoff_pedido_pelo_modelo"]:
                tipos["handoff_pedido_pelo_modelo"] += 1

            for chave in ("I1_agenda_sem_respaldo", "I2_fato_sem_consulta",
                          "I3_bloqueio", "I4_fuga_pela_saida"):
                if v[chave]:
                    tipos[chave] += 1
                    achados.append({"conversa": c["id"], "turno": n, "invariante": chave,
                                    "detalhe": v[chave], "pergunta": texto_usuario[:70],
                                    "resposta": resposta[:140]})
            tipos["turnos"] += 1
            tipos["tools_chamadas"] += len(v["tools"])

            if agente.sessao.get("state") == "HUMAN_HANDOFF":
                # Em producao o atendente assume aqui e o bot para de responder.
                break

            if verboso:
                marca = "".join(k[1] for k in ("I1_agenda_sem_respaldo", "I2_fato_sem_consulta",
                                               "I3_bloqueio", "I4_fuga_pela_saida") if v[k])
                print(f"  [{n}] {'!' + marca if marca else 'ok'} tools={v['tools']} "
                      f"| {texto_usuario[:45]!r}")

    return {
        "turnos": tipos["turnos"],
        "conversas": len(conversas),
        "violacoes": {k: tipos[k] for k in
                      ("I1_agenda_sem_respaldo", "I2_fato_sem_consulta",
                       "I3_bloqueio", "I4_fuga_pela_saida")},
        "falhas_execucao": tipos["falha_execucao"],
        "handoff_pedido_pelo_modelo": tipos["handoff_pedido_pelo_modelo"],
        "chamadas_modelo": anthropic.chamadas,
        "tools_chamadas": tipos["tools_chamadas"],
        "tokens_in": anthropic.tokens_in,
        "tokens_out": anthropic.tokens_out,
        "tokens_cache_read": anthropic.tokens_cache_read,
        "erros_de_api": anthropic.erros,
        "primeiro_erro": anthropic.primeiro_erro,
        "segundos": round(time.time() - inicio, 1),
        "prompt_chars": len(prompt),
        "achados": achados[:40],
    }


def imprime(nome, r):
    t = max(r["turnos"], 1)
    print(f"\n===== {nome} =====")
    print(f"conversas {r['conversas']} | turnos {t} | {r['segundos']}s "
          f"| prompt {r.get('prompt_chars', '?')} chars")
    print(f"chamadas de modelo {r['chamadas_modelo']} ({r['chamadas_modelo']/t:.2f}/turno)")
    print(f"tools              {r['tools_chamadas']} ({r['tools_chamadas']/t:.2f}/turno)")
    print(f"tokens in {r['tokens_in']} | cache_read {r['tokens_cache_read']} "
          f"| out {r['tokens_out']}")
    if r["tokens_in"]:
        pct = 100 * r["tokens_cache_read"] / (r["tokens_in"] + r["tokens_cache_read"])
        print(f"  aproveitamento de cache: {pct:.0f}% do input")
    print("violacoes:")
    for k, v in r["violacoes"].items():
        print(f"  {k:<26} {v:>4}  ({100*v/t:.0f}% dos turnos)")
    if r["falhas_execucao"]:
        print(f"  FALHAS DE EXECUCAO         {r['falhas_execucao']:>4}")


def nota_valida(r):
    """A execucao mediu alguma coisa?

    Sem esta checagem o eval da verde quando a API esta fora: o agente trata o
    erro, responde "estou com dificuldades", e zero violacao vira zero medicao
    disfarcada de aprovacao.
    """
    if r["erros_de_api"]:
        return False, (f"{r['erros_de_api']} de {r['chamadas_modelo']} chamadas de modelo "
                       f"falharam. Primeiro erro: {r['primeiro_erro']}")
    if not r["turnos"]:
        return False, "nenhum turno executado"
    if not r["tokens_in"] and not r["tokens_cache_read"]:
        return False, "zero token consumido - o modelo nao respondeu"
    return True, ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nome", default="run", help="rotulo do resultado gravado")
    ap.add_argument("--conversas", type=int, default=0, help="0 = todas")
    ap.add_argument("--verboso", action="store_true")
    ap.add_argument("--comparar", nargs=2, metavar=("A", "B"))
    ap.add_argument("--prompt-arquivo", help="mede este prompt em vez do de producao")
    args = ap.parse_args()

    if args.comparar:
        a, b = [json.load(open(os.path.join(RESULTADOS, f"{n}.json"), encoding="utf-8"))
                for n in args.comparar]
        imprime(args.comparar[0], a)
        imprime(args.comparar[1], b)
        print(f"\n===== {args.comparar[0]} -> {args.comparar[1]} =====")
        for k in a["violacoes"]:
            d = b["violacoes"][k] - a["violacoes"][k]
            print(f"  {k:<26} {d:+d}  {'PIOROU' if d > 0 else 'ok'}")
        for k in ("tokens_in", "tokens_out", "chamadas_modelo"):
            if a[k]:
                print(f"  {k:<26} {100*(b[k]-a[k])/a[k]:+.0f}%")
        return

    conversas = carrega()
    if args.conversas:
        conversas = conversas[:args.conversas]

    prompt = carrega_prompt(args.prompt_arquivo)
    print(f"[eval] prompt sob teste: {len(prompt)} chars "
          f"({args.prompt_arquivo or 'producao'})")
    r = roda(conversas, args.verboso, prompt)
    imprime(args.nome, r)

    valida, motivo = nota_valida(r)
    if not valida:
        print("\n*** NOTA INVALIDA - resultado NAO gravado ***")
        print(f"  {motivo}")
        sys.exit(1)

    os.makedirs(RESULTADOS, exist_ok=True)
    destino = os.path.join(RESULTADOS, f"{args.nome}.json")
    with open(destino, "w", encoding="utf-8", newline="") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    print(f"\ngravado: {destino}")

    if r["achados"]:
        print("\n--- primeiros achados ---")
        for a in r["achados"][:6]:
            print(f"  {a['conversa']}#{a['turno']} {a['invariante']} {a['detalhe']}")
            print(f"     P: {a['pergunta']!r}")
            print(f"     R: {a['resposta']!r}")


if __name__ == "__main__":
    main()
