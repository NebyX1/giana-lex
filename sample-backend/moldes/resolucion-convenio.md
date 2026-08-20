---
name: resolucion-convenio
authority_level: TEMPLATE
document_type: resolucion
subtype: convenio
jurisdiction: Intendencia Departamental de Lavalleja
variants:
  - estandar
required_fields:
  - contraparte
  - objeto
conditional_fields:
  - personeria
  - financiamiento
  - juridico_notarial
  - suscripcion
  - unidad_ejecutora
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

[PROYECTO DE CONVENIO]

## RESULTANDO

I) [CONTRAPARTE].

II) [OBJETO].

III) [ANTECEDENTES].

IV) [OBLIGACIONES RELEVANTES].

## CONSIDERANDO

I) [FINALIDAD PÚBLICA].

II) [COMPETENCIA].

III) [CONVENIENCIA].

IV) [INFORMES JURÍDICOS / PRESUPUESTALES SI EXISTEN].

## ATENTO

[NORMATIVA REALMENTE VERIFICADA]

El Intendente Departamental de Lavalleja,

## RESUELVE

**1°.-** Apruébase el proyecto de Convenio entre la Intendencia Departamental de Lavalleja y [CONTRAPARTE], cuyo objeto es [OBJETO].

**2°.-** Pase a [JURÍDICO NOTARIAL] para su trámite.

**3°.-** Pase a [SECRETARÍA / AUTORIDAD] a efectos de coordinar su suscripción.

**4°.-** Comuníquese a [UNIDAD EJECUTORA] para su conocimiento y cumplimiento.

**5°.-** Cumplido, archívese.

## Instrucciones internas (no forman parte del documento)

- **Distinguir etapas:** `APROBAR EL PROYECTO` ≠ `SUSCRIBIR EL CONVENIO` ≠ `EJECUTAR EL CONVENIO`. Pueden ocurrir en etapas distintas. No fusionarlas automáticamente.
- Campos: `[CONTRAPARTE]`, `[PERSONERÍA]`, `[OBJETO]`, `[ANTECEDENTE]`, `[OBLIGACIONES IDL]`, `[OBLIGACIONES CONTRAPARTE]`, `[PLAZO]`, `[FINANCIAMIENTO]`, `[DEPENDENCIA EJECUTORA]`, `[FORMA DE SUSCRIPCIÓN]`.
- No inventar expediente, norma, monto, fecha, persona, empresa ni RUT. Usar `[DATO PENDIENTE: ...]` cuando falte información.
