# -*- coding: utf-8 -*-
"""Ficha de anamnese respondida no check-in do iPad (PRD 038).

Este módulo é o catálogo ÚNICO das perguntas: chave, tela, texto, tipo,
condicional e alerta. Dele saem, nesta ordem, o que o iPad renderiza
(`catalogo`), a validação do que volta (`valida_tela`, `valida_completa`), as
variáveis do modelo compilado da ClickSign (`variaveis`) e os alertas que o
painel mostra à profissional (`alertas`). As chaves são as mesmas do gerador
`docs/work/assets/038-modelo-compilado/gera_modelo.js`, e um teste confere.

Regras herdadas do PRD 014 e mantidas no 038:

- Alertas são EXIBIDOS, nunca interpretados: nada aqui bloqueia sessão.
- O fototipo é autodeclarado e nunca escreve `patients.skin_type`.
- Nenhuma tool do bot lê ou escreve respostas.
"""
import re
from typing import Any, Dict, List, NamedTuple, Optional

VERSAO_DA_FICHA = "03"
SIM_NAO, TEXTO, FOTOTIPO = "SIM_NAO", "TEXTO", "FOTOTIPO"
FOTOTIPOS = ("I", "II", "III", "IV", "V", "VI")
TAMANHO_DO_TEXTO = 300
TELAS = (1, 2, 3, 4)
VAZIO = "-"


class AnamneseInvalida(Exception):
    def __init__(self, mensagem: str, campo: Optional[str] = None):
        super().__init__(mensagem)
        self.campo = campo


class Pergunta(NamedTuple):
    chave: str
    tela: int
    secao: str
    texto: str
    tipo: str = SIM_NAO
    condicional_de: Optional[str] = None
    rotulo: Optional[str] = None
    obrigatoria: bool = True
    alerta: Optional[str] = None  # rótulo do alerta quando a resposta é Sim


S1, S2, S3, S4, S5, S6, S7, S8 = (
    "1. Queixa principal", "2. Histórico médico", "3. Uso de medicamentos",
    "4. Informações dermatológicas", "5. Hábitos e estilo de vida",
    "6. Outras informações relevantes", "7. Observações adicionais",
    "8. Classificação de fototipo (autodeclaração)",
)

