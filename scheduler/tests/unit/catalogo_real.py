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
    # As duas grafias convivem de propósito. A Essência foi renomeada para
    # "Virilha Completa + ânus" em 16/09/2026, depois do defeito; Nobre Laser e
    # Depilação Premium continuam com a abreviada. Tirar a abreviada daqui
    # desligaria a auditoria justamente onde ela ainda é necessária.
    "Virilha Comp. + ânus", "Virilha Completa + ânus",
]

AREAS = [{"id": n, "name": n} for n in CATALOGO]
