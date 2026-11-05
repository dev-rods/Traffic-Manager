# -*- coding: utf-8 -*-
"""Termo de consentimento (TCLE) assinado no check-in do iPad (PRD 036).

É o ÚNICO lugar que decide "esta paciente precisa assinar?"
(`precisa_assinar`). O handler do check-in, a lista de agendamentos do painel
e o iPad só perguntam aqui ou mostram o que daqui sai.

Regras:

- Gatilho: há uma versão vigente (`TCLE_VERSION`), a paciente não tem termo
  SIGNED/PAPER dessa versão nesta clínica, e a recepção não dispensou nesta
  sessão. Sem versão configurada, ninguém é cobrado (prod sem configuração
  não trava o balcão).
- Snapshot é o que foi ao documento; `patients` é o cadastro, e o cadastro só
  ganha o que estava vazio (mesma regra de `checkin._guarda_cpf_no_cadastro`).
- Menor de idade NA DATA DA SESSÃO assina pelo responsável legal
  (`signer_kind = GUARDIAN`); o responsável é anexo do termo, não cadastro.
- Um SIGNING por paciente (índice parcial). Dentro de 24 h é reaproveitado,
  para o widget que caiu não gerar outro envelope; mais velho é descartado.
- O provedor nunca recebe `db`; aqui nunca se fala HTTP.
"""
import json
import logging
import os
import uuid
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import Json

from src.providers.signature_provider import (
    ASSINADO, ASSINANDO, CANCELADO, EXPIRADO, PAPEL, ErroDoProvedor, Signatario, SignatureProvider,
    termo_de_teste,
)
from src.services import documentos_s3, relogio
from src.services.idade import e_menor_de_idade, para_data
from src.utils.cadastro import cpf_valido, normaliza_cpf, normaliza_email
from src.utils.phone import is_valid_phone, normalize_phone

logger = logging.getLogger(__name__)

PACIENTE = "PATIENT"
RESPONSAVEL = "GUARDIAN"
NAO_EXIGIDO = "NOT_REQUIRED"
MOTIVOS_DE_DISPENSA = ("SEM_CELULAR", "RECUSOU", "SISTEMA_FORA", "OUTRO")
REAPROVEITA_SIGNING_ATE = timedelta(hours=24)
PRAZO_DO_ENVELOPE = timedelta(days=2)
NOME_DO_PDF = "tcle-assinado.pdf"
NOME_DO_ZIP = "tcle-auditoria.zip"

# Nomes de evento da ClickSign que fecham ou encerram o envelope. O payload do
# webhook v3 varia de versão para versão; `_ids_do_evento` lê o que vier.
EVENTOS_FECHADO = ("auto_close", "close", "closed", "document_closed", "envelope_closed",
                   "envelope.closed", "document.closed")
EVENTOS_CANCELADO = ("cancel", "canceled", "cancelled", "refusal", "refused", "envelope.canceled",
                     "envelope.cancelled", "document.canceled")
EVENTOS_EXPIRADO = ("deadline", "expired", "envelope.deadline", "envelope.expired")


class ConsentimentoInvalido(Exception):
    """Pedido que a paciente (ou a recepção) pode corrigir na tela."""


class NaoEncontrado(Exception):
    pass


def _agora(tz=None) -> datetime:
    """Separado para o teste fixar o relógio."""
    return datetime.now(tz)


def versao() -> str:
    return (os.environ.get("TCLE_VERSION") or "").strip()


def template_key() -> str:
    return (os.environ.get("CLICKSIGN_TCLE_TEMPLATE_KEY") or "").strip()


def _iso(valor) -> Optional[str]:
    return valor.isoformat() if hasattr(valor, "isoformat") else (str(valor) if valor else None)


def _br(valor) -> str:
    d = para_data(valor)
    return d.strftime("%d/%m/%Y") if d else ""


def _cpf_mascarado(cpf: Optional[str]) -> Optional[str]:
    digitos = normaliza_cpf(cpf)
    return "***.***.***-{}".format(digitos[-2:]) if digitos else None


def _cpf_formatado(digitos: str) -> str:
    return "{}.{}.{}-{}".format(digitos[:3], digitos[3:6], digitos[6:9], digitos[9:])


def _telefone_formatado(telefone: str) -> str:
    d = "".join(ch for ch in str(telefone or "") if ch.isdigit())
    if d.startswith("55") and len(d) in (12, 13):
        d = d[2:]
    if len(d) == 11:
        return "({}) {}-{}".format(d[:2], d[2:7], d[7:])
    if len(d) == 10:
        return "({}) {}-{}".format(d[:2], d[2:6], d[6:])
    return telefone or ""


def _dois_nomes(nome: Optional[str]) -> bool:
    return len((nome or "").split()) >= 2


# -- Gatilho ------------------------------------------------------------------

