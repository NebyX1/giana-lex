# Moldes editables

Los moldes son **TEMPLATE**: estructuras sobre las cuales generar un documento nuevo. No son reglas jurídicas, no son documentos aprobados y no constituyen autoridad legal.

## Qué es un molde

Un molde es un esqueleto generativo. Indica al agente **cómo estructurar correctamente una decisión** una vez que los hechos, la competencia y el derecho aplicable han sido verificados. No le dice **qué decidir**.

## Qué no es un molde

- **NO** es `LEGAL_AUTHORITY`: no demuestra derecho aplicable.
- **NO** es `EXAMPLE`: no enseña cómo se redactó un caso anterior.
- **NO** es un documento final: todo lo generado es un BORRADOR.

## Diferencia conceptual

| Nivel | Rol |
| --- | --- |
| `LEGAL_AUTHORITY` | Demuestra derecho aplicable |
| `EXAMPLE` | Enseña cómo se redactó un caso anterior |
| `TEMPLATE` | Estructura sobre la cual generar un documento nuevo |

## Sintaxis de placeholders

Preferir:

```text
[FECHA]
[NOMBRE]
[MONTO]
[NORMA APLICABLE]
[INFORME]
```

Para ausencias detectadas durante la generación:

```text
[DATO PENDIENTE: informe de Contaduría]
```

No usar múltiples convenciones incompatibles. Nunca completar automáticamente datos que no existen en el contexto.

## Variantes

Algunos moldes soportan variantes internas. El agente debe determinarlas ANTES de redactar y no mezclarlas.

## Qué información no puede inventarse

Nunca inventar: número de expediente, norma, competencia, monto, fecha, persona, empresa, RUT, cargo, informe, oficio o fojas. Si falta información, usar `[DATO PENDIENTE: ...]` o solicitarla.

## Cómo crear un molde nuevo

1. Crear un archivo `.md` en `backend/moldes/`.
2. Añadir frontmatter YAML con `name`, `authority_level: TEMPLATE`, `document_type`, `subtype`, `jurisdiction`, `variants`, `required_fields`, `conditional_fields`, `forbidden_inference`.
3. Escribir la estructura con placeholders.
4. Añadir instrucciones internas (marcadas como "no forman parte del documento").

## Cómo seleccionar variantes

- Determinar la variante antes de redactar.
- Si no puede determinarse, consultar el expediente, usar herramientas, solicitar aclaración o marcar la variante como pendiente. No adivinar.

## Tabla conceptual

| Molde | Uso | Variantes |
| --- | --- | --- |
| resolucion_basica | Resolución administrativa general | simple / desarrollada |
| resolucion-adjudicacion | Decisión de procedimiento competitivo | total / por ítems |
| resolucion-contratacion | Contrataciones | personal / arrendamiento / proveedor |
| resolucion-convenio | Aprobación de convenio | estándar |
| resolucion-exoneracion | Solicitudes de exoneración | directa / Junta |
| proyecto-decreto | Iniciativa normativa | nuevo / modificativo / declarativo |
| informe-juridico | Asesoramiento jurídico | según cuestión |
