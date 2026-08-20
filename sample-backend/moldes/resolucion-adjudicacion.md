---
name: resolucion-adjudicacion
authority_level: TEMPLATE
document_type: resolucion
subtype: adjudicacion
jurisdiction: Intendencia Departamental de Lavalleja
variants:
  - total
  - por_items
required_fields:
  - procedimiento
  - objeto
  - decision
conditional_fields:
  - tribunal_de_cuentas
  - juridico_notarial
  - contrato
  - publicaciones
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
  - adjudicatario
---

# RESOLUCIÓN [NÚMERO]/[AÑO]

**Minas, [FECHA].**

## VISTO

[PROCEDIMIENTO DE CONTRATACIÓN + OBJETO]

## RESULTANDO

I) [SOLICITUD O NECESIDAD].

II) [RESOLUCIÓN DE LLAMADO].

III) [PUBLICACIONES].

IV) [APERTURA].

V) [OFERENTES].

VI) [INFORMES TÉCNICOS].

VII) [OTROS ANTECEDENTES RELEVANTES].

## CONSIDERANDO

I) [EVALUACIÓN TÉCNICA].

II) [EVALUACIÓN ECONÓMICA].

III) [DICTAMEN DE COMISIÓN ASESORA].

IV) [ADMISIBILIDAD].

V) [CONVENIENCIA].

VI) [CONTROLES REQUERIDOS].

## ATENTO

[NORMATIVA REALMENTE VERIFICADA]

[PLIEGO]

[ANTECEDENTES]

El Intendente Departamental de Lavalleja,

## RESUELVE

**1°.-** [ADJUDICACIÓN].

**2°.-** [ADJUDICATARIO / ÍTEMS / PRECIO].

**3°.-** [INTERVENCIÓN DEL ÓRGANO DE CONTRALOR, SI CORRESPONDE].

**4°.-** [NOTIFICACIONES].

**5°.-** [INSTRUMENTACIÓN CONTRACTUAL].

**6°.-** [PUBLICACIONES].

**7°.-** [PASE].

## Instrucciones internas (no forman parte del documento)

- **Adjudicación total:** un único adjudicatario para todo el objeto.
- **Adjudicación por ítems:** puede haber varios adjudicatarios, ítems desiertos o rechazados. Ejemplo: `ÍTEM 1 → OFERENTE A`, `ÍTEM 2 → OFERENTE B`, `ÍTEM 3 → DESIERTO`, `ÍTEM 4 → RECHAZADO`. No asumir un único adjudicatario.
- **Resultados alternativos:** `ADJUDICADO`, `DESIERTO`, `FRUSTRADO`, `RECHAZADO`, `SIN OFERTA ADMISIBLE` — solo cuando los antecedentes aportados lo determinen. No inventar estados.
- **Controles condicionales:** Comisión Asesora, Contador Delegado, Tribunal de Cuentas, Jurídico Notarial, publicación, notificación de oferentes y contrato son CONDICIONALES. Verificar el procedimiento y la normativa vigente; no afirmar que todos son obligatorios en cualquier contratación.
- No inventar expediente, norma, monto, fecha, persona, empresa, RUT ni adjudicatario. Usar `[DATO PENDIENTE: ...]` cuando falte información.
