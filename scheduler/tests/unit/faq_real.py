# -*- coding: utf-8 -*-
"""O FAQ real da Essencia, copiado de producao em 25/09/2026.

O teste da busca roda contra ESTE conteudo, e nao contra um FAQ inventado.
A conversa que motivou a correcao (23/09) falhou justamente por causa da
forma dos titulos reais: 'Posso fazer menstruada?' perde para itens do topo
quando a busca pesa 'pode' e 'fazer' igual a 'menstruada'.
"""

FAQ_ESSENCIA = [
    {
        'question_label':
            'Depilação a Laser dói?',
        'answer':
            'O Soprano Ice Platinum possui a ponteira de safira com exclusivo sistema de resfriamento simultâneo, atingindo -3°C. Logo, é o laser mais indolor do mercado.',
        'display_order': 1,
    },
    {
        'question_label':
            'O resultado é definitivo?',
        'answer':
            'Os resultados são duradouros, mas é importante entender que cada organismo reage de forma única. A quantidade de sessões necessárias e a manutenção dos resultados podem variar de acordo com fatores como:\n\n• Influência hormonal: alterações hormonais (como  puberdade, gravidez ou disfunções endócrinas) podem estimular o crescimento de novos pelos.\n• Individualidade biológica: cada pessoa possui características próprias de pele, tipo de pelo e metabolismo que impactam na resposta ao tratamento.\n• Fatores externos: uso de determinados medicamentos, variações de saúde ou estilo de vida também podem interferir.\n\nDe forma geral, os pelos já eliminados pelo laser não voltam a crescer. Porém, para garantir a manutenção dos resultados ao longo do tempo, recomendamos sessões de manutenção duas vezes por ano.',
        'display_order': 2,
    },
    {
        'question_label':
            'Quais são as principais contraindicações?',
        'answer':
            '• Gestantes e lactantes (salvo com liberação médica)\n• Uso recente de isotretinoína (Roacutan) – é necessário um intervalo de 6 meses ou liberação médica\n• Uso de medicamentos fotossensibilizantes ou anticoagulantes\n• Infecções, feridas ou doenças de pele ativas na região\n• Epilepsia fotossensível, doenças autoimunes ou imunossupressão\n• Regiões como pálpebras, orelhas internas ou sobre próteses de silicone não são tratadas\n• Bronzeamento recente com sinais de irritação – vermelhidão, ardência, sensibilidade ao toque ou calor, descamação\n• Cicatrização difícil, diabetes descompensada, lesões suspeitas, entre outros\n• Aplicação sobre queloides\n• Peelings recentes na área a ser tratada (7-21 dias)\n• Sobre tatuagens\n• Pelos brancos e muito claros. Ex: loiros (ineficaz)\n• Distúrbio hormonal não controlado (relativo)',
        'display_order': 3,
    },
    {
        'question_label':
            'Precisa de cuidados antes ou depois?',
        'answer':
            'Sim. As principais recomendações são:\n\n• Raspe os pelos com lâmina no dia anterior ou no mesmo dia da sessão.\n• Evite exposição solar por no mínimo 5 dias antes e depois da aplicação. Sempre use protetor solar (FPS 30 ou mais).\n• Durante todo o tratamento, evite métodos que removem o pelo pela raiz (cera, pinça, etc.).\n• Não use descolorantes nos pelos da área tratada.\n• Suspenda o uso de ácidos, esfoliantes, cremes depilatórios e perfumes na semana anterior e posterior à sessão.\n• Evite peelings ou outros procedimentos dermatológicos agressivos na área 2 semanas antes e depois.\n• Mantenha a pele bem limpa e hidratada. Sugestões de hidratantes: CeraVe®, Cetaphil®, Cicaplast® ou Bepantol®.\n• Evite roupas apertadas, banhos muito quentes, atritos e suor excessivo por até 7 dias após a sessão.\n• Maquiagens, desodorantes e cosméticos podem ser usados novamente entre 24 e 48h após a sessão (caso não haja irritações).\n• Evite exercícios  intensos por 24h, e o uso de piscina, sauna ou mar por 48h.\n• Em caso de vermelhidão leve ou inchaço, utilize compressa fria ou hidratante calmante.\n• Não aplique pomadas ou remédios por conta própria – fale conosco primeiro!\n• Se a sessão for em região íntima, evite relações sexuais por 48h.\n\nAtenção: nos avise antes da sessão caso:\n• Esteja usando medicamentos como antibióticos ou isotretinoína (Roacutan)\n• Tenha feridas, irritações ou tatuagens na área a ser tratada\n• Tenha histórico de herpes, doenças autoimunes, ou esteja gestante/lactante\n• Tenha feito outros procedimentos estéticos recentemente',
        'display_order': 4,
    },
    {
        'question_label':
            'Quantas sessões são necessárias?',
        'answer':
            'Não existe um número fixo — depende de fatores como genética, espessura e cor dos pelos, influência hormonal e área tratada. Em média, são necessárias de 8 a 12 sessões para resultados significativos, com intervalo de aproximadamente 30 dias entre elas. A redução gradual dos pelos é percebida desde as primeiras sessões.',
        'display_order': 4,
    },
    {
        'question_label':
            'Pode fazer em pele bronzeada/com sol?',
        'answer':
            'O Soprano Ice Platinum possui tecnologia que permite maior segurança em diferentes tipos de pele. Porém, recomendamos evitar exposição solar na área tratada por 5 dias antes e 5 dias depois da sessão. Se você tomou sol recentemente, avise nosso especialista para avaliarmos juntos o melhor momento para sua sessão.',
        'display_order': 5,
    },
    {
        'question_label':
            'Posso fazer mais de uma sessão na mesma área no mesmo dia?',
        'answer':
            'Não podemos realizar uma sessão na mesma área dentro de um intervalo de aproximadamente 30 dias. Fazer mais de uma sessão nesse intervalo não melhora a eficácia do processo. Mas podemos sim fazer várias áreas distintas no mesmo dia! 😊',
        'display_order': 5,
    },
    {
        'question_label':
            'Atende homens também?',
        'answer':
            'Sim! Atendemos todos os gêneros. A depilação a laser é muito procurada por homens, especialmente nas áreas de barba, costas, peito e axilas.',
        'display_order': 6,
    },
    {
        'question_label':
            'Qual a duração de cada sessão?',
        'answer':
            'A duração varia conforme a quantidade de áreas tratadas. Áreas pequenas (buço, axilas) levam cerca de 5-10 minutos. Áreas maiores (pernas, costas) levam 15-30 minutos. Sessões combinando várias áreas podem durar até 60 minutos.',
        'display_order': 8,
    },
    {
        'question_label':
            'E se eu tiver foliculite ou pelos encravados?',
        'answer':
            'A depilação a laser é um dos melhores tratamentos para quem sofre com foliculite (pelos encravados). Ao destruir o bulbo do pelo, o laser elimina o problema na raiz. Muitos clientes relatam melhora significativa já nas primeiras sessões.',
        'display_order': 10,
    },
    {
        'question_label':
            'Posso fazer menstruada?',
        'answer':
            'Sim, não tem problema fazer a sessão menstruada. Se o fluxo estiver mais intenso, pode usar absorvente interno; se estiver leve, nem é necessário. A clínica disponibiliza absorvente comum, interno e lenço umedecido no banheiro, caso queira fazer a troca antes ou depois da sessão.',
        'display_order': 11,
    },
    {
        'question_label':
            'Virilha completa já inclui o ânus?',
        'answer':
            "Não. A virilha completa e a virilha completa + ânus (perianal) são áreas diferentes, com valores diferentes. Se quiser incluir a região perianal, escolha a área 'Virilha Comp. + ânus'.",
        'display_order': 12,
    },
    {
        'question_label':
            'Fiz depilação com cera, posso fazer laser?',
        'answer':
            'Pode, mas é necessário aguardar pelo menos 20 dias entre a depilação com cera e a sessão de laser. O laser age no pelo com raiz, então ele precisa ter voltado a crescer.',
        'display_order': 13,
    },
    {
        'question_label':
            'Posso usar lâmina entre as sessões?',
        'answer':
            'Pode sim, sem problema. A lâmina (gilete) é o método recomendado entre as sessões. O que não pode é usar métodos que arrancam o pelo pela raiz, como cera, pinça ou epilador elétrico.',
        'display_order': 14,
    },
    {
        'question_label':
            'Tenho prótese de silicone, posso fazer?',
        'answer':
            'Sim, normalmente — exceto exatamente sobre a região onde está a prótese. Nas áreas próximas é possível realizar sem problema.',
        'display_order': 15,
    },
    {
        'question_label':
            'Posso pegar sol antes ou depois da sessão?',
        'answer':
            'Oriente-se por 5 dias antes e 5 dias depois da sessão sem exposição solar na área tratada. Passado esse período, a exposição é normal, sempre com protetor solar FPS 30 ou mais. Se tomou sol recentemente, avise a equipe para avaliarmos juntos o melhor momento da sessão.',
        'display_order': 16,
    },
    {
        'question_label':
            'Preciso de avaliação antes da primeira sessão?',
        'answer':
            'A avaliação é feita no mesmo dia da primeira sessão. Avaliamos a pele e os pelos, preenchemos a ficha de anamnese e os documentos necessários. Estando tudo certo, já iniciamos a primeira sessão de laser no mesmo dia, e reforçamos as orientações de cuidado antes e depois.',
        'display_order': 17,
    },
    {
        'question_label':
            'A clínica pode auxiliar na raspagem pré-sessão?',
        'answer':
            'Orientamos que você raspe o máximo que conseguir sozinho. Nas regiões em que não conseguir alcançar ou caso fique algum pelo, não tem problema, finalizamos a raspagem no consultório antes da sessão.',
        'display_order': 18,
    },
    {
        'question_label':
            'Precisa levar algo para a sessão?',
        'answer':
            'Se tiver alguma gilete que você já tenha costume de usar, dá sua preferência, pode levar. De resto não precisa mais nada.',
        'display_order': 19,
    },
]
