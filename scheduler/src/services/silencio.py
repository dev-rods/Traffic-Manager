# -*- coding: utf-8 -*-
"""O bot calado para UM contato, por tempo indeterminado (PRD 039).

Dono do registro `scheduler.contatos_silenciados`. Este módulo faz I/O; a
regra de quem responde continua em `atendimento`, que é pura e recebe o
silêncio como argumento (`silenciado=`).

POR QUE NO POSTGRES, e não na sessão do DynamoDB:

1. Retenção. A sessão pode ganhar TTL (PRD 020 §9.3) e o silêncio sumiria com
   o item - o bot voltaria a falar sem ninguém ter pedido.
2. "Quais números estão mudos nesta clínica?" é a pergunta que mantém o
   recurso honesto, e no DynamoDB ela exige varredura.
3. Quem silenciou, quando e por quê é registro, e registro mora em tabela.

E POR QUE NÃO INJETAR NO DICT DA SESSÃO: `session_store.grava_atendimento`,
quando a sessão ainda não existe, grava o dict inteiro (`put_item(Item=...)`).
Um campo injetado viraria cópia persistida de um dado cujo dono é este módulo,
livre para divergir em silêncio. Vai como argumento, que não persiste nada.

Isto reabre, de propósito e em parte, a decisão 9.1 do PRD 020 ("nenhuma pausa
é permanente"): o que ela proibiu foi pausa DERIVADA, que calaria milhares de
conversas antigas por um critério implícito. Esta é DECLARADA - um gesto
humano por contato, com autor, motivo e data, desfeita por outro gesto humano.
"""
import logging
from typing import Dict, Optional, Set

from src.utils.phone import normalize_phone

logger = logging.getLogger(__name__)

MOTIVO_MIN = 3
MOTIVO_MAX = 500


def _db(db=None):
    if db is not None:
        return db
    from src.services.db.postgres import PostgresService
    return PostgresService()


def _motivo_valido(motivo: Optional[str]) -> str:
    """Motivo é obrigatório: silenciar sem motivo é o que produz o número
    calado e esquecido meses depois (risco 5.1 do PRD 019, aqui intencional)."""
    texto = (motivo or "").strip()
    if len(texto) < MOTIVO_MIN:
        raise ValueError("motivo obrigatório para silenciar (mínimo 3 caracteres)")
    return texto[:MOTIVO_MAX]


def esta_silenciado(clinic_id: str, phone: str, db=None) -> bool:
    """Este contato está silenciado agora?

    Falha FECHADA PARA O SILÊNCIO: erro de banco devolve False e o bot
    responde. O contrário (erro -> tudo mudo) calaria todas as clínicas numa
    instabilidade do Postgres, e o sintoma seria invisível - ninguém percebe
    mensagem que não foi enviada. Aqui o pior caso é o bot responder uma
    conversa que devia estar muda, que uma pessoa enxerga e corrige.
    """
    if not clinic_id or not phone:
        return False
    try:
        linhas = _db(db).execute_query(
            """SELECT 1 FROM scheduler.contatos_silenciados
                WHERE clinic_id = %s AND phone = %s AND reativado_em IS NULL
                LIMIT 1""",
            (clinic_id, normalize_phone(phone)))
        return bool(linhas)
    except Exception as e:
        logger.warning(f"[Silencio] Não consegui ler o silêncio de {phone}: {e}")
        return False


def silenciados_da_clinica(clinic_id: str, db=None) -> Set[str]:
    """Todos os telefones mudos da clínica, para as listas do painel.

    Uma consulta por tela, nunca uma por telefone: a lista de conversas
    carrega dezenas de linhas de uma vez. Falha fechada para o silêncio, como
    `esta_silenciado`: sem resposta do banco, nenhum selo - e não uma lista
    inteira marcada por engano.
    """
    if not clinic_id:
        return set()
    try:
        linhas = _db(db).execute_query(
            """SELECT phone FROM scheduler.contatos_silenciados
                WHERE clinic_id = %s AND reativado_em IS NULL""",
            (clinic_id,))
        return {normalize_phone(r["phone"]) for r in linhas if r.get("phone")}
    except Exception as e:
        logger.warning(f"[Silencio] Não consegui listar os silenciados de {clinic_id}: {e}")
        return set()


