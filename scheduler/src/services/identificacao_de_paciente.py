# -*- coding: utf-8 -*-
"""Quem está do outro lado da conversa, antes de o modelo escrever.

Nenhuma das 16 tools do agente identificava a pessoa. A única leitura de
`patients` era a data de nascimento para calcular idade. O contrato de
`book_appointment` exigia nome completo sempre, e o roteiro do prompt pedia
"Nome completo, Data de nascimento, CPF, E-mail" no passo 6 - para todo mundo.
Em 05/10/2026 a Yasmin, cadastrada com os quatro dados e tendo acabado de
marcar, recebeu esse pedido.

Não era falha do prompt. Era a ferramenta pedindo o que já estava no banco, e
nada dizendo ao modelo que estava. Aqui entra a identificação, e ela alimenta
três coisas:

  1. a tool `identificar_paciente`, pré-carregada nas intenções de agendamento;
  2. o prompt, que perde o passo de cadastro quando o cadastro está completo
     (RETIRADO, não contradito - ver prompt_da_campanha para a lição);
  3. a trava de saída, que recusa pedir cadastro a quem já o tem.

O que NÃO sai daqui: áreas tratadas, CPF, e-mail, nascimento. O bot não precisa
ver o dado para saber que ele existe, e as áreas são sempre perguntadas
(test_areas_sempre_perguntadas). PRD 020 §7.
"""
import logging
import re
from typing import Dict, List, Optional

from src.utils.phone import variantes_do_numero

logger = logging.getLogger(__name__)

# Os quatro que o roteiro pedia. É a régua de "cadastro completo": faltando
# qualquer um, o bot ainda tem o que perguntar, e o passo fica no prompt.
CAMPOS_DO_CADASTRO = ("name", "birth_date", "cpf", "email")


def cadastro_completo(paciente: Optional[Dict]) -> bool:
    """Os quatro campos do cadastro estão preenchidos?"""
    paciente = paciente or {}
    return all(_preenchido(paciente.get(campo)) for campo in CAMPOS_DO_CADASTRO)


def _preenchido(valor) -> bool:
    if valor is None:
        return False
    if isinstance(valor, str):
        return bool(valor.strip())
    return True


def identificar(db, clinic_id: str, phone: str) -> Dict:
    """O paciente deste telefone, com o que o bot pode saber dele.

    Casa pelas variantes do número (com e sem o nono dígito): o WhatsApp e o
    cadastro nem sempre gravam igual, e casar exato deixaria a paciente
    cadastrada passar por lead nova - que é o bug de origem com outra cara.

    Mais de um paciente nas variantes é AMBÍGUO, e ambíguo não é identificado:
    a trava de cadastro recusaria pedir o nome, e o agendamento sairia em nome
    da pessoa errada. Nesse caso devolve os candidatos e deixa o modelo
    perguntar.

    Nunca levanta: sem identificação o fluxo é o de antes, que pede cadastro.
    """
    try:
        variantes = sorted(variantes_do_numero(phone))
        linhas = db.execute_query(
            """
            SELECT p.id, p.name, p.birth_date, p.cpf, p.email,
                   (SELECT COUNT(*) FROM scheduler.appointments a
                     WHERE a.patient_id = p.id AND a.status = 'CONFIRMED'
                       AND a.appointment_date < CURRENT_DATE) AS sessoes_feitas,
                   (SELECT MAX(a.appointment_date) FROM scheduler.appointments a
                     WHERE a.patient_id = p.id AND a.status = 'CONFIRMED'
                       AND a.appointment_date < CURRENT_DATE) AS ultima_sessao,
                   (SELECT json_build_object(
                           'id', a.id::text, 'data', a.appointment_date::text,
                           'hora', to_char(a.start_time, 'HH24:MI'))
                      FROM scheduler.appointments a
                     WHERE a.patient_id = p.id AND a.status = 'CONFIRMED'
                       AND a.appointment_date >= CURRENT_DATE
                     ORDER BY a.appointment_date, a.start_time LIMIT 1) AS agendamento_futuro
            FROM scheduler.patients p
            WHERE p.clinic_id = %s AND p.phone = ANY(%s) AND p.deleted_at IS NULL
            ORDER BY p.created_at
            """,
            (clinic_id, variantes),
        )
    except Exception as e:
        logger.error(f"[Identificacao] Falha ao identificar {phone}: {e}")
        return {"encontrado": False}

    return a_partir_das_linhas(linhas, phone)


