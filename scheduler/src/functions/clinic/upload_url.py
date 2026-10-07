import logging
import os
import time
import uuid

import boto3

from src.utils.http import http_response, require_api_key, extract_path_param, parse_body

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ALLOWED_KINDS = {"logo", "favicon"}

ALLOWED_CONTENT_TYPES = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/svg+xml": "svg",
    "image/webp": "webp",
    "image/x-icon": "ico",
    "image/vnd.microsoft.icon": "ico",
}

UPLOAD_URL_TTL_SECONDS = 300


def handler(event, context):
    """
    POST /clinics/{clinicId}/assets/upload-url
    Body: { "kind": "logo" | "favicon", "contentType": "image/png" }

    Gera uma URL pré-assinada do S3 para o painel enviar a imagem direto do
    navegador (sem passar o binário pela Lambda/API Gateway). Devolve também
    a URL pública final, que o painel deve salvar via PUT /clinics/{clinicId}
    (campo logo_url ou favicon_url).
    """
    try:
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId não fornecido no path"})

        body = parse_body(event) or {}
        kind = body.get("kind")
        content_type = body.get("contentType")

        if kind not in ALLOWED_KINDS:
            return http_response(400, {
                "status": "ERROR",
                "message": f"kind deve ser um de: {sorted(ALLOWED_KINDS)}",
            })

        if content_type not in ALLOWED_CONTENT_TYPES:
            return http_response(400, {
                "status": "ERROR",
                "message": f"contentType deve ser um de: {sorted(ALLOWED_CONTENT_TYPES)}",
            })

        extension = ALLOWED_CONTENT_TYPES[content_type]
        key = f"clinics/{clinic_id}/{kind}-{int(time.time())}-{uuid.uuid4().hex[:8]}.{extension}"

        bucket = os.environ["CLINIC_ASSETS_BUCKET"]
        region = os.environ.get("AWS_REGION", "us-east-1")

        s3 = boto3.client("s3")
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=UPLOAD_URL_TTL_SECONDS,
        )
        public_url = f"https://{bucket}.s3.{region}.amazonaws.com/{key}"

        logger.info(f"[UploadAssetUrl] URL gerada: clinic={clinic_id} kind={kind} key={key}")

        return http_response(200, {
            "status": "SUCCESS",
            "uploadUrl": upload_url,
            "publicUrl": public_url,
            "expiresIn": UPLOAD_URL_TTL_SECONDS,
        })

    except Exception as e:
        logger.error(f"Erro ao gerar URL de upload de asset: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
