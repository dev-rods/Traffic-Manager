# -*- coding: utf-8 -*-
"""EVAL dos casos do PRD 064, com o modelo real e o prompt/FAQ de producao.

Tres conversas sinteticas equivalentes aos casos de 24/11/2026 (sem nomes nem
numeros reais), com assercoes objetivas. Roda em ~2 minutos e custa centavos.

    python -X utf8 tests/evaluation/eval_064.py [--verboso] [--prompt-arquivo f]

Casos
-----
 1  "Ola, boa noite" + "Quanto e a depilacao na virilha?" (lead)
    - uma mensagem por turno; nenhuma bolha literal do FAQ
    - a resposta da virilha fala dos tipos (simples/cavada/completa) ou diz que
      depende do tipo, e pergunta qual
    - a saudacao e do periodo de AGORA (nao "boa noite" de dia)
 2  paciente cadastrada, clinica com site: "Podemos marcar dia 23/09 as 14:30?"
    - primeira resposta traz o link e NAO pergunta areas nem consulta agenda
    - "prefiro marcar por aqui, pode ser 23/09 as 14:30?": consulta a agenda
      (check_availability/get_time_slots) e nenhuma resposta traz o link
 3  depois de "Agendamento confirmado" do sistema: "Muito obrigada" -> uma
    despedida; "Ate" -> nenhuma mensagem
"""
import argparse
import json
import os
import sys
import time

RAIZ = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, RAIZ)
os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "eval-sem-dynamo")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "eval-sem-dynamo")

from tests.evaluation.eval_fluxo_agente import (  # noqa: E402
    RESULTADOS, AnthropicMedido, ToolsMockadas, carrega_faq, carrega_prompt, custo, monta_agente,
)
from src.providers.whatsapp_provider import IncomingMessage  # noqa: E402
from src.services import relogio, saudacao  # noqa: E402

LINK = "https://agendar.clinica-eval.com.br/"
PACIENTE = {"encontrado": True, "nome": "Paciente Eval", "cadastro_completo": True,
            "sessoes_feitas": 0, "ultima_sessao": None, "agendamento_futuro": None}


def _msg(texto, n):
    return IncomingMessage(message_id=f"064-{n}", phone="5511900000000", sender_name="Eval",
                           timestamp=0, message_type="TEXT", content=texto)


def _evento(direction, content, ha_segundos=60, autor=None):
    quando = time.gmtime(time.time() - ha_segundos)
    e = {"direction": direction, "content": content,
         "sk": f"MSG#{time.strftime('%Y-%m-%dT%H:%M:%S', quando)}Z#x"}
    if autor:
        e["metadata"] = {"autor": autor}
    return e


def caso_1(anthropic, prompt, faq, verboso):
    tools = ToolsMockadas(faq=faq)
    agente = monta_agente(anthropic, tools, prompt, faq=faq)
    respostas_do_faq = {i["answer"] for i in faq}
    periodo = saudacao.periodo(relogio.agora_na_clinica("America/Sao_Paulo"))
    falhas = []

    s1 = agente.process_message("eval", _msg("Ola, boa noite", 1))
    t1 = " ".join(m.content for m in s1)
    if verboso:
        print("  [1a]", t1[:300].replace("\n", " / "))
    if len(s1) != 1:
        falhas.append(f"turno 1: {len(s1)} mensagens (esperado 1)")
    if saudacao.saudacao_errada(t1, periodo):
        falhas.append(f"turno 1: saudacao fora do periodo '{periodo}': {t1[:60]!r}")

    antes = len(tools.chamadas)
    s2 = agente.process_message("eval", _msg("Quanto é a depilação na virilha?", 2))
    t2 = " ".join(m.content for m in s2).lower()
    if verboso:
        print("  [1b]", t2[:400].replace("\n", " / "), "| tools:", tools.chamadas[antes:])
    if any(m.content in respostas_do_faq for m in s2):
        falhas.append("turno 2: saiu bolha literal do FAQ")
    if len(s2) > 1:
        falhas.append(f"turno 2: {len(s2)} mensagens (esperado 1)")
    fala_dos_tipos = ("simples" in t2 and "completa" in t2) or "depende do tipo" in t2 or "qual tipo" in t2
    if not fala_dos_tipos:
        falhas.append("turno 2: nao falou dos tipos de virilha nem disse que depende do tipo")
    if "?" not in t2:
        falhas.append("turno 2: nao devolveu pergunta (qual tipo / incluir perianal)")
    return falhas


