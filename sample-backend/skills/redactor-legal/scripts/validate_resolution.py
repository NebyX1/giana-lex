"""Validador determinista de estructura de resoluciones.

Analiza un texto de resolución y reporta observaciones estructurales:

- presencia de la sección "RESUELVE";
- presencia de al menos un numeral del tipo "1°.-";
- encabezados de sección duplicados;
- huecos en la secuencia de numerales (1°.-, 2°.-, luego 4°.-);
- placeholders sin resolver;
- referencias inconsistentes (referencia cruzada que no apunta a una sección existente).

Solo usa la biblioteca estándar de Python. No emite juicio jurídico.
"""

from __future__ import annotations

import re
from pathlib import Path

# Encabezados de sección habituales de una resolución.
SECTION_HEADINGS: tuple[str, ...] = (
    "VISTO",
    "RESULTANDO",
    "CONSIDERANDO",
    "ATENTO",
    "RESUELVE",
    "Notifíquese",
    "Comuníquese",
    "Pase",
    "Archívese",
)

# Patrón de un numeral del tipo "1°.-" (permite "1º.-", "1.".-", variantes ortográficas).
NUMERAL_RE = re.compile(r"^\s*(\d{1,3})\s*[°º]\s*\.\s*-", re.MULTILINE)

# Patrón de placeholder sin resolver.
PLACEHOLDER_RE = re.compile(r"\[[^\]]*DATO PENDIENTE[^\]]*\]", re.IGNORECASE)

# Patrón de una referencia cruzada a una sección (p. ej. "el VISTO", "numeral 3°.-",
# "RESULTANDO II").
SECTION_REF_RE = re.compile(
    r"(?:numeral|n\.|nro\.|art\.|artículo|punto)\s*(\d{1,3})",
    re.IGNORECASE,
)


class ResolucionValidator:
    """Valida la estructura de un texto de resolución de forma determinista."""

    def __init__(self, texto: str) -> None:
        self.texto: str = texto

    def tiene_resuelve(self) -> bool:
        """True si aparece la palabra 'RESUELVE' como encabezado de sección."""
        return bool(re.search(r"^\s*RESUELVE\s*:?\s*$", self.texto, re.MULTILINE))

    def tiene_numeral(self) -> bool:
        """True si existe al menos un numeral del tipo '1°.-'."""
        return bool(NUMERAL_RE.search(self.texto))

    def encabezados_duplicados(self) -> list[str]:
        """Devuelve los encabezados de sección que aparecen más de una vez.

        Un encabezado puede aparecer solo en su línea ("VISTO") o seguido de
        dos puntos y contenido ("VISTO: el expediente ...").
        """
        duplicados: list[str] = []
        for encabezado in SECTION_HEADINGS:
            matches = re.findall(
                rf"^\s*{re.escape(encabezado)}\s*:?\s*(?:$|\S)",
                self.texto,
                re.MULTILINE,
            )
            if len(matches) > 1:
                duplicados.append(encabezado)
        return duplicados

    def huecos_de_numerales(self) -> list[int]:
        """Devuelve los números faltantes en la secuencia de numerales."""
        numeros: list[int] = []
        for match in NUMERAL_RE.finditer(self.texto):
            numeros.append(int(match.group(1)))
        if not numeros:
            return []
        numeros = sorted(set(numeros))
        primero = numeros[0]
        ultimo = numeros[-1]
        presentes = set(numeros)
        huecos = [
            n for n in range(primero, ultimo + 1) if n not in presentes
        ]
        return huecos

    def placeholders_sin_resolver(self) -> list[str]:
        """Devuelve los placeholders pendientes encontrados."""
        return PLACEHOLDER_RE.findall(self.texto)

    def referencias_inconsistentes(self) -> list[str]:
        """Devuelve referencias cruzadas a numerales que no existen en el texto.

        Una referencia a un numeral (p. ej. 'numeral 5°.-') se considera inconsistente
        si ese numeral no aparece como numeral real en el documento. No se valida
        legalidad, solo coherencia estructural de la referencia.
        """
        presentes = {m.group(1) for m in NUMERAL_RE.finditer(self.texto)}
        inconsistentes: list[str] = []
        for match in SECTION_REF_RE.finditer(self.texto):
            numero = match.group(1)
            if numero not in presentes:
                inconsistentes.append(match.group(0))
        return inconsistentes

    def informe(self) -> str:
        """Genera un informe textual con las observaciones encontradas."""
        lineas: list[str] = ["Informe de validación estructural", "-" * 40]

        if self.tiene_resuelve():
            lineas.append("OK: sección RESUELVE presente.")
        else:
            lineas.append("FALTA: no se encontró la sección RESUELVE.")

        if self.tiene_numeral():
            lineas.append("OK: hay al menos un numeral (ej. 1°.-).")
        else:
            lineas.append("FALTA: no se encontró ningún numeral del tipo 1°.-.")

        duplicados = self.encabezados_duplicados()
        if duplicados:
            lineas.append("AVISO: encabezados duplicados: " + ", ".join(duplicados))
        else:
            lineas.append("OK: no hay encabezados duplicados.")

        huecos = self.huecos_de_numerales()
        if huecos:
            lineas.append("AVISO: huecos en la secuencia de numerales: " +
                          ", ".join(str(h) for h in huecos))
        else:
            lineas.append("OK: secuencia de numerales sin huecos.")

        pendientes = self.placeholders_sin_resolver()
        if pendientes:
            lineas.append("AVISO: placeholders sin resolver: " +
                          "; ".join(pendientes))
        else:
            lineas.append("OK: sin placeholders pendientes.")

        refs = self.referencias_inconsistentes()
        if refs:
            lineas.append("AVISO: referencias inconsistentes (a numeral inexistente): " +
                          "; ".join(refs))
        else:
            lineas.append("OK: referencias cruzadas coherentes.")

        lineas.append("-" * 40)
        lineas.append("Nota: solo validación estructural; no se emite juicio jurídico.")
        return "\n".join(lineas)


def validar_texto(texto: str) -> str:
    """Valida un texto de resolución y devuelve el informe."""
    return ResolucionValidator(texto).informe()


def validar_archivo(ruta: str) -> str:
    """Valida el contenido de un archivo y devuelve el informe."""
    path = Path(ruta)
    texto = path.read_text(encoding="utf-8")
    return validar_texto(texto)


def main() -> None:
    """Punto de entrada: recibe una o varias rutas de archivo."""
    import sys

    if len(sys.argv) < 2:
        print("Uso: python validate_resolution.py <ruta-a-resolucion.txt> [...]")
        return
    for ruta in sys.argv[1:]:
        print(validar_archivo(ruta))
        print()


if __name__ == "__main__":
    main()
