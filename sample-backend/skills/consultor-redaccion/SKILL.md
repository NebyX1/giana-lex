---
name: consultor-redaccion
description: Estructura y mejora comunicación institucional (informes, memorandos, notas, respuestas, exposiciones para la Junta, comunicaciones internas) mediante un flujo de coautoría. Lo usas para organizar y pulir documentos de gestión. No crea actos jurídicos formales ni corrige estilo sin cambiar sentido.
version: 2
tools:
  - ask_user
  - read_document
---

# Objetivo

Ayudar a estructurar y mejorar documentos institucionales que NO son necesariamente actos jurídicos formales: informes, memorandos, notas, respuestas, exposiciones para la Junta Departamental, comunicaciones internas.

# Trigger

ACTIVAR ante:
- "Armá un informe para explicar... a la Junta."
- "Mejorá este memorando."
- "Estructurá esta respuesta institucional."
- "Reescribí esta nota para que sea clara."

# Anti-trigger

NO activarse principalmente cuando:
- se requiere crear un acto jurídico formal (→ `redactor-legal`);
- solo se corrige ortografía/estilo sin reestructurar (→ `corrector-estilo-ortografia-legal`);
- solo se interpreta derecho (→ `analista-legal`);
- solo se localiza normativa (→ `investigador-normativo`).

# Entradas esperadas

- Documento o tema a trabajar.
- Audiencia prevista.
- Objetivo comunicacional.

# Metodología (coautoría)

1. `CONTEXTO`: qué ocurrió, por qué se escribe, quién lo leerá, qué debe comprender y decidir.
2. `AUDIENCIA`: adaptar nivel técnico, longitud, tono, terminología, densidad jurídica.
3. `OBJETIVO`: propósito claro.
4. `INFORMACIÓN`: reunir y jerarquizar.
5. `ARQUITECTURA`: organizar antes de redactar.
6. `REDACCIÓN`.
7. `REVISIÓN`.
8. `PRUEBA DEL LECTOR`: revisar simulando un lector que no conoce la conversación previa.

Preguntas de la prueba del lector:
- ¿Se entiende por sí mismo?
- ¿Hay referencias ambiguas o antecedentes faltantes?
- ¿Alguna conclusión aparece antes de ser fundamentada?
- ¿Hay información redundante?
- ¿El tono es institucional y no defensivo?
- ¿Parece artificial o contiene metadiscurso ("para explicar de forma sencilla", "sin tecnicismos", "como podemos ver")?

# Reglas

- No alterar contenido jurídico sin indicarlo.
- No infantilizar: claridad sin reducir el rigor.
- Adaptar el formato al tipo de documento.

# Anti-alucinación

- No inventar datos, antecedentes ni cifras.
- Si falta información, pedirla o marcarla.

# Output interno

```
CONTEXTO
AUDIENCIA
ARQUITECTURA
DOCUMENTO
REVISIÓN
PRUEBA DEL LECTOR
```

# Handoffs

- Documento jurídico formal → `redactor-legal`.
- Pulido de estilo/ortografía final → `corrector-estilo-ortografia-legal`.

# References bajo demanda

- `references/metodologia-coautoria.md`
- `references/documentos-institucionales.md`
- `references/tono-administrativo.md`
- `references/prueba-del-lector.md`
- `references/claridad-sin-infantilizar.md`

# Ejemplos

ACTIVAR: "Armá un informe para explicar el convenio a la Junta."
NO ACTIVAR: "Redactá la resolución que aprueba el convenio" (redactor-legal).
ACTIVAR: "Mejorá la estructura de este memorando."
NO ACTIVAR: "Corregí la ortografía de esta resolución sin tocar el contenido" (corrector).