def vigente(db, clinic_id: str, patient_id: str) -> Optional[Dict]:
    """O termo SIGNED/PAPER da versão vigente desta paciente nesta clínica."""
    if not versao():
        return None
    rows = db.execute_query(
        "SELECT * FROM scheduler.patient_consents "
        "WHERE clinic_id = %s AND patient_id = %s::uuid AND term_version = %s "
        "AND status IN ('SIGNED', 'PAPER') ORDER BY created_at DESC LIMIT 1",
        (clinic_id, str(patient_id), versao()),
    )
    return rows[0] if rows else None


def precisa_assinar(db, clinic_id: str, appt: Dict) -> bool:
    """A regra do gatilho, em um lugar só."""
    if not versao():
        return False
    if appt.get("consent_waived_at"):
        return False
    return vigente(db, clinic_id, str(appt["patient_id"])) is None


# -- O que o iPad recebe --------------------------------------------------------

def _paciente(db, patient_id: str) -> Optional[Dict]:
    rows = db.execute_query(
        """
        SELECT p.id, p.name, p.cpf, p.birth_date, p.email, p.phone,
               g.name AS guardian_name, g.cpf AS guardian_cpf, g.birth_date AS guardian_birth_date,
               g.phone AS guardian_phone, g.email AS guardian_email
        FROM scheduler.patients p
        LEFT JOIN scheduler.patient_guardians g ON g.patient_id = p.id
        WHERE p.id = %s::uuid
        """,
        (str(patient_id),),
    )
    return rows[0] if rows else None


def _clinica(db, clinic_id: str) -> Optional[Dict]:
    rows = db.execute_query(
        """
        SELECT c.clinic_id, c.name, c.display_name, c.cidade, c.timezone,
               p.name AS profissional_nome, p.role AS profissional_titulo,
               p.registro_conselho AS profissional_registro
        FROM scheduler.clinics c
        LEFT JOIN scheduler.professionals p ON p.id = c.responsible_professional_id AND p.active = true
        WHERE c.clinic_id = %s
        """,
        (clinic_id,),
    )
    return rows[0] if rows else None


def _clinica_pronta(clinica: Optional[Dict]) -> bool:
    return bool(clinica and clinica.get("profissional_nome") and clinica.get("profissional_registro")
                and (clinica.get("cidade") or "").strip())


def resumo_para_o_ipad(db, clinic_id: str, appt: Dict) -> Dict[str, Any]:
    """`consentRequired` e o pré-preenchimento da tela de dados."""
    if not precisa_assinar(db, clinic_id, appt):
        return {"consentRequired": False, "consentPrefill": None}
    pac = _paciente(db, str(appt["patient_id"])) or {}
    cpf = normaliza_cpf(pac.get("cpf"))
    menor = e_menor_de_idade(pac.get("birth_date"), appt.get("appointment_date"))
    responsavel = None
    if pac.get("guardian_name"):
        responsavel = {
            "name": pac["guardian_name"],
            "cpfMasked": _cpf_mascarado(pac.get("guardian_cpf")),
            "birthDate": _iso(pac.get("guardian_birth_date")),
            "phone": pac.get("guardian_phone"),
            "email": pac.get("guardian_email"),
        }
    return {
        "consentRequired": True,
        "consentPrefill": {
            "name": appt.get("full_name") or pac.get("name"),
            "cpfMasked": _cpf_mascarado(cpf) if cpf and cpf_valido(cpf) else None,
            "cpfKnown": bool(cpf and cpf_valido(cpf)),
            "birthDate": _iso(pac.get("birth_date")),
            "phone": pac.get("phone"),
            "email": pac.get("email"),
            "isMinor": bool(menor),
            "guardian": responsavel,
            "clinicReady": _clinica_pronta(_clinica(db, clinic_id)),
        },
    }


# -- Criação ---------------------------------------------------------------------

def _para_tela(row: Dict, provider: Optional[SignatureProvider]) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "status": row["status"],
        "signerId": row.get("provider_signer_id"),
        "widgetEndpoint": provider.widget_endpoint if provider else "",
        "test": termo_de_teste(row.get("provider")),
        "canSimulate": bool(provider and provider.pode_simular and row.get("provider") == provider.nome),
        "signedAt": _iso(row.get("signed_at")),
    }


def _pessoa(dados: Dict, rotulo: str, exige_telefone: bool) -> Dict[str, Any]:
    """Valida nome, CPF, nascimento, e-mail (e celular) de quem assina."""
    nome = " ".join(str(dados.get("fullName") or dados.get("name") or "").split())
    if not _dois_nomes(nome):
        raise ConsentimentoInvalido("Informe o nome completo {}.".format(rotulo))
    cpf = normaliza_cpf(dados.get("cpf"))
    if not cpf or not cpf_valido(cpf):
        raise ConsentimentoInvalido("Confira o CPF {}: os números não batem.".format(rotulo))
    nascimento = para_data(dados.get("birthDate"))
    if not nascimento or nascimento >= date.today() or date.today().year - nascimento.year > 120:
        raise ConsentimentoInvalido("Confira a data de nascimento {}.".format(rotulo))
    email = normaliza_email(dados.get("email"))
    if not email:
        raise ConsentimentoInvalido("Informe um e-mail válido {}.".format(rotulo))
    pessoa = {"nome": nome, "cpf": cpf, "nascimento": nascimento, "email": email, "telefone": None}
    if exige_telefone:
        telefone = normalize_phone(str(dados.get("phone") or ""))
        if not telefone or not is_valid_phone(telefone):
            raise ConsentimentoInvalido("Informe o celular {}.".format(rotulo))
        pessoa["telefone"] = telefone
    return pessoa


