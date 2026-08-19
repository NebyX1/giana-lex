from skills.base import Skill


class PoliticalRiskSkill(Skill):
    key = "political_risk"
    name = "Analizador de riesgos politicos"
    description = (
        "Analiza actores potencialmente afectados, reacciones previsibles y conflictos "
        "institucionales, sindicales, politicos y comunicacionales."
    )
    instructions = (
        "Analiza riesgos politicos potenciales del borrador. Distingue hechos conocidos, posibilidades, "
        "hipotesis e informacion faltante. No afirmes que un actor reaccionara. Si es indispensable, solicita datos una sola vez."
    )


skill = PoliticalRiskSkill()
