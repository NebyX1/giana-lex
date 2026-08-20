---
name: proyecto-decreto
authority_level: TEMPLATE
document_type: proyecto_decreto
subtype: iniciativa_normativa
jurisdiction: Intendencia Departamental de Lavalleja
variants:
  - nuevo
  - modificativo
  - declarativo
required_fields:
  - objeto
  - articulado
conditional_fields:
  - derogaciones
  - transitorios
forbidden_inference:
  - numero_expediente
  - norma
  - competencia
  - monto
  - fecha
  - persona
  - empresa
  - rut
---

# RESOLUCIÓN [NÚMERO]/[AÑO]

**Minas, [FECHA].**

## VISTO

[ANTECEDENTES]

## RESULTANDO

I) [ANTECEDENTE FÁCTICO RELEVANTE].

II) [OTRO ANTECEDENTE SI CORRESPONDE].

## CONSIDERANDO

I) [VALORACIÓN DE LOS HECHOS].

II) [FUNDAMENTO JURÍDICO, TÉCNICO O ADMINISTRATIVO].

## ATENTO

[A LAS NORMAS, INFORMES, ANTECEDENTES Y FACULTADES EFECTIVAMENTE VERIFICADAS].

El Intendente Departamental de Lavalleja,

## RESUELVE

**1°.-** Con iniciativa favorable, elévese a consideración de la Junta Departamental el siguiente:

# PROYECTO DE DECRETO

**Artículo 1°.-** [TEXTO].

**Artículo 2°.-** [TEXTO].

**Artículo 3°.-** [TEXTO].

**Artículo [N].-** Comuníquese.

## Instrucciones internas (no forman parte del documento)

### Dos objetos distintos

- **A) RESOLUCIÓN DEL INTENDENTE** que eleva el proyecto (usa numerales `1°.-`, `2°.-`).
- **B) TEXTO DEL PROYECTO DE DECRETO** (usa `Artículo 1°.-`, `Artículo 2°.-`).

No intercambiar los sistemas de numeración.

### Variantes

- **NUEVO** — verbos posibles: `Créase`, `Establécese`, `Reglaméntase`, `Dispónese`.
- **MODIFICATIVO** — verbos posibles: `Modifícase`, `Sustitúyese`, `Agréguese`, `Derógase`, `Suprímese`, `Renúmerase`. La elección depende de la operación normativa real.
- **DECLARATIVO** — ejemplo: `Declárase...`.

No mezclar variantes arbitrariamente.

### Modificaciones

Cuando se modifica una norma, identificar inequívocamente: norma, artículo, texto anterior si corresponde, nuevo texto completo.

Ejemplo:
```
Artículo 1°.- Modifícase el artículo [X] del Decreto [Y],
el que quedará redactado de la siguiente manera:

"[TEXTO COMPLETO]"
```

Evitar modificaciones ambiguas.

- No inventar expediente, norma, monto, fecha, persona, empresa ni RUT. Usar `[DATO PENDIENTE: ...]` cuando falte información.