def _signing_da_paciente(db, clinic_id: str, patient_id: str) -> Optional[Dict]:
    rows = db.execute_query(
        "SELECT * FROM scheduler.patient_consents "
        "WHERE clinic_id = %s AND patient_id = %s::uuid AND status = 'SIGNING' LIMIT 1",
        (clinic_id, str(patient_id)),
    )
    return rows[0] if rows else None


def _pessoa_do_snapshot(p: Optional[Dict]) -> Optional[tuple]:
    if not p:
        return None
    nasc = p.get("nascimento")
    return (p.get("nome"), p.get("cpf"), nasc.isoformat() if isinstance(nasc, date) else nasc,
            (p.get("email") or "").lower(), p.get("telefone"))


def _mesmos_dados(existente: Dict, paciente: Dict, responsavel: Optional[Dict], autoriza_imagem: bool) -> bool:
    """O termo em andamento só serve se foi gerado com os mesmos dados que a
    pessoa acabou de confirmar: o PDF já está pronto na ClickSign com o nome,
    o CPF e a autorização de imagem de então. Editou algo, é outro termo."""
    snapshot = existente.get("patient_snapshot") or {}
    if isinstance(snapshot, str):
        try:
            snapshot = json.loads(snapshot)
        except ValueError:
            return False
    return (_pessoa_do_snapshot(snapshot) == _pessoa_do_snapshot(paciente)
            and _pessoa_do_snapshot(snapshot.get("responsavel")) == _pessoa_do_snapshot(responsavel)
            and bool(existente.get("image_authorized")) == bool(autoriza_imagem))


def _marca(db, consent_id: str, status: str) -> None:
    db.execute_write(
        "UPDATE scheduler.patient_consents SET status = %s, updated_at = NOW() "
        "WHERE id = %s::uuid AND status = 'SIGNING'",
        (status, str(consent_id)),
    )


def _descarta_signing(db, provider: SignatureProvider, row: Dict, motivo: str) -> None:
    if row.get("provider") == provider.nome and row.get("provider_envelope_id"):
        try:
            provider.cancela(row["provider_envelope_id"])
        except ErroDoProvedor as e:
            logger.warning("[Consentimento] cancelar {} falhou ({}): {}".format(row["id"], motivo, e))
    _marca(db, str(row["id"]), EXPIRADO)


def _guarda_no_cadastro(db, patient_id: str, appointment_id: str, pac: Dict, appt: Dict, pessoa: Dict) -> None:
    """O nome que a pessoa confirmou vale para o cadastro e para este
    agendamento (é dele que o prefill lê primeiro). CPF, nascimento e e-mail
    só entram em campo vazio: num telefone compartilhado, o que a pessoa
    digita para o termo dela não pode sobrescrever o cadastro de outra."""
    campos = []
    valores = []  # type: List[Any]
    if (pac.get("name") or "").strip() != pessoa["nome"]:
        campos.append("name = %s")
        valores.append(pessoa["nome"])
    if (appt.get("full_name") or "").strip() != pessoa["nome"]:
        db.execute_write(
            "UPDATE scheduler.appointments SET full_name = %s, updated_at = NOW() WHERE id = %s::uuid",
            (pessoa["nome"], str(appointment_id)),
        )
    if not normaliza_cpf(pac.get("cpf")):
        campos.append("cpf = %s")
        valores.append(pessoa["cpf"])
    if not pac.get("birth_date"):
        campos.append("birth_date = %s")
        valores.append(pessoa["nascimento"])
    if not (pac.get("email") or "").strip():
        campos.append("email = %s")
        valores.append(pessoa["email"])
    if not campos:
        return
    db.execute_write(
        "UPDATE scheduler.patients SET {}, updated_at = NOW() WHERE id = %s::uuid".format(", ".join(campos)),
        tuple(valores + [str(patient_id)]),
    )


def _guarda_responsavel(db, patient_id: str, resp: Dict) -> None:
    db.execute_write(
        """
        INSERT INTO scheduler.patient_guardians (patient_id, name, cpf, birth_date, phone, email)
        VALUES (%s::uuid, %s, %s, %s, %s, %s)
        ON CONFLICT (patient_id) DO UPDATE SET name = EXCLUDED.name, cpf = EXCLUDED.cpf,
            birth_date = EXCLUDED.birth_date, phone = EXCLUDED.phone, email = EXCLUDED.email,
            updated_at = NOW()
        """,
        (str(patient_id), resp["nome"], resp["cpf"], resp["nascimento"], resp["telefone"], resp["email"]),
    )


