# -*- coding: utf-8 -*-
"""O que os handlers de prontuário compartilham.

Existe porque gravar aplicação acontece em dois caminhos - criar e editar - e a
regra de "apaga e regrava na ordem que a tela mandou" precisa ser a mesma nos
dois. Duplicada, ela diverge no primeiro ajuste, e a divergência aqui aparece
como parâmetro sumido no histórico de uma paciente.
"""
import logging
from datetime import date, datetime, time
from decimal import Decimal

logger = logging.getLogger(__name__)


def serializa(row):
    """Linha do banco em algo que vira JSON.

    Decimal entra na conta porque fluência e energia são NUMERIC: sem isto o
    handler estoura com "Object of type Decimal is not JSON serializable" bem no
    meio do atendimento.
    """
    saida = {}
    for chave, valor in dict(row).items():
        if isinstance(valor, (datetime, date, time)):
            saida[chave] = valor.isoformat()
        elif isinstance(valor, Decimal):
            # float e não str: a tela faz conta e compara com o protocolo.
            saida[chave] = float(valor)
        elif hasattr(valor, "hex") and valor.__class__.__name__ == "UUID":
            saida[chave] = str(valor)
        else:
            saida[chave] = valor
    return saida


def grava_aplicacoes(db, record_id, aplicacoes):
    """Substitui as aplicações do registro pelas que vieram da tela.

    Apaga e regrava em vez de casar linha a linha: a tela manda a lista inteira,
    e tentar diferenciar por id abriria caminho para linha órfã quando ela
    remove uma área e adiciona outra na mesma edição.
    """
    db.execute_write(
        "DELETE FROM scheduler.patient_session_applications WHERE record_id = %s::uuid",
        (record_id,),
    )
    for ordem, ap in enumerate(aplicacoes or []):
        db.execute_write(
            """INSERT INTO scheduler.patient_session_applications
               (record_id, area_id, area_name, protocol_area_key, method,
                fluence_j, energy_kj, stacks, passes, display_order)
               VALUES (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (record_id, ap.get("area_id"), ap["area_name"],
             ap.get("protocol_area_key"), ap.get("method"),
             ap.get("fluence_j"), ap.get("energy_kj"),
             ap.get("stacks"), ap.get("passes"), ordem),
        )


def registro_com_aplicacoes(db, record_id):
    """O registro pronto para a tela: cabeçalho + aplicações + selo de editado."""
    linhas = db.execute_query(
        """SELECT r.*, p.name AS professional_name
           FROM scheduler.patient_session_records r
           LEFT JOIN scheduler.professionals p ON p.id = r.professional_id
           WHERE r.id = %s::uuid""",
        (record_id,),
    )
    if not linhas:
        return None

    registro = serializa(linhas[0])
    registro["applications"] = [
        serializa(a) for a in (db.execute_query(
            """SELECT * FROM scheduler.patient_session_applications
               WHERE record_id = %s::uuid ORDER BY display_order""",
            (record_id,),
        ) or [])
    ]
    # O selo "editado" na lista sai daqui: contar na tela exigiria uma chamada
    # por registro só para desenhar uma palavra.
    edicoes = db.execute_query(
        """SELECT COUNT(*) AS n FROM scheduler.patient_session_record_audit
           WHERE record_id = %s::uuid AND action = 'UPDATE'""",
        (record_id,),
    )
    registro["edit_count"] = int(edicoes[0]["n"]) if edicoes else 0
    return registro


def tipo_de_pele(db, patient_id):
    """O tipo de pele da paciente, ou None.

    None é normal: quem nunca foi marcada não tem, e aí não há sugestão. A tela
    pede, não chuta.
    """
    linhas = db.execute_query(
        "SELECT skin_type FROM scheduler.patients WHERE id = %s::uuid",
        (patient_id,),
    )
    return linhas[0]["skin_type"] if linhas else None
