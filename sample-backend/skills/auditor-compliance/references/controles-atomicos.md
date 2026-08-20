# Controles atómicos

Guía metodológica para descomponer requisitos en controles verificables.
No inventa requisitos ni normas.

## Qué es un control atómico

Es el elemento mínimo de verificación: una condición concreta, observable y
evaluable que permite afirmar si un aspecto del cumplimiento está satisfecho.
Un mismo requisito puede dar origen a varios controles atómicos.

## Cómo construir un control

Un control atómico bien formado especifica:

- **ID**: identificador único (ej.: C-001, C-002).
- **Requisito**: la obligación o condición de la que deriva.
- **Fuente**: norma o documento donde consta el requisito (si es norma, debe
  estar verificada).
- **Evidencia requerida**: qué documento, dato o actuación demuestra el
  cumplimiento.
- **Evidencia encontrada**: qué se encontró realmente.
- **Excepción**: supuestos en que el control no es exigible.
- **Resultado**: estado del control (ver `metodologia-auditoria.md`).
- **Severidad**: impacto del incumplimiento (ver `niveles-severidad.md`).
- **Acción correctiva**: qué hacer para subsanar.

## Reglas

- Cada control debe ser verificable; si no hay forma de verificarlo, es
  `NO EVALUABLE`.
- No combinar varias condiciones en un control ambiguo; dividirlas.
- No derivar controles de requisitos no verificados.
- Un requisito de un EXAMPLE jamás genera controles obligatorios.
- Si el control depende de norma vigente no verificada, marcar
  `[VERIFICAR NORMA APLICABLE]`.