def detalhe(clinic_id: str, phone: str, db=None) -> Optional[Dict]:
    """Motivo, autor e data do silêncio vivo, para o cabeçalho da conversa.

    Sem isto o selo diria "silenciado" e ninguém saberia por quê - que é
    exatamente como o recurso viraria dívida.
    """
    if not clinic_id or not phone:
        return None
    try:
        linhas = _db(db).execute_query(
            """SELECT motivo, silenciado_por, silenciado_em
                 FROM scheduler.contatos_silenciados
                WHERE clinic_id = %s AND phone = %s AND reativado_em IS NULL
                LIMIT 1""",
            (clinic_id, normalize_phone(phone)))
    except Exception as e:
        logger.warning(f"[Silencio] Não consegui ler o detalhe de {phone}: {e}")
        return None
    if not linhas:
        return None
    linha = linhas[0]
    quando = linha.get("silenciado_em")
    return {
        "motivo": linha.get("motivo"),
        "silenciado_por": linha.get("silenciado_por"),
        "silenciado_em": quando.isoformat() if hasattr(quando, "isoformat") else quando,
    }


def silencia(clinic_id: str, phone: str, motivo: str, por: str, db=None) -> Dict:
    """Cala o bot para este contato até alguém reativar.

    Idempotente: já silenciado devolve o silêncio VIGENTE sem duplicar nem
    sobrescrever o motivo original - duas recepcionistas clicando no mesmo
    botão não podem virar erro na tela, e o primeiro motivo é o que explica.
    Ao contrário de `esta_silenciado`, aqui o erro de banco SOBE: quem clicou
    precisa saber que não funcionou.
    """
    motivo = _motivo_valido(motivo)
    phone = normalize_phone(phone)
    autor = (por or "painel").strip()[:120]
    banco = _db(db)

    ja = detalhe(clinic_id, phone, banco)
    if ja:
        logger.info(f"[Silencio] {phone} já estava silenciado na clínica {clinic_id}")
        return dict(ja, ja_estava=True)

    linha = banco.execute_write_returning(
        """INSERT INTO scheduler.contatos_silenciados
               (clinic_id, phone, motivo, silenciado_por)
           VALUES (%s, %s, %s, %s)
           ON CONFLICT (clinic_id, phone) WHERE reativado_em IS NULL DO NOTHING
           RETURNING motivo, silenciado_por, silenciado_em""",
        (clinic_id, phone, motivo, autor))
    if not linha:
        # Corrida: outra pessoa silenciou entre o detalhe e o insert. O
        # vigente é o que vale.
        return dict(detalhe(clinic_id, phone, banco) or {}, ja_estava=True)

    logger.info(f"[Silencio] Bot silenciado para {phone} na clínica {clinic_id} por {autor}")
    quando = linha.get("silenciado_em")
    return {
        "motivo": linha.get("motivo"),
        "silenciado_por": linha.get("silenciado_por"),
        "silenciado_em": quando.isoformat() if hasattr(quando, "isoformat") else quando,
        "ja_estava": False,
    }


def reativa(clinic_id: str, phone: str, por: str, db=None) -> bool:
    """Devolve o contato ao bot. True se havia silêncio para desfazer.

    A linha NÃO é apagada: ganha `reativado_por`/`reativado_em` e sai do
    índice único parcial, preservando o histórico.

    Não mexe na pausa de 24 h nem em `bot_enabled`: se havia atendente na
    conversa, ela continua com a conversa até vencer. São estados
    independentes, e juntar os dois aqui faria um botão desfazer o outro.
    """
    phone = normalize_phone(phone)
    autor = (por or "painel").strip()[:120]
    linhas = _db(db).execute_write(
        """UPDATE scheduler.contatos_silenciados
              SET reativado_por = %s, reativado_em = NOW()
            WHERE clinic_id = %s AND phone = %s AND reativado_em IS NULL""",
        (autor, clinic_id, phone))
    if linhas:
        logger.info(f"[Silencio] Silêncio removido de {phone} na clínica {clinic_id} por {autor}")
    return bool(linhas)
