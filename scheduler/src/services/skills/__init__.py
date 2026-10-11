# -*- coding: utf-8 -*-
"""Skills: o que o bot pode fazer e como se conduz, por estado comercial.

PRD 020 §6, fase 7. O Router escolhe a skill de forma determinística, pelo
estado comercial (fase 4), e a skill decide duas coisas que ficam em CÓDIGO,
não em instrução:

  1. as tools que o modelo enxerga - lead nova e paciente sem horário não têm
     `reschedule_appointment` nem `cancel_appointment`: não há o que remarcar,
     e uma tool que não existe não pode ser chamada por engano;
  2. um bloco de conduta próprio no system prompt, curto, dizendo o que muda
     para quem está do outro lado.

Por que por ESTADO e não por intenção (revisão de 10/10/2026): tools e system
prompt são o prefixo cacheado da API. O estado comercial é estável durante a
conversa (só muda quando um agendamento é criado ou feito); a intenção muda a
cada mensagem - uma lead pergunta o preço, depois marca, depois tira dúvida.
Despachar por intenção invalidaria o cache a cada turno e pagaria os ~17k
chars de prompt de novo, e ainda faria o bot "trocar de roteiro" no meio da
conversa. As intenções continuam decidindo a pré-carga (roteador), e as
dúvidas e o risco já têm caminho próprio (FAQ literal, nível 3).

O que NÃO muda entre skills (invariantes do PRD §3.1): as áreas são sempre
perguntadas e confirmadas; o cadastro é pedido só do que falta e só na hora
de agendar; o valor vai a quem nunca fez sessão. Cadastro e valor continuam
decididos pelos fatos da pessoa (`identificacao_de_paciente`,
`valor_para_recorrente`), não pela skill: a skill não pode "esquecer" o
cadastro de uma paciente encontrada com cadastro incompleto.

A campanha de reagendamento é uma sobreposição, não uma skill: ela adapta o
roteiro e acrescenta o próprio bloco por cima de qualquer skill
(`prompt_da_campanha`).
"""
from dataclasses import dataclass
from typing import Dict, FrozenSet, List, Optional, Sequence

from src.services import estado_comercial as ec

# Tools que só fazem sentido quando existe sessão marcada.
TOOLS_DE_SESSAO_MARCADA = frozenset({"reschedule_appointment", "cancel_appointment"})


@dataclass(frozen=True)
class Skill:
    nome: str
    estados: FrozenSet[str]
    tools_vetadas: FrozenSet[str]
    bloco: str

    def permite(self, nome_da_tool: str) -> bool:
        return nome_da_tool not in self.tools_vetadas

    def filtra(self, definicoes: Sequence[Dict]) -> List[Dict]:
        """As definições (formato Anthropic ou OpenAI) sem as tools vetadas."""
        saida = []
        for d in definicoes:
            nome = d.get("name") or (d.get("function") or {}).get("name")
            if self.permite(nome):
                saida.append(d)
        return saida


PRIMEIRO_AGENDAMENTO = Skill(
    nome="primeiro_agendamento",
    estados=frozenset({ec.NEW_LEAD}),
    tools_vetadas=TOOLS_DE_SESSAO_MARCADA,
    bloco=(
        "\n═══ QUEM VOCÊ ESTÁ ATENDENDO ═══\n"
        "Uma pessoa que ainda não é paciente: nenhuma sessão feita, nada marcado.\n"
        "1. Apresente a clínica uma vez, no início, e não repita.\n"
        "2. Pergunte e confirme as áreas; só depois os horários.\n"
        "3. O valor da sessão é informado ao confirmar o agendamento.\n"
        "4. O cadastro (nome, nascimento, CPF, e-mail) é pedido só na hora de agendar,\n"
        "   e só o que faltar.\n"
        "5. Não existe sessão marcada: não há o que remarcar ou cancelar.\n"
    ),
)

PACIENTE_COM_HORARIO = Skill(
    nome="paciente_com_horario",
    estados=frozenset({ec.FIRST_BOOKING, ec.ACTIVE_CUSTOMER}),
    tools_vetadas=frozenset(),
    bloco=(
        "\n═══ QUEM VOCÊ ESTÁ ATENDENDO ═══\n"
        "Uma paciente que já tem sessão marcada (veja o próximo horário no bloco QUEM É).\n"
        "1. Não se apresente nem apresente a clínica: a relação já existe.\n"
        "2. Quem já tem sessão marcada raramente quer marcar outra: antes de agendar,\n"
        "   confirme se não é remarcar, cancelar ou tirar uma dúvida sobre a sessão\n"
        "   que existe. Consulte lookup_appointments.\n"
        "3. Se for marcar outra sessão, pergunte e confirme as áreas como sempre:\n"
        "   o que ela fez antes não diz o que quer agora.\n"
        "4. Não repita o valor sem ela perguntar.\n"
    ),
)

PACIENTE_SEM_HORARIO = Skill(
    nome="paciente_sem_horario",
    estados=frozenset({ec.NO_NEXT_BOOKING}),
    tools_vetadas=TOOLS_DE_SESSAO_MARCADA,
    bloco=(
        "\n═══ QUEM VOCÊ ESTÁ ATENDENDO ═══\n"
        "Uma paciente que já fez sessão e não tem a próxima marcada.\n"
        "1. Não se apresente nem apresente a clínica: a relação já existe.\n"
        "2. Comece pelas áreas DESTA sessão: pergunte e confirme as áreas, sempre. O\n"
        "   que ela fez da última vez não diz o que ela quer agora.\n"
        "3. Não repita o valor sem ela perguntar.\n"
        "4. Não existe sessão marcada: não há o que remarcar ou cancelar. Se ela\n"
        "   falar em remarcar, é marcar uma nova.\n"
    ),
)

SKILLS = (PRIMEIRO_AGENDAMENTO, PACIENTE_COM_HORARIO, PACIENTE_SEM_HORARIO)
_POR_ESTADO = {estado: skill for skill in SKILLS for estado in skill.estados}


def despacha(estado: Optional[str]) -> Skill:
    """A skill do estado comercial. Estado desconhecido cai em
    PRIMEIRO_AGENDAMENTO: é a skill mais restrita (sem remarcar/cancelar) e a
    que pede e confirma tudo - errar para esse lado custa uma pergunta a
    mais, nunca uma sessão mexida por engano."""
    return _POR_ESTADO.get(estado or "", PRIMEIRO_AGENDAMENTO)