def a_partir_das_linhas(linhas: List[Dict], phone: str = "") -> Dict:
    """Pura: traduz as linhas do banco no que o modelo recebe."""
    if not linhas:
        return {"encontrado": False}

    if len(linhas) > 1:
        nomes = [l.get("name") or "(sem nome)" for l in linhas]
        logger.warning(
            f"[Identificacao] {phone} casa {len(linhas)} pacientes: {nomes}; "
            f"não identificando"
        )
        return {
            "encontrado": False,
            "ambiguo": True,
            "candidatos": nomes,
            "o_que_fazer": (
                "Este telefone está em mais de um cadastro. Pergunte o nome "
                "completo da pessoa antes de agendar."
            ),
        }

    p = linhas[0]
    return {
        "encontrado": True,
        "patient_id": str(p.get("id") or ""),
        "nome": p.get("name") or "",
        "cadastro_completo": cadastro_completo(p),
        "sessoes_feitas": int(p.get("sessoes_feitas") or 0),
        "ultima_sessao": str(p["ultima_sessao"]) if p.get("ultima_sessao") else None,
        "agendamento_futuro": p.get("agendamento_futuro") or None,
    }


# -- O prompt sem o passo de cadastro -------------------------------------
#
# Mesmo desenho de prompt_da_campanha.adapta: o roteiro numerado com texto
# pronto é o que o modelo reproduz palavra por palavra. "NUNCA peça CPF" colado
# no fim não vence "6. CADASTRO ... 'Perfeito! Para finalizar o cadastro'".
# Então o passo é substituído, e as frases que mandam passar cadastro para a
# tool são retiradas.

_CABECALHO = chr(0x2550) * 3
_SECAO = "COMO CONDUZIR A CONVERSA"
_PASSO = re.compile(r"^(\d+)\. CADASTRO\s*$", re.MULTILINE)
_PROXIMO_PASSO = re.compile(r"^\d+\. ", re.MULTILINE)
_FRASE_DE_CADASTRO = "dados de cadastro"


def sem_passo_de_cadastro(prompt: str, nome: str) -> str:
    """O prompt de quem já tem cadastro: o passo some, o nome entra.

    Tolerante a template editado pela clínica: sem a seção ou sem o passo, o
    prompt volta como veio - a trava de saída continua valendo.
    """
    if not prompt:
        return prompt

    # Mesma delimitacao de prompt_da_campanha: a secao vai do seu cabecalho
    # de caixa dupla ate o proximo cabecalho.
    marca = re.search(
        re.escape(_CABECALHO) + r"\s*" + re.escape(_SECAO) + r"\s*" + re.escape(_CABECALHO),
        prompt,
    )
    if not marca:
        return prompt
    inicio_secao = marca.start()
    fim_secao = prompt.find(_CABECALHO, marca.end())
    if fim_secao == -1:
        fim_secao = len(prompt)

    secao = prompt[inicio_secao:fim_secao]
    passo = _PASSO.search(secao)
    if passo:
        seguinte = _PROXIMO_PASSO.search(secao, passo.end())
        fim_passo = seguinte.start() if seguinte else len(secao)
        novo = (
            f"{passo.group(1)}. CADASTRO\n"
            f"   Esta pessoa JÁ É PACIENTE CADASTRADA"
            f"{' (nome: ' + nome + ')' if nome else ''}. A clínica já tem nome,\n"
            f"   data de nascimento, CPF e e-mail dela. NÃO peça nenhum desses dados.\n"
            f"   Depois do sim dela, chame calculate_discount e book_appointment\n"
            f"   direto, sem full_name, birth_date, cpf e email.\n\n"
        )
        secao = secao[:passo.start()] + novo + secao[fim_passo:]
        # As frases de outros passos que mandam passar cadastro para a tool.
        cabeca, resto = secao[:passo.start() + len(novo)], secao[passo.start() + len(novo):]
        resto = "\n".join(
            linha for linha in resto.split("\n") if _FRASE_DE_CADASTRO not in linha.lower()
        )
        secao = cabeca + resto

    return prompt[:inicio_secao] + secao + prompt[fim_secao:]
