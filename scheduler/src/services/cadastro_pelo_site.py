# -*- coding: utf-8 -*-
"""O cadastro do paciente que o site grava - com ou sem agendamento (PRD 061).

Ate 23/11/2026 este preenchimento vivia dentro de
`AppointmentService._get_or_create_patient` e so rodava ao criar um
agendamento. O PRD 061 cadastra a pessoa assim que ela confirma o codigo do
WhatsApp, antes de escolher data; quem abandona fica cadastrado sem sessao.
A criacao e a rota de cadastro gravam pelo MESMO codigo, para a ficha nao
depender de qual caminho a pessoa seguiu.

Regras (inalteradas desde o PRD 032):
- casa pelas variantes do numero (com e sem o nono digito); exato vence;
  ativo vence apagado;
- o que ja esta cadastrado NAO e sobrescrito: so o vazio e preenchido
  (COALESCE). Quem esta no sistema pode ter sido corrigido a mao;
- ficha apagada (soft-delete) volta no lugar, completando o vazio;
- sem ficha, INSERT com o que veio.
"""
import logging
from typing import Any, Dict, Optional

from src.utils.phone import formas_do_numero, normalize_phone

logger = logging.getLogger(__name__)


def completa_paciente(db, clinic_id: str, phone: str, nome: Optional[str] = None,
                      cpf: Optional[str] = None, birth_date: Optional[str] = None,
                      email: Optional[str] = None) -> Dict[str, Any]:
    """O paciente deste celular, criado se ainda nao existir, com o vazio
    preenchido pelo que veio. Devolve a linha de `scheduler.patients`."""
    phone = normalize_phone(phone)
    nome = (nome or "").strip() or None

    patients = db.execute_query(
        "SELECT * FROM scheduler.patients WHERE clinic_id = %s AND phone = ANY(%s) "
        "ORDER BY (phone = %s) DESC, (deleted_at IS NULL) DESC, created_at",
        (clinic_id, formas_do_numero(phone), phone),
    )

    if patients:
        existing = patients[0]
        if existing.get("deleted_at") is None:
            if _completa_algo(existing, nome, cpf, birth_date, email):
                atualizado = db.execute_write_returning(
                    """
                    UPDATE scheduler.patients
                       SET name = COALESCE(NULLIF(name, ''), %s),
                           cpf = COALESCE(NULLIF(cpf, ''), %s),
                           birth_date = COALESCE(birth_date, %s::date),
                           email = COALESCE(NULLIF(email, ''), %s),
                           updated_at = NOW()
                     WHERE id = %s::uuid
                    RETURNING *
                    """,
                    (nome, cpf, birth_date, email, str(existing["id"])),
                )
                return atualizado or existing
            return existing

        restored = db.execute_write_returning(
            """
            UPDATE scheduler.patients
               SET deleted_at = NULL,
                   name = COALESCE(NULLIF(name, ''), %s),
                   cpf = COALESCE(NULLIF(cpf, ''), %s),
                   birth_date = COALESCE(birth_date, %s::date),
                   email = COALESCE(NULLIF(email, ''), %s),
                   updated_at = NOW()
             WHERE id = %s::uuid
            RETURNING *
            """,
            (nome, cpf, birth_date, email, str(existing["id"])),
        )
        logger.info(f"[Cadastro] Patient restored from soft-delete: id={existing['id']} phone={phone}")
        return restored

    return db.execute_write_returning(
        """
        INSERT INTO scheduler.patients (clinic_id, phone, name, cpf, birth_date, email, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s::date, %s, NOW(), NOW())
        RETURNING *
        """,
        (clinic_id, phone, nome, cpf, birth_date, email),
    )


def _completa_algo(existente: Dict[str, Any], nome, cpf, birth_date, email) -> bool:
    """Veio algum dado para um campo que esta vazio no cadastro?"""
    def vazio(campo):
        v = existente.get(campo)
        return v is None or (isinstance(v, str) and not v.strip())
    return any(novo and vazio(campo) for campo, novo in (
        ("name", nome), ("cpf", cpf), ("birth_date", birth_date), ("email", email)))


def conflito_de_cpf(db, clinic_id: str, cpf: Optional[str], proprio_id) -> bool:
    """O CPF ja e de OUTRO paciente da clinica? O mesmo CPF em dois telefones
    viraria dois pacientes, e o check-in cobraria no cadastro errado."""
    if not cpf:
        return False
    proprio = str(proprio_id) if proprio_id else None
    dono = db.execute_query(
        "SELECT id FROM scheduler.patients WHERE clinic_id = %s AND cpf = %s "
        "AND deleted_at IS NULL AND (%s::uuid IS NULL OR id <> %s::uuid) LIMIT 1",
        (clinic_id, cpf, proprio, proprio),
    )
    return bool(dono)


def primeiro_nome(nome) -> str:
    """So o primeiro nome vai ao site ("Ola, Edna, e voce?"): o sobrenome nao
    ajuda a pergunta e e dado a menos exposto."""
    return (str(nome or "").strip().split() or [""])[0]
