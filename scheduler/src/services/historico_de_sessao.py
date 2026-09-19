# -*- coding: utf-8 -*-
"""O registro do que a profissional fez em cada sessão.

O que a clínica tinha até 19/09/2026: `appointments`, que guarda o que foi
MARCADO. O que foi FEITO - qual fluência, em que área, com que método - saía da
sala na memória de quem aplicou.

A pergunta que este módulo existe para responder em um clique é *"que parâmetro
eu usei na virilha da Maria da última vez?"*. Por isso as aplicações são uma
tabela, com colunas, e não um campo de texto: a resposta tem de ser um `WHERE`.

Preencher tem de ser quase automático. O registro nasce do agendamento daquele
dia - as áreas já estão lá - e cada área traz o parâmetro inicial do protocolo,
conforme o tipo de pele da paciente. Ela confere e salva. Ver [protocolo_laser].

Três coisas que não se negociam aqui:

  - **`area_name` é snapshot.** Renomear a área no catálogo não reescreve o
    passado. Mesmo padrão de `appointment_service_areas`, e a mesma razão pela
    qual renomeamos três áreas em prod sem tocar em nenhum agendamento antigo.

  - **Os VALORES são gravados, não uma referência ao protocolo.** Ajustar a
    tabela de protocolos daqui a um ano não pode alterar uma sessão de hoje.

  - **A trilha guarda o estado completo.** O André escolheu "edita, e o anterior
    fica guardado". Snapshot e não diff: diff parece econômico e depois não
    reconstitui nada sozinho.

O bot não chega aqui. Nenhuma tool do agente lê ou escreve estas tabelas.
"""
import json
import logging
from typing import Dict, List, Optional, Sequence

from src.services.protocolo_laser import (
    campos_do_metodo,
    metodos_disponiveis,
    sugestao,
)

logger = logging.getLogger(__name__)

ACOES = ("CREATE", "UPDATE", "DELETE")

# Todos os campos numéricos possíveis. O que não pertence ao método é gravado
# como NULL - ver `valida_aplicacoes`.
CAMPOS_NUMERICOS = ("fluence_j", "energy_kj", "stacks", "passes")


class RegistroInvalido(ValueError):
    """O que a tela mandou não dá para gravar.

    ValueError de propósito: os handlers transformam em 400. Formulário
    malpreenchido não é falha do servidor.
    """


def _num(valor):
    if valor is None or valor == "":
        return None
    try:
        return float(valor)
    except (TypeError, ValueError):
        raise RegistroInvalido(f"Valor numérico inválido: {valor!r}")


def aplicacoes_do_agendamento(db, appointment_id: str,
                              skin_type: Optional[str]) -> List[Dict]:
    """As aplicações com que o registro nasce, vindas do agendamento.

    Cada área do agendamento é expandida pelo mapa: a composta `Virilha Completa
    + ânus` vira DUAS aplicações, virilha no SHR e perianal no Stacking, que é o
    que a profissional de fato aplica.

    Área sem mapa entra assim mesmo, com o nome preenchido e os parâmetros
    vazios. "Sem parâmetro sugerido" é resposta válida; inventar não é.
    """
    areas = db.execute_query(
        """
        SELECT asa.area_id, asa.area_name,
               COALESCE(m.protocol_area_key, NULL) AS protocol_area_key,
               COALESCE(m.display_order, 0) AS map_order,
               asa.created_at
        FROM scheduler.appointment_service_areas asa
        LEFT JOIN scheduler.area_protocol_map m ON m.area_id = asa.area_id
        WHERE asa.appointment_id = %s::uuid
        ORDER BY asa.created_at, m.display_order
        """,
        (appointment_id,),
    ) or []

    saida = []
    for linha in areas:
        chave = linha.get("protocol_area_key")
        metodos = metodos_disponiveis(chave) if chave else []
        # Um método só: a tela já deixa escolhido. Mais de um (Buço tem Stacking
        # e HR) fica em branco - escolher por ela seria decidir conduta.
        metodo = metodos[0] if len(metodos) == 1 else None
        sugerido = sugestao(chave, metodo, skin_type) if (chave and metodo) else None

        saida.append({
            "area_id": str(linha["area_id"]) if linha.get("area_id") else None,
            "area_name": linha["area_name"],
            "protocol_area_key": chave,
            "method": metodo,
            "fluence_j": sugerido["fluence_j"] if sugerido else None,
            "energy_kj": sugerido["energy_kj"] if sugerido else None,
            "stacks": sugerido["stacks"] if sugerido else None,
            "passes": sugerido["passes"] if sugerido else None,
            "display_order": len(saida),
        })
    return saida


