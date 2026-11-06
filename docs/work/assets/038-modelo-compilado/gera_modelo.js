// Gera o modelo .docx COMPILADO para a ClickSign (PRD 038): o TCLE exatamente
// como está em produção (PRD 036, cabeçalho e cláusulas 1 a 20, byte a byte),
// seguido da Ficha de Anamnese - Epilação a Laser, Versão 03, e da cláusula
// de assinaturas do termo no fim do documento.
//
// Ficha Versão 03 = Versão 02 (revisão 09/2026) com três cortes, nada reescrito:
//   - seção 8 (exposição solar e condição atual da pele) sai: vira triagem por
//     sessão, fora deste documento;
//   - item 10.8 sem citar marca ("plataformas digitais legalmente reconhecidas");
//   - seção 11 (linhas de assinatura) sai do corpo: a assinatura é uma, no fim.
// Cada resposta da ficha é uma variável {{...}} ("Sim"/"Não", ou o texto; "-"
// quando vazio), preenchida pela API a partir das telas do iPad.
//
// Uso: node gera_modelo.js  (precisa do pacote `docx`, npm install docx)
// Saída: TCLE_anamnese_modelo_clicksign_<TCLE_VERSION>.docx na mesma pasta.

const fs = require('fs')
const path = require('path')
const {
  AlignmentType, BorderStyle, Document, Packer, Paragraph, TextRun,
} = require('docx')

const TCLE_VERSION = '2026-12'
const FONT = 'Arial'
const SIZE = 20 // 10 pt

const run = (text, opts = {}) => new TextRun({ text, font: FONT, size: SIZE, ...opts })
const variavel = (nome, opts = {}) => run(`{{${nome}}}`, opts)

const titulo = (text) => new Paragraph({
  alignment: AlignmentType.CENTER,
  spacing: { before: 0, after: 60 },
  children: [run(text, { bold: true, size: 26 })],
})

const secao = (text) => new Paragraph({
  spacing: { before: 200, after: 80 },
  keepNext: true,
  children: [run(text, { bold: true })],
})

const paragrafo = (...children) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  spacing: { before: 0, after: 80 },
  children: children.map((c) => (typeof c === 'string' ? run(c) : c)),
})

const item = (marca, text, nivel = 0) => new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  spacing: { before: 0, after: 40 },
  indent: { left: 540 + nivel * 400, hanging: 300 },
  children: [run(`${marca} ${text}`)],
})

const campo = (rotulo, nome) => new Paragraph({
  spacing: { before: 0, after: 60 },
  children: [run(`${rotulo}: `), variavel(nome)],
})

const linhaAssinatura = (rotulo) => [
  new Paragraph({
    spacing: { before: 480, after: 0 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: '000000', space: 1 } },
    children: [run('')],
  }),
  new Paragraph({ spacing: { before: 40, after: 120 }, children: [run(rotulo)] }),
]


// --- Ficha de anamnese (PRD 038) ---------------------------------------------
const pergunta = (texto, nome) => new Paragraph({
  spacing: { before: 0, after: 40 },
  indent: { left: 200 },
  children: [run(`${texto}  `), run('Resposta: '), variavel(nome, { bold: true })],
})
const detalhe = (rotulo, nome) => new Paragraph({
  spacing: { before: 0, after: 80 },
  indent: { left: 560 },
  children: [run(`${rotulo} `, { italics: true }), variavel(nome)],
})
const fichaTitulo = (text) => new Paragraph({
  alignment: AlignmentType.CENTER,
  pageBreakBefore: true,
  spacing: { before: 0, after: 160 },
  children: [run(text, { bold: true, size: 26 })],
})

