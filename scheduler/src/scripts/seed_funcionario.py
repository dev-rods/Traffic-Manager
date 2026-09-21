# -*- coding: utf-8 -*-
"""Cria (ou atualiza) um usuario de papel STAFF.

    python -m src.scripts.seed_funcionario \
        --clinic clinicaessenciaestetica-9668a4 \
        --email recepcao.essencia@gmail.com \
        --nome "Recepcao Essencia" \
        --senha "..." \
        --dias 14

Idempotente: rodar de novo troca a senha e a janela, e nao duplica o usuario.

Nao existe rota de API para isto de proposito. Criar acesso e ato de
administracao, e nao algo que se dispare de uma tela que ainda nao sabe provar
quem esta do outro lado - ver a divida de auth por usuario.
"""
import argparse
import sys

sys.path.insert(0, ".")

from src.functions.auth.login import hash_password_for_storage
from src.services.db.postgres import PostgresService
from src.utils.acesso import STAFF


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--clinic", required=True)
    p.add_argument("--email", required=True)
    p.add_argument("--nome", required=True)
    p.add_argument("--senha", required=True)
    p.add_argument("--dias", type=int, default=14,
                   help="quantos dias a frente ele enxerga a agenda")
    p.add_argument("--ate", default=None,
                   help="data limite YYYY-MM-DD (opcional; o mais restritivo vence)")
    args = p.parse_args()

    email = args.email.strip().lower()
    db = PostgresService()

    if not db.execute_query(
            "SELECT 1 FROM scheduler.clinics WHERE clinic_id = %s", (args.clinic,)):
        raise SystemExit("Clinica nao encontrada: %s" % args.clinic)

    senha = hash_password_for_storage(args.senha)

    existente = db.execute_query(
        "SELECT id, role FROM scheduler.clinic_users WHERE email = %s", (email,))

    if existente:
        if existente[0]["role"] != STAFF:
            # Rebaixar um administrador por engano de digitacao seria um jeito
            # silencioso de derrubar o acesso de quem trabalha.
            raise SystemExit(
                "%s ja existe como %s. Recusando mudar o papel por script."
                % (email, existente[0]["role"]))
        db.execute_write(
            "UPDATE scheduler.clinic_users "
            "SET password_hash = %s, name = %s, active = TRUE, "
            "    agenda_days_ahead = %s, agenda_visible_until = %s, "
            "    updated_at = NOW() "
            "WHERE email = %s",
            (senha, args.nome, args.dias, args.ate, email))
        # Senha nova invalida o que estava em pe: trocar a senha tem de
        # expulsar quem ja estava dentro.
        db.execute_write(
            "UPDATE scheduler.user_sessions SET revoked_at = NOW() "
            "WHERE user_id = %s AND revoked_at IS NULL", (existente[0]["id"],))
        print("atualizado: %s" % email)
    else:
        db.execute_write(
            "INSERT INTO scheduler.clinic_users "
            "(clinic_id, email, password_hash, name, role, "
            " agenda_days_ahead, agenda_visible_until) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (args.clinic, email, senha, args.nome, STAFF, args.dias, args.ate))
        print("criado: %s" % email)

    u = db.execute_query(
        "SELECT role, active, agenda_days_ahead, agenda_visible_until "
        "FROM scheduler.clinic_users WHERE email = %s", (email,))[0]
    print("  papel=%s ativo=%s dias=%s ate=%s"
          % (u["role"], u["active"], u["agenda_days_ahead"], u["agenda_visible_until"]))


if __name__ == "__main__":
    main()