PERGUNTAS = (
    # Tela 1: queixa + histórico médico
    Pergunta("queixa_principal", 1, S1, "O que motivou a busca pelo procedimento?", TEXTO),
    Pergunta("gestante", 1, S2, "Está gestante?", alerta="Gestante"),
    Pergunta("amamentando", 1, S2, "Está amamentando?", alerta="Amamentando"),
    Pergunta("hormonal", 1, S2, "Possui distúrbios hormonais?"),
    Pergunta("hormonal_quais", 1, S2, "Quais?", TEXTO, "hormonal", "Se sim, quais?"),
    Pergunta("doenca_pele", 1, S2, "Possui doenças de pele, como herpes, dermatite ou psoríase?"),
    Pergunta("doenca_pele_quais", 1, S2, "Quais?", TEXTO, "doenca_pele", "Se sim, quais?"),
    Pergunta("doenca_pele_controlada", 1, S2, "A condição encontra-se controlada?", SIM_NAO, "doenca_pele"),
    Pergunta("autoimune", 1, S2, "Possui alguma doença autoimune?"),
    Pergunta("autoimune_qual", 1, S2, "Qual?", TEXTO, "autoimune", "Se sim, qual?"),
    Pergunta("imunossupressao", 1, S2, "Possui alguma condição de imunossupressão?", alerta="Imunossupressão"),
    Pergunta("epilepsia", 1, S2, "Possui epilepsia?", alerta="Epilepsia"),
    Pergunta("cancer", 1, S2, "Possui câncer ativo ou já realizou tratamento oncológico?",
             alerta="Câncer ativo ou tratamento oncológico"),
    Pergunta("cancer_detalhe", 1, S2, "Qual tratamento e quando ocorreu?", TEXTO, "cancer",
             "Se sim, informe qual tratamento e quando ocorreu:"),
    Pergunta("diabetes", 1, S2, "Possui diabetes?"),
    Pergunta("diabetes_controlada", 1, S2, "A condição está controlada?", SIM_NAO, "diabetes"),
    Pergunta("alergia", 1, S2, "Possui alguma alergia conhecida?"),
    Pergunta("alergia_quais", 1, S2, "Quais?", TEXTO, "alergia", "Se sim, qual(is)?"),
    # Tela 2: medicamentos
    Pergunta("medicamento", 2, S3, "Faz uso de algum medicamento atualmente?"),
    Pergunta("medicamento_quais", 2, S3, "Nome e, se souber, dose", TEXTO, "medicamento",
             "Se sim, informe o nome e, se souber, a dose:"),
    Pergunta("isotretinoina", 2, S3, "Fez ou faz uso de isotretinoína (Roacutan®)?", alerta="Isotretinoína (Roacutan®)"),
    Pergunta("isotretinoina_ultima_dose", 2, S3, "Data da última dose", TEXTO, "isotretinoina",
             "Se sim, informe a data da última dose:"),
    Pergunta("fotossensibilizante", 2, S3, "Fez uso de medicamentos fotossensibilizantes recentemente?",
             alerta="Medicamento fotossensibilizante"),
    Pergunta("fotossensibilizante_quais", 2, S3, "Quais?", TEXTO, "fotossensibilizante", "Se sim, quais?"),
    Pergunta("minoxidil", 2, S3,
             "Faz uso de minoxidil ou de algum medicamento para estimular o crescimento dos pelos ou cabelos?"),
    Pergunta("minoxidil_qual", 2, S3, "Qual?", TEXTO, "minoxidil", "Se sim, qual?"),
    # Tela 3: dermatológicas
    Pergunta("tatuagem", 3, S4, "Possui tatuagens na área que poderá ser tratada?", alerta="Tatuagem na área"),
    Pergunta("peeling_30d", 3, S4, "Realizou peeling na região que poderá ser tratada nos últimos 30 dias?",
             alerta="Peeling nos últimos 30 dias"),
    Pergunta("cera_30d", 3, S4, "Realizou depilação com cera, pinça ou linha nos últimos 30 dias?",
             alerta="Cera, pinça ou linha nos últimos 30 dias"),
    Pergunta("foliculite", 3, S4, "Tem histórico de foliculite ou pelos encravados?"),
    Pergunta("herpes_area", 3, S4, "Tem histórico de herpes na região que poderá ser tratada?",
             alerta="Herpes na área"),
    Pergunta("silicone", 3, S4, "Tem silicone na área que poderá ser tratada?"),
    Pergunta("procedimentos_30d", 3, S4,
             "Realizou procedimentos estéticos ou dermatológicos na área que poderá ser tratada nos últimos 30 dias?"),
    Pergunta("procedimentos_30d_quais", 3, S4, "Quais?", TEXTO, "procedimentos_30d", "Se sim, quais?"),
    Pergunta("queloide", 3, S4, "Possui tendência a queloide ou cicatrização hipertrófica?",
             alerta="Queloide ou cicatrização hipertrófica"),
    Pergunta("acidos", 3, S4,
             "Faz uso de cosméticos com ácidos na área que poderá ser tratada, como retinol, ácido glicólico ou ácido salicílico?"),
    Pergunta("acidos_quais", 3, S4, "Quais?", TEXTO, "acidos", "Se sim, quais?"),
    Pergunta("lesao_ativa", 3, S4, "Possui feridas, inflamações, infecções ou lesões ativas na pele?",
             alerta="Lesão ativa na pele"),
    Pergunta("lesao_ativa_quais", 3, S4, "Quais?", TEXTO, "lesao_ativa", "Se sim, quais?"),
    # Tela 4: hábitos, outras, observações, fototipo
    Pergunta("atividade_fisica", 4, S5, "Pratica atividade física?"),
    Pergunta("atividade_fisica_detalhe", 4, S5, "Tipo e frequência", TEXTO, "atividade_fisica",
             "Se sim, qual tipo e qual frequência?"),
    Pergunta("fuma", 4, S5, "Fuma?"),
    Pergunta("alcool", 4, S5, "Consome bebidas alcoólicas?"),
    Pergunta("acompanhamento_medico", 4, S5, "Está sob acompanhamento médico ou em tratamento atualmente?"),
    Pergunta("acompanhamento_medico_quais", 4, S5, "Quais?", TEXTO, "acompanhamento_medico", "Se sim, qual(is)?"),
    Pergunta("laser_antes", 4, S6, "Já realizou epilação a laser anteriormente?"),
    Pergunta("laser_antes_reacao", 4, S6, "Reação ou intercorrência", TEXTO, "laser_antes",
             "Se sim, houve alguma reação ou intercorrência? Qual(is)?", obrigatoria=False),
    Pergunta("laser_antes_sessoes", 4, S6, "Sessões e equipamento", TEXTO, "laser_antes",
             "Sabe informar uma média de quantas sessões realizou e qual equipamento foi utilizado?",
             obrigatoria=False),
    Pergunta("observacoes", 4, S7, "Observações adicionais", TEXTO, obrigatoria=False),
    Pergunta("fototipo", 4, S8, "Considerando como sua pele normalmente reage à exposição solar, assinale uma opção:",
             FOTOTIPO),
)

