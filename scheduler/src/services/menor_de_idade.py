# -*- coding: utf-8 -*-
"""Menor de 18 só faz a primeira sessão com responsável ou autorização.

Regra do André, 14/09/2026, e ela vale SÓ no bot de leads - a conversa que
começa pela landing page, com alguém que ainda não é paciente. Na campanha, do
outro lado, estão pacientes cadastradas que já vieram à clínica: a primeira
sessão delas já aconteceu, com ou sem responsável, e repetir a exigência seria
cobrar de quem já cumpriu.

"Só na primeira sessão" é literal: a partir da segunda, a idade deixa de
importar para este aviso. Por isso a pergunta não é "é menor?" e sim "é menor E
está estreando?", e quem responde a segunda metade é primeira_visita, o mesmo
lugar que responde isso para o desconto e para a agenda.

A idade é medida NA DATA DA SESSÃO, não hoje: quem faz 18 antes de sentar na
cadeira não precisa de autorização nenhuma. Ver idade.py.

O aviso sai pelo código, como o de preparo - o texto tem consequência jurídica e
não é para o modelo reescrever. Ver orientacoes_pos_sessao.
"""
import logging

from src.services.idade import e_menor_de_idade
from src.services.primeira_visita import e_primeira_visita

logger = logging.getLogger(__name__)

TEXTO = """⚠️ *Atenção: paciente menor de 18 anos*

Como você ainda é menor de idade, a *primeira sessão* só pode ser realizada de uma destas duas formas:

• Com o *acompanhamento de um responsável legal* no dia da sessão; ou
• Com o envio de uma *autorização formal do responsável legal*, assinada digitalmente pelo Gov.br.

Isso vale apenas para a primeira sessão. Nas seguintes, você pode vir sozinho(a).

Qualquer dúvida sobre a autorização, é só nos chamar!"""


def _nascimento(db, clinic_id, phone):
    """A data de nascimento no cadastro, ou None se não temos."""
    try:
        from src.utils.phone import normalize_phone

        linhas = db.execute_query(
            "SELECT birth_date FROM scheduler.patients "
            "WHERE clinic_id = %s AND phone = %s AND deleted_at IS NULL LIMIT 1",
            (clinic_id, normalize_phone(phone)),
        )
        return linhas[0].get("birth_date") if linhas else None
    except Exception as e:
        logger.error(f"[MenorDeIdade] Falha ao ler o cadastro de {phone}: {e}")
        return None


def precisa_avisar(db, clinic_id, phone, data_da_sessao, appointment_id=None):
    """O aviso do menor de idade cabe neste agendamento?

    `appointment_id` é o que acabou de ser criado: sem ignorá-lo, ele conta a si
    mesmo e ninguém nunca está estreando.

    Falha fechada nos dois sentidos - sem data de nascimento, sem idade; sem
    idade, sem aviso. Mandar a exigência de responsável legal para uma adulta é
    um erro que ela conta para as amigas.
    """
    nascimento = _nascimento(db, clinic_id, phone)
    if not nascimento:
        return False

    menor = e_menor_de_idade(nascimento, data_da_sessao)
    if not menor:
        return False

    if not e_primeira_visita(db, clinic_id, phone, ignorar_id=appointment_id):
        logger.info(f"[MenorDeIdade] {phone} é menor mas já é paciente - sem aviso")
        return False

    logger.info(f"[MenorDeIdade] {phone} estreia menor de idade em {data_da_sessao} - avisando")
    return True
