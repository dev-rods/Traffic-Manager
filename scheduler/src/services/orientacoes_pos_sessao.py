# -*- coding: utf-8 -*-
"""O aviso que fecha todo agendamento, palavra por palavra.

Primeiro isto foi um filtro por palavra-chave sobre o FAQ. Conferido contra o
FAQ real da Essência em 13/09/2026, ele puxava dez itens - três que não eram
orientação nenhuma ("O resultado é definitivo?") - e deixava de fora "Precisa
levar algo para a sessão?", porque o texto diz "gilete" e o filtro procurava
"lâmina". Adivinhar qual item é orientação é um problema que não precisa
existir: o André escreveu o aviso, e é esse que vai.

Duas decisões que sustentam o "palavra por palavra":

1. O texto NÃO passa pelo modelo. O agente não é instruído a escrevê-lo - o
   código anexa a mensagem depois que a tool gravou o agendamento. Instrução de
   prompt é pedido, e aqui o pedido é reproduzir 15 linhas com contraindicação
   médica sem trocar nada. Nenhum modelo merece essa confiança.

2. A clínica pode sobrescrever pelo template POST_BOOKING_INSTRUCTIONS, como
   qualquer outra mensagem. O texto abaixo é o padrão, não uma amarra.
"""
import logging

logger = logging.getLogger(__name__)

CHAVE_DO_TEMPLATE = "POST_BOOKING_INSTRUCTIONS"

# Texto do André, 13/09/2026. Alterar aqui muda o que todas as clínicas sem
# template próprio enviam - a mudança de uma só vai no template dela.
TEXTO = """⚠️ IMPORTANTE SABER ANTES DA SUA SESSÃO DE LASER

➡️Antes da sessão:
• Raspe os pelos com lâmina no dia anterior ou no mesmo dia.
• Não utilize cera, pinça ou outros métodos que removam o pelo pela raiz.
• Evite exposição solar por aproximadamente 5 dias antes. É permitido realizar o laser em pele bronzeada, desde que não esteja descamando, avermelhada, ardendo ou com outros sinais de sensibilização.
• Suspenda o uso de ácidos na região por 7 dias.

🚫 Nos avise antes de vir caso:
• Esteja gestante ou amamentando;
• Esteja usando Roacutan (isotretinoína), antibióticos ou outros medicamentos fotossensibilizantes;
• Tenha feridas, irritações, infecção, herpes ativa ou alguma condição de pele ativa na região a ser tratada;
• Tenha tatuagem na área da aplicação;
• Tenha realizado peeling ou procedimento agressivo na região nas últimas 2 semanas.

Após a sessão: evite exposição solar por aproximadamente 5 dias e utilize protetor solar nas áreas expostas.
Qualquer dúvida, estamos à disposição!"""


def texto(template_service, clinic_id: str) -> str:
    """O aviso desta clínica: o dela se existir, o padrão se não.

    Nunca propaga erro. Um agendamento confirmado sem o aviso é ruim; um
    agendamento que falha porque a consulta do template caiu é pior.
    """
    try:
        do_banco = (template_service.get_and_render(clinic_id, CHAVE_DO_TEMPLATE) or "").strip()
        if do_banco:
            return do_banco
    except Exception as e:
        logger.error(f"[OrientacoesPosSessao] Falha ao ler o template de {clinic_id}: {e}")
    return TEXTO