def caso_2(anthropic, prompt, faq, verboso):
    tools = ToolsMockadas(faq=faq)
    agente = monta_agente(anthropic, tools, prompt, faq=faq, paciente=PACIENTE,
                          clinic_extra={"custom_domain": "agendar.clinica-eval.com.br"})
    falhas = []
    antes = len(tools.chamadas)
    s1 = agente.process_message("eval", _msg("Olá! Podemos marcar dia 23/09 às 14:30?", 1))
    t1 = " ".join(m.content for m in s1)
    if verboso:
        print("  [2a]", t1[:300].replace("\n", " / "), "| tools:", tools.chamadas[antes:])
    if "agendar.clinica-eval" not in t1:
        falhas.append("turno 1: resposta sem o link")
    if "áreas" in t1.lower() or "areas" in t1.lower():
        falhas.append("turno 1: perguntou areas")
    if any(t in tools.chamadas[antes:] for t in ("check_availability", "get_time_slots", "book_appointment")):
        falhas.append(f"turno 1: consultou agenda ({tools.chamadas[antes:]})")
    if "pedir_esclarecimento" in tools.chamadas[antes:] or "o que você quer fazer" in t1.lower():
        falhas.append("turno 1: pediu esclarecimento em vez de mandar o link")

    antes = len(tools.chamadas)
    s2 = agente.process_message("eval", _msg("Prefiro marcar por aqui. Pode ser dia 23/09 às 14:30? Axilas e buço.", 2))
    t2 = " ".join(m.content for m in s2)
    if verboso:
        print("  [2b]", t2[:300].replace("\n", " / "), "| tools:", tools.chamadas[antes:])
    if "agendar.clinica-eval" in t2:
        falhas.append("turno 2: mandou o link de novo")
    if not any(t in tools.chamadas[antes:] for t in ("check_availability", "get_time_slots", "list_areas", "calculate_discount", "book_appointment")):
        falhas.append(f"turno 2: nao seguiu para a agenda ({tools.chamadas[antes:]})")
    return falhas


def caso_3(anthropic, prompt, faq, verboso):
    tools = ToolsMockadas(faq=faq)
    eventos = []
    agente = monta_agente(anthropic, tools, prompt, faq=faq, paciente=dict(PACIENTE, sessoes_feitas=2),
                          eventos=lambda: eventos)
    falhas = []
    eventos.append(_evento("OUTBOUND", "Agendamento confirmado para *Paciente Eval*! Te esperamos no dia 23/09 às 14:30.", 120, autor="SISTEMA"))
    s1 = agente.process_message("eval", _msg("Muito obrigada 😊", 1))
    t1 = " ".join(m.content for m in s1)
    if verboso:
        print("  [3a]", t1[:200].replace("\n", " / "))
    if len(s1) != 1:
        falhas.append(f"turno 1: {len(s1)} mensagens (esperado 1 despedida)")
    if "?" in t1:
        falhas.append("turno 1: despediu-se com pergunta")
    eventos.append(_evento("INBOUND", "Muito obrigada 😊", 70))
    eventos.append(_evento("OUTBOUND", t1 or "Por nada! Até lá 💛", 60))

    chamadas_antes = anthropic.chamadas
    s2 = agente.process_message("eval", _msg("Até 🙂", 2))
    if verboso:
        print("  [3b]", [m.content for m in s2], "| chamadas de modelo:", anthropic.chamadas - chamadas_antes)
    if s2:
        falhas.append(f"turno 2: respondeu a despedida: {[m.content[:60] for m in s2]}")
    return falhas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verboso", action="store_true")
    ap.add_argument("--prompt-arquivo")
    args = ap.parse_args()

    prompt = carrega_prompt(args.prompt_arquivo)
    faq = carrega_faq()
    print(f"[eval 064] prompt {len(prompt)} chars | FAQ {len(faq)} itens")
    anthropic = AnthropicMedido()
    inicio = time.time()
    resultado = {}
    for nome, fn in (("caso_1_virilha", caso_1), ("caso_2_link", caso_2), ("caso_3_despedida", caso_3)):
        print(f"\n== {nome}")
        try:
            falhas = fn(anthropic, prompt, faq, args.verboso)
        except Exception as e:  # noqa: BLE001
            falhas = [f"EXCECAO: {e!r}"]
        resultado[nome] = falhas
        print("  PASS" if not falhas else "  FAIL\n   - " + "\n   - ".join(falhas))

    r = {"casos": resultado, "chamadas_modelo": anthropic.chamadas, "erros_de_api": anthropic.erros,
         "tokens_in": anthropic.tokens_in, "tokens_out": anthropic.tokens_out,
         "tokens_cache_read": anthropic.tokens_cache_read, "tokens_cache_write": anthropic.tokens_cache_write,
         "segundos": round(time.time() - inicio, 1), "modelo": "claude-sonnet-5"}
    print(f"\nchamadas {r['chamadas_modelo']} | erros {r['erros_de_api']} | {r['segundos']}s | custo US$ {custo(r):.2f}")
    os.makedirs(RESULTADOS, exist_ok=True)
    with open(os.path.join(RESULTADOS, "casos-064.json"), "w", encoding="utf-8", newline="") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
    sys.exit(1 if any(resultado.values()) or anthropic.erros else 0)


if __name__ == "__main__":
    main()