POR_CHAVE = {p.chave: p for p in PERGUNTAS}
CHAVES = tuple(p.chave for p in PERGUNTAS)

# Alerta composto: diabetes sem controle. Os simples vêm de `Pergunta.alerta`.
ALERTA_DIABETES = ("diabetes_nao_controlada", "Diabetes não controlada")

OPCOES_DE_FOTOTIPO = (
    ("I", "Pele muito clara, queima facilmente e nunca bronzeia."),
    ("II", "Pele clara, queima facilmente e bronzeia minimamente."),
    ("III", "Pele clara média, queima um pouco e bronzeia gradualmente."),
    ("IV", "Pele morena média, raramente queima e bronzeia com facilidade."),
    ("V", "Pele morena escura, quase nunca queima e bronzeia intensamente."),
    ("VI", "Pele negra, nunca queima e bronzeia intensamente."),
)


def catalogo() -> Dict[str, Any]:
    """O que o iPad renderiza. Sem a flag de alerta: o painel recebe os
    alertas prontos, o iPad não precisa saber."""
    telas = []
    for n in TELAS:
        telas.append({"n": n, "questions": [
            {"key": p.chave, "text": p.texto, "type": p.tipo, "conditionalOf": p.condicional_de,
             "label": p.rotulo, "required": p.obrigatoria, "section": p.secao}
            for p in PERGUNTAS if p.tela == n
        ]})
    return {"version": VERSAO_DA_FICHA, "screens": telas,
            "phototypes": [{"value": v, "text": t} for v, t in OPCOES_DE_FOTOTIPO]}


def _habilitada(p: Pergunta, respostas: Dict[str, Any]) -> bool:
    return p.condicional_de is None or respostas.get(p.condicional_de) is True