def valida_aplicacoes(aplicacoes: Sequence[Dict]) -> List[Dict]:
    """Normaliza as aplicações e recusa o que não faz sentido.

    O filtro por método não é preciosismo: gravar `stacks` num SHR sujaria a
    consulta que justifica a tabela existir. Se a tela mandar campo que o método
    não usa, é sinal de tela desatualizada, e o valor vira NULL em vez de virar
    dado.
    """
    limpas = []
    for i, ap in enumerate(aplicacoes or []):
        if not isinstance(ap, dict):
            raise RegistroInvalido("Aplicação em formato inesperado.")

        nome = (ap.get("area_name") or "").strip()
        if not nome:
            # É o snapshot que sobrevive ao catálogo. Sem ele o histórico não
            # diz o que foi tratado.
            raise RegistroInvalido("Toda aplicação precisa do nome da área.")

        metodo = ap.get("method") or None
        if metodo and not campos_do_metodo(metodo):
            raise RegistroInvalido(f"Método desconhecido: {metodo!r}")

        permitidos = set(campos_do_metodo(metodo)) if metodo else set()
        valores = {}
        for campo in CAMPOS_NUMERICOS:
            bruto = _num(ap.get(campo))
            if bruto is not None and campo not in permitidos:
                logger.info(
                    f"[Prontuario] descartando {campo}={bruto} numa aplicação "
                    f"de método {metodo!r}: o método não usa este campo"
                )
                bruto = None
            if bruto is not None and bruto <= 0:
                raise RegistroInvalido(
                    f"{campo} precisa ser maior que zero (recebido: {bruto})."
                )
            valores[campo] = bruto

        limpas.append({
            "area_id": ap.get("area_id") or None,
            "area_name": nome[:160],
            "protocol_area_key": ap.get("protocol_area_key") or None,
            "method": metodo,
            "display_order": ap.get("display_order", i),
            **valores,
        })
    return limpas


def estado_do_registro(db, record_id: str) -> Dict:
    """O registro e suas aplicações, como estão agora. É o que vai na trilha."""
    linhas = db.execute_query(
        "SELECT * FROM scheduler.patient_session_records WHERE id = %s::uuid",
        (record_id,),
    )
    if not linhas:
        return {}
    registro = dict(linhas[0])

    aplicacoes = db.execute_query(
        """SELECT area_id, area_name, protocol_area_key, method,
                  fluence_j, energy_kj, stacks, passes, display_order
           FROM scheduler.patient_session_applications
           WHERE record_id = %s::uuid ORDER BY display_order""",
        (record_id,),
    ) or []
    registro["applications"] = [dict(a) for a in aplicacoes]
    return registro


def grava_trilha(db, record_id: str, clinic_id: str, action: str,
                 estado: Dict, por: Optional[str] = None) -> None:
    """Um append por escrita, com o estado COMPLETO depois da mudança.

    Nunca levanta para fora: falhar a trilha não pode impedir a profissional de
    registrar o atendimento. Mas loga ERROR, porque uma trilha que para de
    receber é um defeito silencioso - e defeito silencioso em prontuário é
    exatamente o que não se pode ter.
    """
    if action not in ACOES:
        raise RegistroInvalido(f"Ação desconhecida na trilha: {action!r}")
    try:
        db.execute_write(
            """INSERT INTO scheduler.patient_session_record_audit
               (record_id, clinic_id, action, snapshot, changed_by_name)
               VALUES (%s::uuid, %s, %s, %s::jsonb, %s)""",
            (record_id, clinic_id, action,
             json.dumps(estado, ensure_ascii=False, default=str), por),
        )
    except Exception as e:
        logger.error(
            f"[Prontuario] FALHA ao gravar a trilha de {record_id} ({action}): {e}. "
            f"O registro foi salvo, mas esta alteração não tem histórico."
        )