def _dados_do_modelo(paciente: Dict, responsavel: Optional[Dict], autoriza_imagem: bool,
                     clinica: Dict, hoje: date) -> Dict[str, str]:
    """As variáveis do modelo .docx (docs/work/assets/036-tcle/gera_modelo.js)."""
    signatario = responsavel or paciente
    return {
        "nome_completo": paciente["nome"],
        "cpf": _cpf_formatado(paciente["cpf"]),
        "data_nascimento": _br(paciente["nascimento"]),
        "telefone": _telefone_formatado(signatario["telefone"] or ""),
        "email": paciente["email"],
        "autoriza_imagem": "Autorizo" if autoriza_imagem else "Não autorizo",
        "menor_nome": paciente["nome"] if responsavel else "",
        "responsavel_nome": responsavel["nome"] if responsavel else "",
        "responsavel_cpf": _cpf_formatado(responsavel["cpf"]) if responsavel else "",
        "signatario_nome": signatario["nome"],
        "signatario_cpf": _cpf_formatado(signatario["cpf"]),
        "profissional_nome": clinica.get("profissional_nome") or "",
        "profissional_titulo": clinica.get("profissional_titulo") or "",
        "profissional_registro": clinica.get("profissional_registro") or "",
        "clinica_nome": clinica.get("display_name") or clinica.get("name") or "",
        "cidade": (clinica.get("cidade") or "").strip(),
        "data": hoje.strftime("%d/%m/%Y"),
    }