def _normaliza(p: Pergunta, valor: Any) -> Any:
    if p.tipo == SIM_NAO:
        if isinstance(valor, bool):
            return valor
        if isinstance(valor, str) and valor.strip().lower() in ("sim", "true", "não", "nao", "false"):
            return valor.strip().lower() in ("sim", "true")
        raise AnamneseInvalida("Responda Sim ou Não.", p.chave)
    if p.tipo == FOTOTIPO:
        v = str(valor or "").strip().upper()
        if v not in FOTOTIPOS:
            raise AnamneseInvalida("Escolha o fototipo (I a VI).", p.chave)
        return v
    texto = " ".join(str(valor or "").split())
    if len(texto) > TAMANHO_DO_TEXTO:
        raise AnamneseInvalida("Texto longo demais (máximo {} caracteres).".format(TAMANHO_DO_TEXTO), p.chave)
    if p.chave == "isotretinoina_ultima_dose" and texto and not re.match(r"^(\d{2}/)?\d{2}/\d{4}$", texto):
        raise AnamneseInvalida("Informe a data como dd/mm/aaaa ou mm/aaaa.", p.chave)
    return texto


def valida_tela(tela: int, respostas: Dict[str, Any]) -> Dict[str, Any]:
    """Normaliza e valida as respostas de UMA tela. Devolve só as chaves da
    tela: condicionais desabilitadas são descartadas, obrigatórias faltando
    levantam `AnamneseInvalida` com o campo."""
    if tela not in TELAS:
        raise AnamneseInvalida("Tela inválida.", "screen")
    if not isinstance(respostas, dict):
        raise AnamneseInvalida("Respostas inválidas.")
    limpas = {}  # type: Dict[str, Any]
    # Primeiro as Sim/Não e o fototipo, porque as condicionais dependem delas.
    for p in PERGUNTAS:
        if p.tela != tela or p.tipo == TEXTO:
            continue
        if p.condicional_de and not _habilitada(p, {**respostas, **limpas}):
            continue
        if p.chave not in respostas or respostas.get(p.chave) in (None, ""):
            raise AnamneseInvalida("Responda esta pergunta.", p.chave)
        limpas[p.chave] = _normaliza(p, respostas[p.chave])
    for p in PERGUNTAS:
        if p.tela != tela or p.tipo != TEXTO:
            continue
        if not _habilitada(p, limpas):
            continue
        texto = _normaliza(p, respostas.get(p.chave))
        if p.obrigatoria and not texto:
            raise AnamneseInvalida("Preencha este campo.", p.chave)
        limpas[p.chave] = texto
    return limpas


def valida_completa(respostas: Dict[str, Any]) -> Dict[str, Any]:
    """As quatro telas juntas. É o que `consentimento.inicia` exige antes de
    abrir o envelope."""
    if not isinstance(respostas, dict):
        raise AnamneseInvalida("Responda a ficha de anamnese antes de assinar.")
    completas = {}  # type: Dict[str, Any]
    for tela in TELAS:
        completas.update(valida_tela(tela, respostas))
    return completas


def completa(respostas: Optional[Dict[str, Any]]) -> bool:
    try:
        valida_completa(respostas or {})
        return True
    except AnamneseInvalida:
        return False


def variaveis(respostas: Dict[str, Any]) -> Dict[str, str]:
    """Uma variável do modelo por pergunta, sempre as 50: "Sim"/"Não", o
    texto, o fototipo, ou "-" quando não se aplica."""
    saida = {}
    for p in PERGUNTAS:
        v = respostas.get(p.chave)
        if p.tipo == SIM_NAO:
            saida[p.chave] = "Sim" if v is True else ("Não" if v is False else VAZIO)
        elif p.tipo == FOTOTIPO:
            saida[p.chave] = str(v) if v else VAZIO
        else:
            saida[p.chave] = str(v).strip() if v else VAZIO
    return saida


def alertas(respostas: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Os "Sim" que mudam a conduta, na ordem da ficha. Exibidos, nunca
    interpretados."""
    if not respostas:
        return []
    saida = []
    for p in PERGUNTAS:
        if p.alerta and respostas.get(p.chave) is True:
            saida.append({"key": p.chave, "label": p.alerta})
        if p.chave == "diabetes" and respostas.get("diabetes") is True and respostas.get("diabetes_controlada") is False:
            saida.append({"key": ALERTA_DIABETES[0], "label": ALERTA_DIABETES[1]})
    return saida
