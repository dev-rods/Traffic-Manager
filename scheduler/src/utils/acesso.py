# -*- coding: utf-8 -*-
"""Quem é quem, e o que cada um alcança.

Até 21/09/2026 o login devolvia a `SCHEDULER_API_KEY` para todo mundo: uma
chave só, sem identidade, com acesso a tudo. Esconder menu no frontend não
resolveria nada, porque o funcionário teria em mãos a mesma chave que o
administrador e poderia chamar qualquer rota direto.

Duas decisões sustentam este módulo:

1. **A chave mestra continua sendo ADMIN, intocada.** Quem já usa o painel, o
   bot, os scripts e o Postman não sente diferença nenhuma. O risco de mexer
   numa conta que funciona é maior que o ganho de arrumá-la junto - e a dívida
   de a chave compartilhada viajar até o navegador continua registrada, para
   ser paga à parte.

2. **Negar é o padrão.** `require_api_key` passa a RECUSAR quem não é admin, e
   as 76 rotas que a chamam continuam exatamente como estavam - fechadas. Só as
   poucas rotas que o funcionário precisa chamam `require_acesso`, declarando o
   que exigem. Esquecer uma rota fecha a porta em vez de abri-la, que é o lado
   certo para errar.
"""
import hashlib
import logging
import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

import pytz

logger = logging.getLogger(__name__)

ADMIN = "ADMIN"
STAFF = "STAFF"
PAPEIS = (ADMIN, STAFF)

# Quanto tempo vale a sessão de um funcionário. Um turno de trabalho: quem
# chega de manhã entra uma vez, e a sessão não sobrevive à noite.
HORAS_DE_SESSAO = 12

# O fuso em que "hoje" e decidido. A Lambda roda em UTC, e a clinica nao: as
# 21h de Sao Paulo ja sao o dia seguinte em UTC, e usar `date.today()` cru
# tirava da funcionaria a agenda DE HOJE justamente no fim do expediente - que
# e quando ela vai registrar a sessao que acabou de fazer. Pego em 20/09/2026,
# conferindo a janela contra dados reais.
FUSO_PADRAO = "America/Sao_Paulo"

# Janela da agenda quando ninguém configurou nada para aquele funcionário.
# Um padrão conservador evita os dois extremos ruins: travar a pessoa de fora
# da própria agenda, e liberar o calendário inteiro por esquecimento.
DIAS_PADRAO_A_FRENTE = 14

# O que um funcionário alcança. Tudo que não está aqui é negado.
PERMISSOES_DO_STAFF = frozenset({
    "agenda.ler",
    "agenda.escrever",
    "catalogo.ler",
    "pacientes.ler",
    "pacientes.escrever",
    "prontuario.ler",
    "prontuario.escrever",
    "clinica.basica",
})


@dataclass(frozen=True)
class Identidade:
    papel: str
    chave_mestra: bool = False
    user_id: Optional[str] = None
    clinic_id: Optional[str] = None
    nome: Optional[str] = None
    dias_a_frente: Optional[int] = None
    visivel_ate: Optional[date] = None
    fuso: str = FUSO_PADRAO
    # Dois interruptores por pessoa. Ignorados para ADMIN, que ve tudo.
    ve_precos: bool = False
    ve_lista_de_pacientes: bool = True

    @property
    def e_admin(self) -> bool:
        return self.papel == ADMIN

    def pode(self, permissao: str) -> bool:
        if self.e_admin:
            return True
        if permissao == "pacientes.ler" and not self.ve_lista_de_pacientes:
            # Sem a lista ela ainda agenda (o cadastro sai pelo telefone) e
            # ainda registra a sessao (chega pelo atalho da agenda). O que
            # some e so a busca livre pela base inteira de pacientes.
            return False
        return permissao in PERMISSOES_DO_STAFF

    @property
    def mostra_valores(self) -> bool:
        return self.e_admin or self.ve_precos


