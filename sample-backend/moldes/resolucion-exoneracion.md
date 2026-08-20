---
name: resolucion-exoneracion
authority_level: TEMPLATE
document_type: resolucion
subtype: exoneracion
jurisdiction: Intendencia Departamental de Lavalleja
variants:
  - directa
  - junta
required_fields:
  - solicitante
  - tributo
  - objeto
conditional_fields:
  - informe_tecnico
  - informe_juridico
  - junta_departamental
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

[SOLICITUD DE EXONERACIÓN]

## RESULTANDO

I) [SOLICITANTE].

II) [TRIBUTO].

III) [OBJETO].

IV) [EJERCICIO].

## CONSIDERANDO

I) [INFORME TÉCNICO].

II) [INFORME JURÍDICO].

III) [COMPETENCIA].

## ATENTO

[NORMATIVA REALMENTE VERIFICADA]

El Intendente Departamental de Lavalleja,

## RESUELVE

**1°.-** [DECISIÓN SEGÚN COMPETENCIA].

**2°.-** [PASE].

**3°.-** [NOTIFICACIÓN].

**4°.-** Cumplido, archívese.

## Instrucciones internas (no forman parte del documento)

### Decisión previa de competencia

Antes de redactar el numeral principal, determinar:

```
¿EXISTE UNA NORMA VIGENTE QUE HABILITE AL EJECUTIVO
DEPARTAMENTAL A CONCEDER DIRECTAMENTE ESTA EXONERACIÓN?
```

- **SÍ** → variante `directa`.
- **NO** → variante `junta` (remisión / iniciativa a la Junta Departamental).

### VARIANTE DIRECTA

Campos: `[SOLICITANTE]`, `[TRIBUTO]`, `[OBJETO]`, `[EJERCICIO]`, `[NORMA HABILITANTE]`, `[INFORME TÉCNICO]`, `[INFORME JURÍDICO]`.

Parte resolutiva posible:
1°.- Exonérase...
2°.- Pase a...
3°.- Notifíquese...
4°.- Cumplido, archívese.

Solo si la competencia está efectivamente verificada.

### VARIANTE JUNTA

Si el Ejecutivo no tiene competencia directa pero puede elevar iniciativa:

1°.- Elévese a consideración de la Junta Departamental...

NO usar `Exonérase...` si la decisión corresponde jurídicamente a la Junta. Este control es CRÍTICO.

### Exoneraciones parciales

Permitir situaciones donde parte del tributo puede ser exonerada y otra parte no, o requiere otro órgano. No forzar decisiones binarias.

- No inventar expediente, norma, monto, fecha, persona, empresa ni RUT. Usar `[DATO PENDIENTE: ...]` cuando falte información.
