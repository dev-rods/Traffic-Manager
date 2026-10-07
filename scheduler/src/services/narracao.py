# -*- coding: utf-8 -*-
"""O modelo escreveu o raciocínio como se fosse a resposta.

Em 06/10/2026 a Olivia recebeu:

    "Já sendo virilha completa + perianal, ela mencionou exatamente a
     *Virilha Completa + ânus*. Confirmando as áreas que você quer fazer: ..."

"Ela" é a própria Olivia. O modelo estava decidindo se precisava perguntar
sobre a região perianal (regra 5 de ÁREAS no prompt), concluiu que não, e
escreveu a conclusão para a paciente - em terceira pessoa, como quem fala com
outra pessoa sobre ela.

Medido: uma vez em 3020 mensagens desde 15/09. É variação do modelo, não
regressão. Mas uma vez é na conversa de alguém, e o padrão é detectável: a
resposta do bot nunca tem motivo legítimo para dizer "ela mencionou" ou "a
paciente quer" - ele fala COM a pessoa, não SOBRE ela.

Função pura, só texto. Quem decide o que fazer com o achado é o agente.
"""
import re
import unicodedata

# Sujeito em terceira pessoa que só pode ser a própria pessoa da conversa,
# seguido de verbo de fala ou de vontade. "A especialista vai te confirmar"
# não casa: o sujeito é outro. "Ela mencionou" casa.
_PADRAO = re.compile(
    r"\b(ela|a paciente|a pessoa|a cliente)\s+"
    r"(mencionou|disse|falou|pediu|quer|queria|informou|confirmou|escolheu|"
    r"respondeu|perguntou|citou|indicou|ja (disse|falou|mencionou|informou))\b"
)


def _plano(texto):
    return "".join(
        c for c in unicodedata.normalize("NFD", texto or "")
        if unicodedata.category(c) != "Mn"
    ).lower()


def narra_a_pessoa(texto):
    """O trecho em que a resposta fala da pessoa em terceira pessoa, ou None."""
    m = _PADRAO.search(_plano(texto))
    return m.group(0) if m else None