const children = [
  titulo('TERMO DE CONSENTIMENTO LIVRE E ESCLARECIDO - TCLE'),
  titulo('PARA PROCEDIMENTO DE EPILAÇÃO A LASER -'),
  titulo('TECNOLOGIA SOPRANO ICE PLATINUM'),
  new Paragraph({ spacing: { before: 0, after: 160 }, children: [run('')] }),

  campo('Nome Completo', 'nome_completo'),
  campo('CPF', 'cpf'),
  campo('Data de nascimento', 'data_nascimento'),
  campo('Telefone para contato', 'telefone'),
  campo('E-mail', 'email'),
  new Paragraph({
    spacing: { before: 60, after: 60 },
    children: [run('Clínica: '), variavel('clinica_nome'), run(' - Profissional responsável: '),
      variavel('profissional_nome'), run(', '), variavel('profissional_titulo'), run(', '),
      variavel('profissional_registro')],
  }),

  secao('1. ESCLARECIMENTOS SOBRE O PROCEDIMENTO'),
  paragrafo('Fui devidamente informado(a) de que o procedimento de epilação a laser com a tecnologia Soprano Ice Platinum consiste na emissão de energia luminosa de forma gradual e contínua, com o objetivo de destruir progressivamente os folículos pilosos, promovendo a redução duradoura do crescimento dos pelos.'),
  paragrafo('Ressalto que este é um procedimento estético, eletivo e não terapêutico, realizado exclusivamente com finalidade cosmética, sem substituição de tratamento médico.'),

  secao('2. INFORMAÇÕES SOBRE A TECNOLOGIA'),
  paragrafo('A tecnologia Soprano Ice Platinum combina três comprimentos de onda simultâneos (755nm, 810nm e 1064nm), o que a torna eficaz em diferentes profundidades do folículo piloso e adequada para todos os fototipos de pele, inclusive bronzeadas. Trata-se de uma tecnologia segura, eficaz e que permite tratamento em qualquer época do ano, desde que cumpridos os cuidados recomendados.'),

  secao('3. POSSÍVEIS EFEITOS COLATERAIS E RISCOS'),
  paragrafo('Estou ciente de que, mesmo com os cuidados técnicos e protocolos recomendados, podem ocorrer efeitos adversos, como:'),
  item('a.', 'Sensação de calor, ardência ou pinicação durante ou após o procedimento;'),
  item('b.', 'Eritema (vermelhidão), edema perifolicular (inchaço leve), coceira intensa ou prolongada (prurido);'),
  item('c.', 'Formigamento ou dormência temporária na pele tratada;'),
  item('d.', 'Desenvolvimento de foliculite e pelos encravados pós-procedimento;'),
  item('e.', 'Pacientes com histórico de foliculite ou pelos encravados estão mais suscetíveis à recorrência, especialmente se não forem seguidas as recomendações pós-procedimento;'),
  item('f.', 'Em casos raros: manchas (hiper ou hipopigmentação), bolhas, crostas, queimaduras, formação de cicatrizes ou agravamento de doenças cutâneas pré-existentes;'),
  item('g.', 'Reações alérgicas a produtos utilizados durante ou após o procedimento, como géis, cremes ou anestésicos;'),
  item('h.', 'Reativação de herpes simplex em áreas predispostas (como região perioral ou genital);'),
  item('i.', 'Aumento transitório da acne, especialmente em áreas hormonais como rosto e pescoço;'),
  item('j.', 'Resultados variáveis conforme área tratada, tipo, cor e espessura do pelo, cor da pele, fatores hormonais, genéticos, uso de medicamentos e resposta individual ao tratamento.'),
  item('k.', 'Em casos raros, pode haver estímulo paradoxal de crescimento de pelos (hipertricose), especialmente em regiões hormonossensíveis ou em pacientes com predisposição genética;'),
  item('l.', 'Possibilidade de infecção secundária em casos de bolhas, feridas ou manipulação da área tratada sem cuidados adequados.'),

  secao('4. CUIDADOS PRÉ E PÓS-PROCEDIMENTO'),
  paragrafo('Fui orientado(a) a seguir rigorosamente as recomendações abaixo, com o objetivo de garantir a segurança, eficácia e conforto durante o tratamento:'),
  item('a.', 'Raspar com lâmina os pelos da região a ser tratada no dia anterior ou no mesmo dia da sessão, garantindo que não fiquem pontas aparentes;'),
  item('b.', 'Evitar exposição solar direta principalmente 5 dias antes e 5 dias após a sessão, utilizando protetor solar com FPS 30 ou superior diariamente nas áreas expostas;'),
  item('c.', 'Não utilizar métodos de remoção de pelos pela raiz, como cera, pinça ou depilador elétrico, durante todo o período de tratamento;'),
  item('d.', 'Não aplicar produtos descolorantes nos pelos da região a ser tratada;'),
  item('e.', 'Evitar procedimentos estéticos e dermatológicos agressivos na área tratada, necessário respeitar o intervalo mínimo de segurança entre os procedimentos, que pode variar conforme avaliação profissional;'),
  item('f.', 'Suspender o uso de produtos que contenham ácidos (retinóico, glicólico, salicílico, cremes depilatórios, entre outros), esfoliantes, perfumes, desodorantes ou cremes com potencial irritativo (à base de álcool, cânfora, mentol ou ativos desconhecidos) na semana anterior e na semana seguinte à sessão;'),
  item('g.', 'Manter boa higiene e hidratação constante das regiões tratadas. Sugestões de hidratantes pré e pós-laser: CeraVe®, Cetaphil®, Cicaplast®, Bepantol®;'),
  item('h.', 'Evitar banhos muito quentes e prolongados, uso de roupas justas e qualquer tipo de atrito nas áreas tratadas por pelo menos 7 dias após o procedimento;'),
  item('i.', 'O uso de maquiagem, desodorantes ou outros cosméticos na área tratada poderá ser retomado 24 a 48 horas após a sessão, desde que não haja irritação ou lesão na pele;'),
  item('j.', 'Evitar atividades físicas intensas por pelo menos 24h após a sessão para prevenir suor excessivo e irritação da pele;'),
  item('k.', 'Evitar o uso de sauna, piscina ou mar por pelo menos 48 horas após o procedimento;'),
  item('l.', 'Não coçar, manipular ou esfoliar a área tratada nos dias seguintes à sessão;'),
  item('m.', 'Comunicar previamente ao profissional qualquer condição relevante, como:'),
  item('i.', 'Uso de medicamentos fotossensibilizantes (como isotretinoína, antibióticos, entre outros);', 1),
  item('ii.', 'Presença de lesões, irritações, feridas, tatuagens na área a ser tratada;', 1),
  item('iii.', 'Histórico de herpes na região;', 1),
  item('iv.', 'Gestação, lactação ou suspeita de gravidez;', 1),
  item('v.', 'Doenças autoimunes ou imunossupressão.', 1),
  item('n.', 'O uso de gel ou creme anestésico pode ser indicado para minimizar desconfortos, sempre mediante orientação e autorização profissional.'),
  item('o.', 'Em casos de epilação na região íntima, deve-se evitar relações sexuais por pelo menos 48 horas após a sessão para prevenir irritações ou infecções locais;'),
  item('p.', 'Em caso de LEVE vermelhidão, LEVE sensação de calor ou LEVE inchaço, recomenda-se compressa fria e bastante creme hidratante como: CeraVe®, Cetaphil®, Cicaplast®, Bepantol®. Não aplicar pomadas ou medicamentos sem orientação profissional.'),
  item('q.', 'Evitar exposição à radiação ultravioleta artificial (bronzeamento artificial) antes e depois das sessões, pelo risco aumentado de queimaduras e hiperpigmentação.'),
  item('r.', 'Caso ocorra qualquer efeito adverso, como manchas, vermelhidão intensa e persistente, foliculite, bolhas, crostas, sensação de ardência prolongada ou qualquer outra alteração fora do padrão esperado, comprometo-me a:'),
  item('i.', 'Evitar completamente a exposição solar direta, bronzeamento artificial e contato com fontes de calor, como banhos quentes, secador, sauna ou vaporização facial, até que a pele recupere totalmente sua integridade;', 1),
  item('ii.', 'Não utilizar cosméticos, perfumes, desodorantes, cremes ou maquiagens na área afetada, a menos que orientado(a) especificamente pelo profissional responsável;', 1),
  item('iii.', 'Evitar qualquer tipo de automedicação, inclusive o uso de pomadas, cremes anti-inflamatórios, antibióticos ou corticóides sem prescrição;', 1),
  item('iv.', 'Comunicar imediatamente ao profissional responsável pelo tratamento, a fim de receber as orientações adequadas e, se necessário, ser encaminhado(a) a atendimento médico especializado.', 1),

  secao('5. CONTRAINDICAÇÕES'),
  paragrafo('Estou ciente de que o procedimento de epilação a laser não é recomendado nas seguintes situações:'),
  item('a.', 'Gestação e lactação (exceto com liberação médica formal);'),
  item('b.', 'Uso recente de isotretinoína (Roacutan) - necessária avaliação individual do tempo de uso, da dose utilizada e da data da última dose, contraindicação relativa. Na maioria dos casos, é necessária liberação médica formal.'),
  item('c.', 'Uso de medicamentos fotossensibilizantes;'),
  item('d.', 'Uso contínuo de anticoagulantes;'),
  item('e.', 'Presença de infecções ativas, feridas, dermatites ativas ou outras alterações cutâneas na área a ser tratada;'),
  item('f.', 'Histórico de epilepsia fotossensível;'),
  item('g.', 'Doenças autoimunes ou imunossupressão;'),
  item('h.', 'Distúrbios hormonais não controlados (contraindicação relativa);'),
  item('i.', 'Áreas não indicadas: pálpebra superior e interior das orelhas;'),
  item('j.', 'Regiões com tatuagens (procedimento não é realizado sobre elas);'),
  item('k.', 'Presença de prótese de silicone diretamente sob a área a ser tratada (ex.: seios, glúteos), em razão do risco térmico e de interferência com o material implantado.'),
  item('l.', 'Peelings superficiais ou uso de ácidos home care (cosméticos contendo ácidos para tratamentos de pele em casa): evitar nos 7 dias anteriores e posteriores;'),
  item('m.', 'Fotossensibilidade individual significativa;'),
  item('n.', 'Pelos brancos, muito claros ou loiros (com baixa ou nenhuma eficácia do procedimento);'),
  item('o.', 'Bronzeamento recente com sinais de sensibilização cutânea, como ardência, vermelhidão ou descamação. Nestes casos, o procedimento está contraindicado até que a pele esteja íntegra. Caso a pele esteja bronzeada, mas íntegra, o procedimento poderá ser realizado normalmente com os cuidados adequados;'),
  item('p.', 'Histórico de queloide ou cicatrização hipertrófica;'),
  item('q.', 'Diabetes descompensada;'),
  item('r.', 'Presença de lesões suspeitas, histórico de câncer de pele ou diagnóstico de lesões pigmentadas na área a ser tratada;'),
  item('s.', 'Procedimentos ablativos recentes na área a ser tratada, como laser de CO₂, luz intensa pulsada (LIP) ou peelings químicos médios e profundos - necessário respeitar o intervalo mínimo de segurança, evitar por 30 dias ou mais, conforme avaliação profissional;'),
  item('t.', 'Dermatite atópica ou psoríase na região a ser tratada - o procedimento será contraindicado somente na ausência de controle clínico, podendo ser realizado com liberação médica formal.'),
  item('u.', 'Presença de doença vascular periférica grave ou varizes avançadas na área a ser tratada - contraindicação relativa, sujeita à avaliação profissional;'),
  item('v.', 'Realização recente (últimos 7 a 30 dias) de procedimentos estéticos injetáveis ou estimuladores (toxina botulínica, bioestimuladores de colágeno, preenchedores, fios de PDO), especialmente nas áreas tratadas - contraindicação relativa, com necessidade de avaliação profissional.'),

  secao('6. DECLARAÇÕES E COMPROMISSOS'),
  item('a.', 'Declaro que não estou gestante nem amamentando no momento;'),
  item('b.', 'Autorizo o início do tratamento, mesmo ciente dos possíveis efeitos adversos;'),
  item('c.', 'Estou ciente de que o tratamento requer múltiplas sessões e que os resultados variam de acordo com fatores individuais;'),
  item('d.', 'Compreendo que não há garantia de remoção total e definitiva de todos os pelos;'),
  item('e.', 'Estou ciente de que o resultado da epilação a laser está diretamente relacionado à frequência e ao intervalo adequado entre as sessões, conforme orientação profissional;'),
  item('f.', 'Reconheço que a disciplina no comparecimento às sessões e o cumprimento dos intervalos recomendados são fatores determinantes para o sucesso do tratamento.'),
  item('g.', 'Estou ciente de que as sessões são vendidas de forma avulsa, ou seja, cada sessão é contratada individualmente, não sendo obrigatória a aquisição de pacotes.'),
  item('h.', 'Declaro estar ciente de que não é permitido realizar o procedimento sobre áreas com prótese de silicone implantada, e me comprometo a informar sobre qualquer implante previamente.'),
  item('i.', 'Após atingido um resultado considerado satisfatório, compreendo que o tratamento poderá ser encerrado, no entanto, estou ciente de que sessões periódicas de manutenção são recomendadas para preservar os efeitos alcançados e promover a durabilidade dos resultados obtidos.'),
  item('j.', 'Comprometo-me a informar, antes de cada sessão, qualquer alteração no meu estado de saúde, uso de medicamentos, realização de outros procedimentos estéticos ou dermatológicos, exposição solar ou qualquer outra condição que possa interferir na segurança do tratamento, especialmente se estiver presente alguma das contraindicações listadas neste termo.'),
  item('k.', 'Li, compreendi todas as cláusulas e esclareci todas as minhas dúvidas com o(a) profissional responsável antes da assinatura deste termo.'),

  secao('7. CLÁUSULA ESPECÍFICA PARA MENORES DE IDADE'),
  paragrafo('Em caso de cliente menor de 18 anos, este procedimento somente será realizado mediante autorização expressa do(a) responsável legal, o(a) qual declara estar plenamente ciente sobre o procedimento, seus riscos, benefícios, cuidados e contraindicações.'),
  paragrafo('Declaro, na qualidade de responsável legal, que autorizo a realização do procedimento estético de depilação a laser com a tecnologia Soprano Ice Platinum no(a) menor: ', variavel('menor_nome'), ', assumindo total responsabilidade pela decisão e acompanhamento do tratamento.'),
  paragrafo('Responsável legal: ', variavel('responsavel_nome'), ' - CPF: ', variavel('responsavel_cpf')),

  secao('8. AUTORIZAÇÃO DE USO DE IMAGEM (OPCIONAL)'),
  paragrafo(variavel('autoriza_imagem'), ' o uso de imagem da área tratada ou minhas para fins de acompanhamento clínico, estudo de caso, marketing ou divulgação científica/técnica.'),

  secao('9. SIGILO E PROTEÇÃO DE DADOS (LGPD)'),
  paragrafo('Declaro estar ciente de que meus dados pessoais e clínicos serão armazenados com segurança, de forma confidencial, e utilizados exclusivamente para fins assistenciais, conforme determina a Lei Geral de Proteção de Dados (LGPD - Lei nº 13.709/2018).'),

  secao('10. DECLARAÇÃO DE VERACIDADE DOS DADOS'),
  paragrafo('Declaro, sob responsabilidade, que todas as informações fornecidas neste documento e durante minha anamnese são verdadeiras e completas. Estou ciente de que omitir informações relevantes pode comprometer minha segurança e os resultados do tratamento.'),

  secao('11. CIÊNCIA SOBRE INTERCORRÊNCIAS E CONDUTA MÉDICA'),
  paragrafo('Estou ciente de que, em caso de intercorrências, serei prontamente avaliado(a) pela profissional responsável, podendo ser orientado(a) ou encaminhado(a) para acompanhamento médico adequado, conforme a natureza da situação apresentada. Em casos necessários, poderei ser convocado(a) para retorno para avaliação presencial da intercorrência.'),

  secao('12. ASSINATURA DIGITAL'),
  paragrafo('Este documento poderá ser assinado fisicamente ou por meio de plataformas digitais legalmente reconhecidas, garantindo validade jurídica e integridade do conteúdo.'),

  secao('13. VALIDADE DO TERMO'),
  paragrafo('Este termo de consentimento é válido durante todo o plano de tratamento proposto, incluindo as sessões futuras, desde que não haja alteração relevante no estado de saúde do(a) cliente, como início de novo tratamento médico, uso de medicamentos fotossensibilizantes, gravidez, exposição solar excessiva ou qualquer condição que possa comprometer a segurança do procedimento.'),
  paragrafo('Quaisquer alterações devem ser obrigatoriamente comunicadas à profissional responsável antes da realização da próxima sessão.'),

  secao('14. DIREITO DE REVOGAÇÃO DO CONSENTIMENTO'),
  paragrafo('O(a) cliente tem o direito de revogar este termo a qualquer momento, mediante manifestação expressa e formal. No entanto, fica ciente de que essa revogação não exime o pagamento pelas sessões já realizadas até a data da solicitação.'),

  secao('15. REGISTRO DO TRATAMENTO E DO PRONTUÁRIO INDIVIDUAL'),
  paragrafo('Declaro estar ciente de que todas as sessões realizadas serão registradas em prontuário individual, contendo:'),
  item('a.', 'Dados técnicos do procedimento (parâmetros utilizados);'),
  item('b.', 'Observações complementares;'),
  item('c.', 'Data das sessões realizadas;'),
  item('d.', 'Nome do(a) profissional que executou o procedimento;'),
  item('e.', 'Registros fotográficos das áreas tratadas, quando autorizado expressamente.'),
  paragrafo('Tais registros têm a finalidade de acompanhar a evolução do tratamento, documentar condutas e oferecer segurança ao atendimento.'),

  secao('16. CIÊNCIA SOBRE EXPECTATIVAS ESTÉTICAS'),
  paragrafo('Declaro estar ciente de que os resultados do procedimento são progressivos e variáveis, e que eventuais insatisfações subjetivas não caracterizam falha técnica ou erro profissional. A não obtenção de resultado estético esperado não gera, por si só, obrigação de reembolso, compensação ou ressarcimento.'),

  secao('17. AUSÊNCIA DE VÍNCULO CONTÍNUO DE SERVIÇOS'),
  paragrafo('Declaro estar ciente de que este procedimento é prestado por profissional habilitado(a) e não configura relação de emprego, vínculo contratual contínuo ou obrigação de continuidade de atendimento. Cada sessão é contratada de forma pontual e individualizada, de acordo com minha livre escolha.'),

  secao('18. ISENÇÃO DE RESPONSABILIDADE POR OMISSÃO DE INFORMAÇÕES'),
  paragrafo('Estou ciente de que qualquer omissão de informações clínicas, uso de medicamentos, condições de saúde ou hábitos que possam interferir na segurança do procedimento isenta a profissional de responsabilidade por intercorrências decorrentes dessas omissões. Comprometo-me a fornecer informações completas e verdadeiras antes de cada sessão.'),

  secao('19. LIMITAÇÃO DE ÁREAS ATENDIDAS'),
  paragrafo('Declaro estar ciente de que o procedimento de epilação a laser com a tecnologia Soprano Ice Platinum não será realizado em pessoas com genitália externa masculina nas seguintes regiões: mucosa anal, genitais e região interglútea (parte interna das nádegas). Tais áreas não fazem parte do escopo de atendimento por razões técnicas, éticas e de segurança, independentemente da identidade de gênero.'),

  secao('20. FORO'),
  paragrafo('Para dirimir quaisquer dúvidas, litígios ou controvérsias oriundas deste termo, fica eleito o foro da Comarca de São Paulo - SP, com renúncia a qualquer outro, por mais privilegiado que seja.'),


  // ======================= FICHA DE ANAMNESE - VERSÃO 03 =======================
  fichaTitulo('FICHA DE ANAMNESE - EPILAÇÃO A LASER'),
  campo('Nome completo', 'nome_completo'),
  campo('CPF', 'cpf'),
  campo('Data de nascimento', 'data_nascimento'),
  campo('Telefone para contato', 'telefone'),
  campo('E-mail', 'email'),
  new Paragraph({
    spacing: { before: 60, after: 120 },
    children: [run('Clínica: '), variavel('clinica_nome'), run(' - Profissional responsável: '),
      variavel('profissional_nome'), run(', '), variavel('profissional_titulo'), run(', '),
      variavel('profissional_registro')],
  }),

  secao('1. QUEIXA PRINCIPAL'),
  paragrafo('O que motivou a busca pelo procedimento?'),
  detalhe('', 'queixa_principal'),
  paragrafo(run('Assinale a alternativa correspondente e detalhe quando solicitado.', { bold: true })),

  secao('2. HISTÓRICO MÉDICO'),
  pergunta('Está gestante?', 'gestante'),
  pergunta('Está amamentando?', 'amamentando'),
  pergunta('Possui distúrbios hormonais?', 'hormonal'),
  detalhe('Se sim, quais?', 'hormonal_quais'),
  pergunta('Possui doenças de pele, como herpes, dermatite ou psoríase?', 'doenca_pele'),
  detalhe('Se sim, quais?', 'doenca_pele_quais'),
  pergunta('A condição encontra-se controlada?', 'doenca_pele_controlada'),
  pergunta('Possui alguma doença autoimune?', 'autoimune'),
  detalhe('Se sim, qual?', 'autoimune_qual'),
  pergunta('Possui alguma condição de imunossupressão?', 'imunossupressao'),
  pergunta('Possui epilepsia?', 'epilepsia'),
  pergunta('Possui câncer ativo ou já realizou tratamento oncológico?', 'cancer'),
  detalhe('Se sim, informe qual tratamento e quando ocorreu:', 'cancer_detalhe'),
  pergunta('Possui diabetes?', 'diabetes'),
  detalhe('Se sim, a condição está controlada?', 'diabetes_controlada'),
  pergunta('Possui alguma alergia conhecida?', 'alergia'),
  detalhe('Se sim, qual(is)?', 'alergia_quais'),

  secao('3. USO DE MEDICAMENTOS'),
  pergunta('Faz uso de algum medicamento atualmente?', 'medicamento'),
  detalhe('Se sim, informe o nome e, se souber, a dose:', 'medicamento_quais'),
  pergunta('Fez ou faz uso de isotretinoína (Roacutan®)?', 'isotretinoina'),
  detalhe('Se sim, informe a data da última dose:', 'isotretinoina_ultima_dose'),
  pergunta('Fez uso de medicamentos fotossensibilizantes recentemente?', 'fotossensibilizante'),
  detalhe('Se sim, quais?', 'fotossensibilizante_quais'),
  pergunta('Faz uso de minoxidil ou de algum medicamento para estimular o crescimento dos pelos ou cabelos?', 'minoxidil'),
  detalhe('Se sim, qual?', 'minoxidil_qual'),

  secao('4. INFORMAÇÕES DERMATOLÓGICAS'),
  pergunta('Possui tatuagens na área que poderá ser tratada?', 'tatuagem'),
  pergunta('Realizou peeling na região que poderá ser tratada nos últimos 30 dias?', 'peeling_30d'),
  pergunta('Realizou depilação com cera, pinça ou linha nos últimos 30 dias?', 'cera_30d'),
  pergunta('Tem histórico de foliculite ou pelos encravados?', 'foliculite'),
  pergunta('Tem histórico de herpes na região que poderá ser tratada?', 'herpes_area'),
  pergunta('Tem silicone na área que poderá ser tratada?', 'silicone'),
  pergunta('Realizou procedimentos estéticos ou dermatológicos na área que poderá ser tratada nos últimos 30 dias?', 'procedimentos_30d'),
  detalhe('Se sim, quais?', 'procedimentos_30d_quais'),
  pergunta('Possui tendência a queloide ou cicatrização hipertrófica?', 'queloide'),
  pergunta('Faz uso de cosméticos com ácidos na área que poderá ser tratada, como retinol, ácido glicólico ou ácido salicílico?', 'acidos'),
  detalhe('Se sim, quais?', 'acidos_quais'),
  pergunta('Possui feridas, inflamações, infecções ou lesões ativas na pele?', 'lesao_ativa'),
  detalhe('Se sim, quais?', 'lesao_ativa_quais'),

  secao('5. HÁBITOS E ESTILO DE VIDA'),
  pergunta('Pratica atividade física?', 'atividade_fisica'),
  detalhe('Se sim, qual tipo e qual frequência?', 'atividade_fisica_detalhe'),
  pergunta('Fuma?', 'fuma'),
  pergunta('Consome bebidas alcoólicas?', 'alcool'),
  pergunta('Está sob acompanhamento médico ou em tratamento atualmente?', 'acompanhamento_medico'),
  detalhe('Se sim, qual(is)?', 'acompanhamento_medico_quais'),

  secao('6. OUTRAS INFORMAÇÕES RELEVANTES'),
  pergunta('Já realizou epilação a laser anteriormente?', 'laser_antes'),
  detalhe('Se sim, houve alguma reação ou intercorrência? Qual(is)?', 'laser_antes_reacao'),
  detalhe('Sabe informar uma média de quantas sessões realizou e qual equipamento foi utilizado?', 'laser_antes_sessoes'),

  secao('7. OBSERVAÇÕES ADICIONAIS (OPCIONAL)'),
  detalhe('', 'observacoes'),

  secao('8. CLASSIFICAÇÃO DE FOTOTIPO - AUTODECLARAÇÃO'),
  paragrafo(run('Considerando como sua pele normalmente reage à exposição solar, assinale com "X" apenas uma opção:', { bold: true })),
  item('I -', 'Pele muito clara, queima facilmente e nunca bronzeia.'),
  item('II -', 'Pele clara, queima facilmente e bronzeia minimamente.'),
  item('III -', 'Pele clara média, queima um pouco e bronzeia gradualmente.'),
  item('IV -', 'Pele morena média, raramente queima e bronzeia com facilidade.'),
  item('V -', 'Pele morena escura, quase nunca queima e bronzeia intensamente.'),
  item('VI -', 'Pele negra, nunca queima e bronzeia intensamente.'),
  paragrafo('Fototipo assinalado: ', variavel('fototipo', { bold: true })),

  secao('9. DECLARAÇÕES E CIÊNCIA'),
  item('9.1', 'Declaro, sob responsabilidade, que as informações prestadas nesta ficha são verdadeiras e completas, estando ciente de que qualquer omissão pode comprometer a segurança e os resultados do procedimento estético.'),
  item('9.2', 'Estou ciente de que, mesmo com todos os cuidados, podem ocorrer intercorrências como vermelhidão, ardência, edema, foliculite, pelos encravados e etc., e que receberei a conduta adequada, caso necessário.'),
  item('9.3', 'Declaro que li e compreendi as contraindicações e riscos associados à epilação a laser, tendo sido devidamente orientado(a).'),
  item('9.4', 'Confirmo que todas as minhas dúvidas foram esclarecidas previamente.'),
  item('9.5', 'Estou ciente de que os dados informados nesta ficha são confidenciais, protegidos pela Lei Geral de Proteção de Dados (Lei 13.709/2018).'),
  item('9.6', 'Tenho ciência de que as sessões de epilação a laser são contratadas de forma avulsa, conforme minha necessidade e indicação profissional.'),
  item('9.7', 'Estou ciente de que o equipamento utilizado (Soprano Ice Platinum) permite aplicação em pele bronzeada apenas se a pele estiver íntegra, sem vermelhidão, descamação ou ardência.'),
  item('9.8', 'Este documento poderá ser assinado fisicamente ou por meio de plataformas digitais legalmente reconhecidas, garantindo sua validade jurídica.'),
  item('9.9', 'Comprometo-me a informar, antes das próximas sessões, qualquer alteração relevante em meu estado de saúde, gestação, uso de medicamentos ou condição da pele.'),
  new Paragraph({
    spacing: { before: 120, after: 0 },
    children: [run('Ficha de Anamnese - Epilação a Laser | Versão 03 | Revisão: 11/2026', { size: 16, color: '666666' })],
  }),

  // ======================= ASSINATURA (cláusula 21 do TCLE) ====================
  secao('21. ASSINATURAS'),
  paragrafo('Local: ', variavel('cidade'), '          Data: ', variavel('data')),
  paragrafo('Profissional responsável: ', variavel('profissional_nome'), ', ', variavel('profissional_titulo'), ', ', variavel('profissional_registro')),
  new Paragraph({ spacing: { before: 480, after: 0 }, children: [run('{{~position_sign_1}}')] }),
  ...linhaAssinatura('Assinatura do(a) cliente ou do(a) responsável legal (se aplicável)'),
  paragrafo('Signatário(a): ', variavel('signatario_nome'), ' - CPF: ', variavel('signatario_cpf')),
  new Paragraph({
    spacing: { before: 240, after: 0 },
    children: [run(`Versão do documento: ${TCLE_VERSION} (TCLE 2026-11 + Ficha de Anamnese V03)`, { size: 16, color: '666666' })],
  }),
]

const doc = new Document({
  creator: 'Traffic Manager',
  title: 'TCLE e Ficha de Anamnese - Epilação a laser Soprano Ice Platinum',
  styles: { default: { document: { run: { font: FONT, size: SIZE } } } },
  sections: [{
    properties: { page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    children,
  }],
})

const saida = path.join(__dirname, `TCLE_anamnese_modelo_clicksign_${TCLE_VERSION}.docx`)
Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(saida, buf)
  console.log(`gerado: ${saida}`)
})
