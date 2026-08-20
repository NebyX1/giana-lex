---
name: informe-juridico
authority_level: TEMPLATE
document_type: informe_juridico
subtype: asesoramiento
jurisdiction: Intendencia Departamental de Lavalleja
variants:
  - segun_cuestion
required_fields:
  - objeto
  - cuestion_juridica
  - conclusion
conditional_fields:
  - fojas
  - recomendacion
forbidden_inference:
  - numero_expediente
  - norma
  - competencia
  - monto
  - fecha
  - persona
  - empresa
  - rut
  - fojas
---

# INFORME JURÍDICO N° [NÚMERO]/[AÑO]

## I. IDENTIFICACIÓN

**Expediente:** [EXPEDIENTE]

**Solicitante:** [SOLICITANTE]

**Dependencia:** [DEPENDENCIA]

**Objeto:** [OBJETO]

## II. ANTECEDENTES

[DESCRIPCIÓN OBJETIVA DE LAS ACTUACIONES RELEVANTES]

## III. CUESTIÓN JURÍDICA

[PROBLEMA JURÍDICO CONCRETO A DETERMINAR]

## IV. NORMATIVA APLICABLE

[NORMAS VERIFICADAS]

## V. ANÁLISIS

[APLICACIÓN DE LAS NORMAS A LOS HECHOS]

## VI. COMPETENCIA

[ÓRGANO COMPETENTE Y FUNDAMENTO]

## VII. CONCLUSIÓN

[RESPUESTA JURÍDICA CONCRETA]

## VIII. RECOMENDACIÓN

[CURSO DE ACCIÓN SUGERIDO]

## FIRMA

[LETRADO/A]

[DEPENDENCIA]

[FECHA]

## Instrucciones internas (no forman parte del documento)

- **HECHOS ≠ ANÁLISIS:** en `ANTECEDENTES` describir hechos y actuaciones; en `ANÁLISIS` interpretarlos jurídicamente. No mezclar ambos niveles.
- **CUESTIÓN JURÍDICA:** formular claramente qué se está resolviendo. Ejemplo: "Determinar si el Ejecutivo Departamental posee competencia para conceder directamente la exoneración solicitada."
- **NORMATIVA:** toda norma mencionada debe provenir de fuente jurídica verificada, nunca de la memoria del LLM. Si no está verificada: `[DATO PENDIENTE: verificar norma aplicable]`.
- **FOJAS:** si se conoce la ubicación de una actuación, permitir `a fs. [N]`. NUNCA inventar fojas; si no existe metadata de páginas, omitir la referencia.
- **El informe ASESORA; la resolución DECIDE.** No redactar el informe como si fuera el acto administrativo final.
- No inventar expediente, norma, monto, fecha, persona, empresa ni RUT. Usar `[DATO PENDIENTE: ...]` cuando falte información.
