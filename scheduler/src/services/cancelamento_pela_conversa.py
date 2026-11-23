# -*- coding: utf-8 -*-
"""A mensagem que fecha todo cancelamento feito pelo bot (PRD 059).

Texto pedido pela Essência em 2026, palavra por palavra, nos moldes de
`orientacoes_pos_sessao`: o código anexa depois que a tool gravou, o modelo
não é convidado a reproduzi-lo. Em prod, até 23/11/2026, a resposta a um
cancelamento era o que o modelo quisesse escrever, e quase nunca convidava a
remarcar.

Dois templates, porque a segunda parte só faz sentido com o site da clínica
no ar (`autoatendimento.link_de_agendamento`): sem domínio, o parágrafo do
link sai inteiro e o bot oferece remarcar na conversa.
"""
import logging

logger = logging.getLogger(__name__)

CHAVE = "CANCELADO_PELA_CONVERSA"
CHAVE_DO_LINK = "CANCELADO_PELA_CONVERSA_LINK"

TEXTO = "Obrigada por nos avisar! Seu horário foi cancelado com sucesso. ☺️"
TEXTO_DO_LINK = (
    "Caso queira remarcar, você pode acessar nosso link de agendamento e escolher "
    "uma nova data e horário conforme sua disponibilidade. É bem rapidinho e você "
    "consegue fazer tudo por lá! ✨\n{{link}}"
)
TEXTO_SEM_LINK = "Quando quiser remarcar, é só me chamar por aqui. 😊"


def _do_banco(template_service, clinic_id, chave, variables=None):
    try:
        return (template_service.get_and_render(clinic_id, chave, variables) or "").strip()
    except Exception as e:
        logger.error(f"[CancelamentoPelaConversa] Falha ao ler {chave} de {clinic_id}: {e}")
        return ""


def mensagem(template_service, clinic_id: str, link) -> str:
    """A confirmação desta clínica: a dela se existir, a padrão se não.
    Nunca propaga erro: o agendamento já saiu da agenda e a pessoa precisa saber."""
    cabeca = _do_banco(template_service, clinic_id, CHAVE) or TEXTO
    if link:
        corpo = _do_banco(template_service, clinic_id, CHAVE_DO_LINK, {"link": link}) \
            or TEXTO_DO_LINK.replace("{{link}}", link)
    else:
        corpo = TEXTO_SEM_LINK
    return cabeca + "\n\n" + corpo
