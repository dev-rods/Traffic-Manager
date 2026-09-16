# -*- coding: utf-8 -*-
"""Os nomes de área que estão no banco, em dev e prod (13/09/2026).

Um lugar só porque duas travas dependem dele: [areas_ambiguas] decide se o nome
é ambíguo, [confirmacao_de_areas] decide se a paciente conseguiu nomeá-lo. Em
16/09/2026 a segunda foi conferida contra um catálogo imaginário e passou, e o
catálogo de verdade tinha "Virilha Comp. + ânus" - abreviado, inalcançável, e
ninguém soube até uma paciente bater na parede cinco vezes.

Copiados do cadastro real da Essência / Nobre Laser / Depilação Premium.
"""

CATALOGO = [
    "1/2 Braço", "1/2 Coxa", "1/2 Glúteo", "1/2 Perna", "1/2 Virilha", "Abdômen",
    "Aréola", "Axilas", "Barba Comp. + Pescoço", "Barba contorno", "Braço Completo",
    "Buço", "Costas total + ombros", "Costeleta", "Coxas",
    "Glabela (entre as sobrancelhas)", "Glúteo", "Linha alba", "Lombar",
    "Mão ou Pé + Dedos", "Mento/Queixo", "Nariz", "Nuca", "Ombros", "Orelhas",
    "Peitoral", "Peitoral + abdômen", "Perianal/ânus", "Perna Completa",
    "Pernas Completas", "Pescoço",
    "Rosto Completo", "Virilha Cavada", "Virilha Completa", "Virilha Simples",
    # Era "Virilha Comp. + ânus" nas três clínicas até 16/09/2026, e o nome
    # abreviado tornava a área inalcançável. Renomeada em prod no mesmo dia.
    # A abreviação continua coberta pela auditoria por "Barba Comp. + Pescoço",
    # que ainda está assim no cadastro - dado real, não caso inventado.
    "Virilha Completa + ânus",
]

AREAS = [{"id": n, "name": n} for n in CATALOGO]
