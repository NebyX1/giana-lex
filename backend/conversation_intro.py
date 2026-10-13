"""Recognize introductory messages before starting the document workflow."""
import re
import unicodedata


HELP_MESSAGE = (
    "¡Hola! Sí, puedo ayudarte. Puedo acompañarte a:\n\n"
    "• Preparar y revisar resoluciones y otros documentos administrativos.\n"
    "• Organizar los antecedentes y los datos de tu caso.\n"
    "• Buscar ejemplos de resoluciones y referencias disponibles.\n"
    "• Comprobar un borrador e identificar datos faltantes, inconsistencias y posibles riesgos.\n"
    "• Ajustar el texto y exportar el documento aprobado.\n\n"
    "Cuéntame qué necesitas resolver o qué documento quieres preparar."
)

_INTRO_PREFIX = re.compile(
    r"^(?:hola|hey|saludos|buenas(?: tardes| noches)?|buen(?:os)? dia(?:s)?|giana(?: lex)?|gianna(?: lex)?)(?: |$)"
)
_HELP_QUESTION = re.compile(
    r"(?:"
    r"(?:me )?(?:puedes|podes|podrias|podras) (?:ayudar|ayudarme|asistir|asistirme)"
    r"|me (?:ayudas|ayudarias)"
    r"|(?:en )?que (?:me )?(?:puedes|podes|podrias) (?:hacer|ayudar|ayudarme)"
    r"|(?:como|en que) (?:me )?(?:puedes|podes|podrias) (?:ayudar|ayudarme)"
    r"|que (?:haces|sabes hacer|ofreces)"
    r"|como funcionas|quien eres"
    r"|cual(?:es)? (?:es|son) (?:tu|tus) (?:funcion(?:es)?|capacidad(?:es)?)"
    r"|necesito (?:tu )?ayuda|ayuda(?:me)?"
    r")"
)


def introductory_response(message: str) -> str | None:
    normalized = unicodedata.normalize("NFKD", message.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    if not normalized:
        return None
    while prefix := _INTRO_PREFIX.match(normalized):
        normalized = normalized[prefix.end():].strip()
    normalized = re.sub(r"(?: por favor| gracias| por mi)$", "", normalized).strip()
    if not normalized or _HELP_QUESTION.fullmatch(normalized):
        return HELP_MESSAGE
    return None
