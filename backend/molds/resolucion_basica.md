---
name: resolucion_basica
authority_level: TEMPLATE
document_type: resolucion
subtype: general
jurisdiction: Intendencia Departamental de Lavalleja
variants:
  - simple
  - desarrollada
required_fields:
  - decision
conditional_fields:
  - resultando
  - considerandos
  - pases
  - notificaciones
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

[ACTUACIÓN, SOLICITUD, INFORME, OFICIO O ANTECEDENTE QUE ORIGINA EL PROCEDIMIENTO]

## RESULTANDO

[RESULTANDO — INCLUIR CUANDO SEA NECESARIO DESARROLLAR LOS ANTECEDENTES FÁCTICOS O ADMINISTRATIVOS]

I) [ANTECEDENTE FÁCTICO RELEVANTE].

II) [OTRO ANTECEDENTE SI CORRESPONDE].

## CONSIDERANDO

I) [VALORACIÓN DE LOS HECHOS].

II) [FUNDAMENTO JURÍDICO, TÉCNICO O ADMINISTRATIVO].

## ATENTO

[A LAS NORMAS, INFORMES, ANTECEDENTES Y FACULTADES EFECTIVAMENTE VERIFICADAS].

El Intendente Departamental de Lavalleja,

## RESUELVE

**1°.-** [DECISIÓN PRINCIPAL].

**2°.-** [PASE / EJECUCIÓN].

**3°.-** [NOTIFICACIÓN / COMUNICACIÓN].

**4°.-** Cumplido, archívese.

## FIRMAS

[NOMBRE / CARGO / FIRMA]

## Instrucciones internas (no forman parte del documento)

- Usar numerales `1°.-`, `2°.-`, `3°.-` para la parte dispositiva de una resolución administrativa ordinaria. NO usar `ARTÍCULO 1°` salvo tipología excepcional que lo justifique.
- `RESULTANDO` es condicional: omitirlo cuando el acto sea simple y no existan antecedentes que desarrollar. No inventar párrafos para llenar secciones.
- `ATENTO` debe reflejar únicamente normas, informes y facultades efectivamente verificadas.
- No inventar expediente, norma, monto, fecha, persona ni cargo. Usar `[DATO PENDIENTE: ...]` cuando falte información.
