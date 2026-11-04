# -*- coding: utf-8 -*-
"""O bucket privado de documentos das pacientes (PRD 036).

Único ponto que fala com `DOCUMENTOS_BUCKET`. Grava com criptografia no
servidor e devolve o SHA-256 do que gravou, para o banco guardar a prova de
integridade ao lado da chave. O painel nunca recebe a chave: recebe uma URL
assinada de poucos minutos.
"""
import hashlib
import logging
import os
from typing import Optional

import boto3

logger = logging.getLogger(__name__)

URL_SEGUNDOS = 300
_s3 = None


def _cliente():
    global _s3
    if _s3 is None:
        _s3 = boto3.client("s3")
    return _s3


def bucket() -> str:
    return os.environ.get("DOCUMENTOS_BUCKET", "")


def chave_do_termo(clinic_id: str, patient_id: str, consent_id: str, nome: str) -> str:
    return "clinics/{}/patients/{}/consents/{}/{}".format(clinic_id, patient_id, consent_id, nome)


def sha256(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def grava(chave: str, conteudo: bytes, content_type: str = "application/pdf") -> str:
    """Grava e devolve o SHA-256 hex do conteúdo. Sem bucket configurado,
    falha alto: o termo assinado não pode ficar só na ClickSign."""
    nome = bucket()
    if not nome:
        raise RuntimeError("DOCUMENTOS_BUCKET não configurado")
    _cliente().put_object(
        Bucket=nome, Key=chave, Body=conteudo, ContentType=content_type,
        ServerSideEncryption="AES256",
    )
    logger.info("[DocumentosS3] gravado {} ({} bytes)".format(chave, len(conteudo)))
    return sha256(conteudo)


def url_assinada(chave: str, segundos: int = URL_SEGUNDOS, nome_do_arquivo: Optional[str] = None) -> str:
    params = {"Bucket": bucket(), "Key": chave}
    if nome_do_arquivo:
        params["ResponseContentDisposition"] = 'inline; filename="{}"'.format(nome_do_arquivo)
    return _cliente().generate_presigned_url("get_object", Params=params, ExpiresIn=segundos)