def inicia(db, provider: SignatureProvider, clinic_id: str, phone: str, appointment_id: str,
           dados: Dict[str, Any]) -> Dict[str, Any]:
    """Cria (ou reaproveita) o termo SIGNING desta paciente e devolve o que o
    widget precisa. Posse do agendamento pelo mesmo guard do pagamento."""
    from src.services import checkin
    appt = checkin._do_numero(db, clinic_id, phone, appointment_id)
    patient_id = str(appt["patient_id"])
    if not precisa_assinar(db, clinic_id, appt):
        return {"consent": {"id": None, "status": NAO_EXIGIDO, "signerId": None, "widgetEndpoint": "",
                            "test": False, "canSimulate": False, "signedAt": None}}

    clinica = _clinica(db, clinic_id)
    if not _clinica_pronta(clinica):
        raise ConsentimentoInvalido("A clínica ainda não cadastrou a profissional responsável. Chame a recepção.")
    if not template_key():
        raise ConsentimentoInvalido("O modelo do termo não está configurado. Chame a recepção.")

    pac = _paciente(db, patient_id) or {}
    dados = dados or {}
    if dados.get("cpf") in (None, "") and normaliza_cpf(pac.get("cpf")):
        # `cpf: null` = manter o CPF já conhecido; o iPad não pede de novo.
        dados = dict(dados, cpf=normaliza_cpf(pac.get("cpf")))
    paciente = _pessoa(dados, "da paciente", exige_telefone=False)
    paciente["telefone"] = normalize_phone(phone)
    if not isinstance(dados.get("imageAuthorized"), bool):
        raise ConsentimentoInvalido("Escolha se autoriza ou não o uso de imagem.")
    autoriza_imagem = dados["imageAuthorized"]

    menor = bool(e_menor_de_idade(paciente["nascimento"], appt.get("appointment_date")))
    responsavel = None
    if menor:
        if not isinstance(dados.get("guardian"), dict):
            raise ConsentimentoInvalido("Menor de idade: informe os dados do responsável legal.")
        responsavel = _pessoa(dados["guardian"], "do responsável", exige_telefone=True)
        if responsavel["cpf"] == paciente["cpf"]:
            raise ConsentimentoInvalido("O CPF do responsável não pode ser o mesmo da paciente.")
    signer_kind = RESPONSAVEL if menor else PACIENTE

    existente = _signing_da_paciente(db, clinic_id, patient_id)
    if existente:
        criado = existente.get("created_at")
        recente = isinstance(criado, datetime) and (_agora(criado.tzinfo) - criado) <= REAPROVEITA_SIGNING_ATE
        if (recente and existente.get("term_version") == versao() and existente.get("signer_kind") == signer_kind
                and existente.get("provider") == provider.nome
                and _mesmos_dados(existente, paciente, responsavel, autoriza_imagem)):
            return {"consent": _para_tela(existente, provider)}
        _descarta_signing(db, provider, existente, "reinício" if recente else "antigo")

    _guarda_no_cadastro(db, patient_id, appointment_id, pac, appt, paciente)
    if responsavel:
        _guarda_responsavel(db, patient_id, responsavel)

    tz = clinica.get("timezone")
    agora = relogio.agora_na_clinica(tz)
    variaveis = _dados_do_modelo(paciente, responsavel, autoriza_imagem, clinica, agora.date())
    signatario_dict = responsavel or paciente
    signatario = Signatario(nome=signatario_dict["nome"], cpf=signatario_dict["cpf"],
                            nascimento=signatario_dict["nascimento"], telefone=signatario_dict["telefone"],
                            email=signatario_dict["email"])
    referencia = "{}/{}".format(clinic_id, appointment_id)
    consent_id = str(uuid.uuid4())
    termo = provider.cria_termo(
        template_key(), "TCLE-{}-{}.docx".format(versao(), patient_id[:8]), variaveis, signatario,
        referencia, agora + PRAZO_DO_ENVELOPE,
    )
    snapshot = {
        "nome": paciente["nome"], "cpf": paciente["cpf"], "nascimento": paciente["nascimento"].isoformat(),
        "telefone": paciente["telefone"], "email": paciente["email"],
        "menor": menor, "responsavel": None if not responsavel else {
            "nome": responsavel["nome"], "cpf": responsavel["cpf"],
            "nascimento": responsavel["nascimento"].isoformat(),
            "telefone": responsavel["telefone"], "email": responsavel["email"]},
        "variaveis": variaveis,
    }
    responsavel_tecnico = {
        "clinica": variaveis["clinica_nome"], "cidade": variaveis["cidade"],
        "profissional_nome": variaveis["profissional_nome"],
        "profissional_titulo": variaveis["profissional_titulo"],
        "profissional_registro": variaveis["profissional_registro"],
    }
    try:
        row = db.execute_write_returning(
            """
            INSERT INTO scheduler.patient_consents
                (id, clinic_id, patient_id, appointment_id, term_version, status, signer_kind,
                 signer_name, signer_cpf, signer_birth_date, signer_phone, signer_email,
                 patient_snapshot, image_authorized, responsible_snapshot,
                 provider, provider_envelope_id, provider_document_id, provider_signer_id)
            VALUES (%s::uuid, %s, %s::uuid, %s::uuid, %s, 'SIGNING', %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (consent_id, clinic_id, patient_id, appointment_id, versao(), signer_kind,
             signatario.nome, signatario.cpf, signatario.nascimento, signatario.telefone, signatario.email,
             Json(snapshot), autoriza_imagem, Json(responsavel_tecnico),
             provider.nome, termo.envelope_id, termo.document_id, termo.signer_id),
        )
    except psycopg2.IntegrityError:
        # Dois toques ao mesmo tempo: o outro já gravou. Este envelope não
        # pode ficar vivo sem registro nosso.
        logger.warning("[Consentimento] termo concorrente para {} em {}".format(patient_id, clinic_id))
        _cancela_orfao(provider, termo.envelope_id, referencia)
        existente = _signing_da_paciente(db, clinic_id, patient_id)
        if not existente:
            raise ConsentimentoInvalido("Não conseguimos preparar o termo. Tente de novo.")
        return {"consent": _para_tela(existente, provider)}
    except Exception:
        logger.exception("[Consentimento] envelope {} criado mas não gravado ({})".format(
            termo.envelope_id, referencia))
        _cancela_orfao(provider, termo.envelope_id, referencia)
        raise
    logger.info("[Consentimento] termo {} {} {} provider={} envelope={} signer_kind={}".format(
        consent_id, clinic_id, appointment_id, provider.nome, termo.envelope_id, signer_kind))
    return {"consent": _para_tela(row, provider)}


def _cancela_orfao(provider: SignatureProvider, envelope_id: str, referencia: str) -> None:
    try:
        provider.cancela(envelope_id)
    except Exception as e:
        logger.error("[Consentimento] envelope órfão {} ({}) ficou vivo em {}: {}".format(
            envelope_id, referencia, provider.nome, e))


# -- Acompanhamento ----------------------------------------------------------------

def _do_numero(db, clinic_id: str, phone: str, consent_id: str) -> Dict:
    """O termo, se o agendamento dele é deste número (posse)."""
    from src.utils.phone import variantes_do_numero
    try:
        uuid.UUID(str(consent_id))
    except ValueError:
        raise NaoEncontrado()
    rows = db.execute_query(
        """
        SELECT pc.* FROM scheduler.patient_consents pc
        JOIN scheduler.patients p ON p.id = pc.patient_id
        WHERE pc.id = %s::uuid AND pc.clinic_id = %s
          AND p.phone = ANY(%s) AND p.deleted_at IS NULL
        """,
        (consent_id, clinic_id, sorted(variantes_do_numero(phone))),
    )
    if not rows:
        raise NaoEncontrado()
    return rows[0]


def _por_id(db, consent_id: str) -> Optional[Dict]:
    rows = db.execute_query("SELECT * FROM scheduler.patient_consents WHERE id = %s::uuid", (str(consent_id),))
    return rows[0] if rows else None


def _fecha(db, provider: SignatureProvider, row: Dict) -> Dict:
    """Baixa o PDF assinado, guarda no S3 e marca SIGNED. Idempotente. Se o
    download falhar, loga e NÃO marca: o próximo polling ou webhook tenta."""
    if row.get("status") != ASSINANDO:
        return row
    if row.get("provider") != provider.nome:
        logger.error("[Consentimento] termo {} é de {}, provedor ativo é {}".format(
            row["id"], row.get("provider"), provider.nome))
        return row
    envelope_id, document_id = row["provider_envelope_id"], row["provider_document_id"]
    try:
        pdf = provider.baixa_pdf(envelope_id, document_id)
    except ErroDoProvedor as e:
        logger.warning("[Consentimento] PDF de {} ainda não disponível: {}".format(row["id"], e))
        return row
    if not pdf:
        logger.warning("[Consentimento] PDF de {} veio vazio".format(row["id"]))
        return row
    chave_pdf = documentos_s3.chave_do_termo(row["clinic_id"], str(row["patient_id"]), str(row["id"]), NOME_DO_PDF)
    sha = documentos_s3.grava(chave_pdf, pdf, "application/pdf")
    chave_zip = None
    try:
        zipado = provider.baixa_zip(envelope_id, document_id)
    except ErroDoProvedor as e:
        logger.warning("[Consentimento] zip de {} indisponível: {}".format(row["id"], e))
        zipado = None
    if zipado:
        chave_zip = documentos_s3.chave_do_termo(row["clinic_id"], str(row["patient_id"]), str(row["id"]), NOME_DO_ZIP)
        documentos_s3.grava(chave_zip, zipado, "application/zip")
    atualizado = db.execute_write_returning(
        """
        UPDATE scheduler.patient_consents
           SET status = 'SIGNED', signed_at = COALESCE(signed_at, NOW()), pdf_s3_key = %s, pdf_sha256 = %s,
               audit_s3_key = %s, updated_at = NOW()
         WHERE id = %s::uuid AND status = 'SIGNING'
        RETURNING *
        """,
        (chave_pdf, sha, chave_zip, str(row["id"])),
    )
    logger.info("[Consentimento] assinado {} {} sha256={}".format(row["id"], row["clinic_id"], sha[:12]))
    return atualizado or _por_id(db, str(row["id"])) or dict(row, status=ASSINADO)


def _sincroniza(db, provider: SignatureProvider, row: Dict) -> Dict:
    """SIGNING pergunta ao provedor e aplica o que ele disser."""
    if row["status"] != ASSINANDO or row.get("provider") != provider.nome or not row.get("provider_envelope_id"):
        return row
    try:
        estado = provider.consulta(row["provider_envelope_id"])
    except ErroDoProvedor as e:
        logger.warning("[Consentimento] consulta de {} falhou: {}".format(row["id"], e))
        return row
    if estado == ASSINADO:
        return _fecha(db, provider, row)
    if estado in (CANCELADO, EXPIRADO):
        _marca(db, str(row["id"]), estado)
        return _por_id(db, str(row["id"])) or dict(row, status=estado)
    return row


def status(db, provider: SignatureProvider, clinic_id: str, phone: str, consent_id: str) -> Dict[str, Any]:
    row = _do_numero(db, clinic_id, phone, consent_id)
    return {"consent": _para_tela(_sincroniza(db, provider, row), provider)}


def simula(db, provider: SignatureProvider, clinic_id: str, phone: str, consent_id: str) -> Dict[str, Any]:
    """Só com o provedor simulado (dev sem chave)."""
    row = _do_numero(db, clinic_id, phone, consent_id)
    if not provider.pode_simular or row.get("provider") != provider.nome:
        raise ConsentimentoInvalido("Este ambiente não simula assinatura: assine pelo widget.")
    if row["status"] == ASSINANDO:
        provider.simula(row["provider_envelope_id"])
    return status(db, provider, clinic_id, phone, consent_id)


# -- Webhook ---------------------------------------------------------------------------

def _achados(obj: Any, chaves: List[str], profundidade: int = 0) -> List[str]:
    """Valores de `chaves` em qualquer nível do payload, na ordem em que aparecem."""
    out = []  # type: List[str]
    if profundidade > 6:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in chaves and isinstance(v, (str, int)) and str(v):
                out.append(str(v))
            elif isinstance(v, (dict, list)):
                out.extend(_achados(v, chaves, profundidade + 1))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_achados(item, chaves, profundidade + 1))
    return out


def _nome_do_evento(evento: Dict) -> str:
    ev = evento.get("event")
    if isinstance(ev, dict):
        return str(ev.get("name") or ev.get("type") or "").lower()
    if isinstance(ev, str):
        return ev.lower()
    return str(evento.get("name") or evento.get("type") or "").lower()


def _ids_do_evento(evento: Dict) -> Dict[str, List[str]]:
    """Chaves de documento e de envelope, onde quer que o payload as ponha."""
    documentos = []  # type: List[str]
    envelopes = []  # type: List[str]
    for nome, lista in (("document", documentos), ("envelope", envelopes)):
        for bloco in _achados_de(evento, nome):
            lista.extend(_achados(bloco, ["key", "id"]) if isinstance(bloco, dict) else [])
    return {"documentos": documentos, "envelopes": envelopes}


def _achados_de(obj: Any, chave: str, profundidade: int = 0) -> List[Any]:
    out = []  # type: List[Any]
    if profundidade > 6:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == chave:
                out.append(v)
            if isinstance(v, (dict, list)):
                out.extend(_achados_de(v, chave, profundidade + 1))
    elif isinstance(obj, list):
        for item in obj:
            out.extend(_achados_de(item, chave, profundidade + 1))
    return out


def event_id_de(evento: Dict) -> str:
    """O id próprio do evento; sem ele, nome + chave do documento + instante."""
    ev = evento.get("event") if isinstance(evento.get("event"), dict) else {}
    proprio = ev.get("id") or evento.get("id")
    if proprio:
        return str(proprio)[:120]
    ids = _ids_do_evento(evento)
    chave = (ids["documentos"] or ids["envelopes"] or ["?"])[0]
    instante = ev.get("occurred_at") or evento.get("occurred_at") or evento.get("created_at") or ""
    return "{}:{}:{}".format(_nome_do_evento(evento), chave, instante)[:120]


def aplica_evento(db, provider: SignatureProvider, evento: Dict[str, Any], event_id: str) -> str:
    """Um evento do webhook da ClickSign. Idempotente pelo `event_id`, gravado
    só DEPOIS de processado (como o Asaas): reenvio após falha não é
    repetição, e processar duas vezes é inofensivo."""
    nome = _nome_do_evento(evento)
    ids = _ids_do_evento(evento)
    if not event_id or not nome:
        return "ignorado: sem id"
    if db.execute_query("SELECT 1 FROM scheduler.consent_webhook_events WHERE event_id = %s", (event_id,)):
        return "repetido"
    resultado = _processa_evento(db, provider, nome, ids)
    db.execute_write(
        "INSERT INTO scheduler.consent_webhook_events (event_id, provider, event, provider_document_id, payload) "
        "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (event_id) DO NOTHING",
        (event_id, provider.nome, nome[:60], (ids["documentos"] or [None])[0], Json(_payload_enxuto(evento))),
    )
    return resultado


def _payload_enxuto(evento: Dict) -> Dict:
    """O que vale guardar: nomes e chaves, nunca o documento inteiro."""
    return {"event": _nome_do_evento(evento), "ids": _ids_do_evento(evento),
            "occurred_at": (evento.get("event") or {}).get("occurred_at")
            if isinstance(evento.get("event"), dict) else evento.get("occurred_at")}


def _processa_evento(db, provider: SignatureProvider, nome: str, ids: Dict[str, List[str]]) -> str:
    if nome in EVENTOS_FECHADO:
        destino = ASSINADO
    elif nome in EVENTOS_CANCELADO:
        destino = CANCELADO
    elif nome in EVENTOS_EXPIRADO:
        destino = EXPIRADO
    else:
        return "ignorado: {}".format(nome)
    row = _por_provedor(db, provider.nome, ids)
    if not row:
        return "ignorado: termo desconhecido"
    if row["status"] != ASSINANDO:
        return "ignorado: já {}".format(row["status"])
    if destino == ASSINADO:
        novo = _fecha(db, provider, row)
        return novo["status"] if novo.get("status") == ASSINADO else "pendente: PDF indisponível"
    _marca(db, str(row["id"]), destino)
    logger.info("[Consentimento] webhook {} -> {} termo {}".format(nome, destino, row["id"]))
    return destino


def _por_provedor(db, provider_nome: str, ids: Dict[str, List[str]]) -> Optional[Dict]:
    for doc in ids["documentos"]:
        rows = db.execute_query(
            "SELECT * FROM scheduler.patient_consents WHERE provider = %s AND provider_document_id = %s",
            (provider_nome, doc),
        )
        if rows:
            return rows[0]
    for env in ids["envelopes"]:
        rows = db.execute_query(
            "SELECT * FROM scheduler.patient_consents WHERE provider = %s AND provider_envelope_id = %s",
            (provider_nome, env),
        )
        if rows:
            return rows[0]
    return None


# -- Painel -------------------------------------------------------------------------------

def para_o_painel(row: Dict) -> Dict[str, Any]:
    return {
        "id": str(row["id"]),
        "appointment_id": str(row["appointment_id"]) if row.get("appointment_id") else None,
        "term_version": row.get("term_version"),
        "status": row.get("status"),
        "signer_kind": row.get("signer_kind"),
        "signer_name": row.get("signer_name"),
        "image_authorized": row.get("image_authorized"),
        "signed_at": _iso(row.get("signed_at")),
        "paper_signed_at": _iso(row.get("paper_signed_at")),
        "paper_registered_by": row.get("paper_registered_by"),
        "has_pdf": bool(row.get("pdf_s3_key")),
        "has_zip": bool(row.get("audit_s3_key")),
        "test": termo_de_teste(row.get("provider")) if row.get("provider") else False,
        "created_at": _iso(row.get("created_at")),
    }


def lista_do_paciente(db, clinic_id: str, patient_id: str) -> List[Dict[str, Any]]:
    try:
        uuid.UUID(str(patient_id))
    except ValueError:
        raise NaoEncontrado()
    rows = db.execute_query(
        "SELECT * FROM scheduler.patient_consents WHERE clinic_id = %s AND patient_id = %s::uuid "
        "ORDER BY created_at DESC",
        (clinic_id, str(patient_id)),
    )
    return [para_o_painel(r) for r in rows]


def dispensa(db, clinic_id: str, appointment_id: str, motivo: str, nota: Optional[str], autor: str) -> Dict[str, Any]:
    """A recepção dispensa o termo NESTA sessão. A próxima pede de novo."""
    if motivo not in MOTIVOS_DE_DISPENSA:
        raise ConsentimentoInvalido("Motivo inválido. Use um de: {}".format(", ".join(MOTIVOS_DE_DISPENSA)))
    nota = (nota or "").strip()[:200] or None
    if motivo == "OUTRO" and not nota:
        raise ConsentimentoInvalido("Descreva o motivo da dispensa.")
    try:
        uuid.UUID(str(appointment_id))
    except ValueError:
        raise NaoEncontrado()
    row = db.execute_write_returning(
        """
        UPDATE scheduler.appointments
           SET consent_waived_at = NOW(), consent_waived_by = %s, consent_waived_reason = %s,
               consent_waived_note = %s, updated_at = NOW()
         WHERE id = %s::uuid AND clinic_id = %s AND status = 'CONFIRMED'
        RETURNING id, consent_waived_at, consent_waived_by, consent_waived_reason, consent_waived_note
        """,
        ((autor or "admin")[:120], motivo, nota, str(appointment_id), clinic_id),
    )
    if not row:
        raise NaoEncontrado()
    logger.info("[Consentimento] dispensa {} {} motivo={} por={}".format(clinic_id, appointment_id, motivo, autor))
    return {k: _iso(v) if k == "consent_waived_at" else (str(v) if k == "id" else v) for k, v in row.items()}


def registra_papel(db, clinic_id: str, patient_id: str, assinado_em: date, autor: str) -> Dict[str, Any]:
    """Termo assinado em papel na recepção: vale como vigente, sem PDF."""
    if not versao():
        raise ConsentimentoInvalido("Nenhuma versão do termo configurada.")
    try:
        uuid.UUID(str(patient_id))
    except ValueError:
        raise NaoEncontrado()
    if not isinstance(assinado_em, date) or assinado_em > date.today():
        raise ConsentimentoInvalido("Data da assinatura inválida.")
    try:
        row = db.execute_write_returning(
            """
            INSERT INTO scheduler.patient_consents
                (clinic_id, patient_id, term_version, status, signer_kind, paper_signed_at, paper_registered_by)
            VALUES (%s, %s::uuid, %s, 'PAPER', 'PATIENT', %s, %s)
            RETURNING *
            """,
            (clinic_id, str(patient_id), versao(), assinado_em, (autor or "admin")[:120]),
        )
    except psycopg2.IntegrityError:
        existente = vigente(db, clinic_id, patient_id)
        if not existente:
            raise
        return para_o_painel(existente)
    logger.info("[Consentimento] papel {} paciente {} por={}".format(clinic_id, patient_id, autor))
    return para_o_painel(row)


def _do_painel(db, clinic_id: str, consent_id: str) -> Dict:
    try:
        uuid.UUID(str(consent_id))
    except ValueError:
        raise NaoEncontrado()
    rows = db.execute_query(
        "SELECT * FROM scheduler.patient_consents WHERE id = %s::uuid AND clinic_id = %s",
        (str(consent_id), clinic_id),
    )
    if not rows:
        raise NaoEncontrado()
    return rows[0]


def url_do_pdf(db, clinic_id: str, consent_id: str) -> Dict[str, Any]:
    row = _do_painel(db, clinic_id, consent_id)
    if not row.get("pdf_s3_key"):
        raise NaoEncontrado()
    return {"url": documentos_s3.url_assinada(row["pdf_s3_key"], nome_do_arquivo=NOME_DO_PDF),
            "expiresInSeconds": documentos_s3.URL_SEGUNDOS}


def url_do_zip(db, clinic_id: str, consent_id: str) -> Dict[str, Any]:
    row = _do_painel(db, clinic_id, consent_id)
    if not row.get("audit_s3_key"):
        raise NaoEncontrado()
    return {"url": documentos_s3.url_assinada(row["audit_s3_key"], nome_do_arquivo=NOME_DO_ZIP),
            "expiresInSeconds": documentos_s3.URL_SEGUNDOS}
