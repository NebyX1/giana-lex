# Control de consistencia

Método para verificar la coherencia interna de un documento jurídico.

## Dimensiones a comprobar

- **Fechas**: que no haya fechas divergentes para un mismo hecho.
- **Montos**: coherencia entre cifra y su expresión en letras; sin duplicaciones erróneas.
- **Nombres y cargos**: uso uniforme y correcto.
- **Números de resolución / expediente / informe / oficio**: que no cambien dentro del texto.
- **Numerales**: secuencia correcta (sin huecos ni duplicados).
- **Referencias cruzadas**: que apunten a las secciones o numerales correctos.
- **Pases administrativos**: coherencia en el trámite.
- **Notificaciones**: coherencia de los actos de notificación.

## Herramienta

Usar `scripts/validate_resolution.py` para validar:

- Presencia de `RESUELVE`.
- Presencia de al menos un numeral tipo `1°.-`.
- Duplicación de encabezados de sección.
- Huecos en la secuencia de numerales.
- Placeholders sin resolver.
- Referencias inconsistentes.

## Reglas

- El script es **determinista y estructural**: no decide legalidad mediante regex.
- Las observaciones del script se revisan junto con la consistencia semántica.
- Toda inconsistencia se señala, sin inventar el valor correcto.
