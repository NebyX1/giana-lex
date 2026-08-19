from skills.base import Skill


class LegalRiskSkill(Skill):
    key = "legal_risk"
    name = "Analizador de riesgos legales potenciales"
    description = "Detecta puntos que necesitan revision juridica sin inventar leyes ni articulos."
    instructions = (
        "Detecta solo riesgos legales potenciales: competencia, motivacion, antecedentes, presupuesto, procedimiento, "
        "notificacion, plazos, contratacion, delegacion y terceros. No inventes normas ni declares ilegalidad sin fuente. "
        "Explicita cuando falta informacion normativa. Si es indispensable, solicita datos una sola vez."
    )


skill = LegalRiskSkill()