def hash_do_token(token: str) -> str:
    """O banco guarda o hash, nunca o token.

    Vazamento da tabela não pode virar sessão válida.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def hoje_na_clinica(fuso: Optional[str] = None) -> date:
    """O dia de hoje para quem esta na clinica, e nao para o relogio da AWS."""
    try:
        zona = pytz.timezone(fuso or FUSO_PADRAO)
    except Exception:
        logger.error(f"[acesso] Fuso desconhecido: {fuso!r}. Usando {FUSO_PADRAO}.")
        zona = pytz.timezone(FUSO_PADRAO)
    return datetime.now(zona).date()


def janela_da_agenda(identidade: Identidade, hoje: Optional[date] = None) -> Tuple[date, date]:
    """De quando até quando este usuário enxerga a agenda.

    Decisão do André em 21/09/2026: o funcionário vê de HOJE em diante, sem
    passado. A consequência, aceita de olhos abertos, é que uma sessão não
    registrada no mesmo dia sai do alcance dele e passa a depender do admin.

    O fim é o MAIS RESTRITIVO entre os dois controles, quando os dois existem:
    travar numa data não pode ser afrouxado pelo contador de dias, nem o
    contrário.
    """
    hoje = hoje or hoje_na_clinica(identidade.fuso)

    limites = []
    if identidade.dias_a_frente is not None:
        limites.append(hoje + timedelta(days=identidade.dias_a_frente))
    if identidade.visivel_ate is not None:
        limites.append(identidade.visivel_ate)

    if not limites:
        limites.append(hoje + timedelta(days=DIAS_PADRAO_A_FRENTE))

    return hoje, min(limites)


def identifica(event) -> Optional[Identidade]:
    """Quem está chamando. `None` quando o token não vale nada.

    A chave mestra vence primeiro e não toca o banco: é o caminho de todo o
    tráfego que já existe, e não pode ficar mais lento nem mais frágil por
    causa de uma funcionalidade nova.
    """
    from src.utils.http import extract_api_key

    token = extract_api_key(event)
    if not token:
        return None

    mestra = os.environ.get("SCHEDULER_API_KEY")
    if mestra and token == mestra:
        return Identidade(papel=ADMIN, chave_mestra=True)

    return _sessao(token)


def _sessao(token: str) -> Optional[Identidade]:
    from src.services.db.postgres import PostgresService

    try:
        linhas = PostgresService().execute_query(
            """
            SELECT u.id, u.clinic_id, u.name, u.role, u.active,
                   u.agenda_days_ahead, u.agenda_visible_until,
                   u.can_see_prices, u.can_see_patient_list,
                   c.timezone
              FROM scheduler.user_sessions s
              JOIN scheduler.clinic_users u ON u.id = s.user_id
              JOIN scheduler.clinics c ON c.clinic_id = u.clinic_id
             WHERE s.token_hash = %s
               AND s.expires_at > NOW()
               AND s.revoked_at IS NULL
            """,
            (hash_do_token(token),),
        )
    except Exception as e:
        # Sem banco não há como afirmar que a sessão vale. Negar é a resposta.
        logger.error(f"[acesso] Falha ao ler a sessao: {e}")
        return None

    if not linhas:
        return None

    u = linhas[0]
    if not u.get("active", False):
        return None

    papel = u.get("role") or ADMIN
    if papel not in PAPEIS:
        logger.error(f"[acesso] Papel desconhecido em {u['id']}: {papel!r}")
        return None

    return Identidade(
        papel=papel,
        user_id=str(u["id"]),
        clinic_id=u.get("clinic_id"),
        nome=u.get("name"),
        dias_a_frente=u.get("agenda_days_ahead"),
        visivel_ate=u.get("agenda_visible_until"),
        fuso=u.get("timezone") or FUSO_PADRAO,
        ve_precos=bool(u.get("can_see_prices")),
        ve_lista_de_pacientes=bool(u.get("can_see_patient_list", True)),
    )


def require_acesso(event, permissao: str):
    """Autoriza uma rota que o funcionário PODE alcançar.

    Devolve `(identidade, None)` quando pode, e `(None, resposta)` quando não.
    Rotas que não chamam isto seguem em `require_api_key`, que é só do admin.
    """
    from src.utils.http import http_response

    identidade = identifica(event)
    if identidade is None:
        return None, http_response(401, {"status": "ERROR", "message": "Não autorizado"})

    if not identidade.pode(permissao):
        logger.info(f"[acesso] {identidade.papel} barrado em {permissao}")
        return None, http_response(403, {
            "status": "ERROR",
            "message": "Seu usuário não tem acesso a esta função",
        })

    if identidade.clinic_id:
        erro = _confere_a_clinica(event, identidade)
        if erro:
            return None, erro

    return identidade, None


def _confere_a_clinica(event, identidade: Identidade):
    """Um funcionário só alcança a própria clínica.

    Sem isto, o token da Essência leria a agenda da Nobre Laser trocando o id
    na URL - as três clínicas dividem o mesmo banco.
    """
    from src.utils.http import extract_path_param, http_response

    pedido = extract_path_param(event, "clinicId")
    if pedido and pedido != identidade.clinic_id:
        logger.info(
            f"[acesso] {identidade.user_id} pediu {pedido}, é de {identidade.clinic_id}"
        )
        return http_response(403, {
            "status": "ERROR",
            "message": "Seu usuário não tem acesso a esta clínica",
        })
    return None
