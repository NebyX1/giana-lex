# Ejemplos de resoluciones

Este directorio contiene **once tipologías** de resoluciones administrativas de la Intendencia Departamental de Lavalleja, utilizadas exclusivamente como patrones de estructura, estilo y redacción.

Los documentos de este directorio se tratarán exclusivamente como **EXAMPLE**. Nunca deben ser utilizados como autoridad jurídica.

## Tipologías

| Archivo | Tipología |
| --- | --- |
| `01_reintegro_gastos.md` | Reintegro de gastos |
| `02_horas_extraordinarias.md` | Autorización de horas extraordinarias |
| `03_compensacion_funcionario.md` | Compensación a funcionario/a |
| `04_exoneracion_patente.md` | Exoneración de patente de rodados |
| `05_adjudicacion_licitacion.md` | Adjudicación de licitación |
| `06_aprobacion_convenio.md` | Aprobación de convenio |
| `07_designacion_funcion.md` | Designación para cometido específico |
| `08_modificacion_resolucion.md` | Modificación de resolución anterior |
| `09_reiteracion_gasto_observado.md` | Reiteración de gasto observado |
| `10_trasposicion_rubros.md` | Trasposición de rubros presupuestales |
| `11_subrogacion_funcionario.md` | Designación de subrogante |

## Naturaleza

Los documentos de este directorio se tratarán exclusivamente como **EXAMPLE**. Nunca deben ser utilizados como autoridad jurídica.

No constituyen:

- normativa vigente;
- jurisprudencia;
- acto administrativo aplicable;
- precedente vinculante;
- autoridad jurídica;
- evidencia suficiente para afirmar que una norma está vigente.

## Placeholders

Los archivos contienen placeholders deliberados:

```text
[FECHA]
[MONTO]
[NOMBRE]
[NÚMERO/AÑO]
[NORMA HABILITANTE]
```

Estos valores **no deben sustituirse automáticamente inventando información**. Solo pueden completarse con datos provenientes del expediente, de una herramienta, de una fuente jurídica autoritativa o de información suministrada explícitamente por el usuario.

El agente responsable de recuperar el fundamento jurídico debe obtener la normativa vigente desde el RAG de fuentes autoritativas antes de completar `[NORMA HABILITANTE]`.

## Índice machine-readable

`manifest.json` contiene el índice de las 11 tipologías con sus metadata.

## Instrucciones del agente

`GUIA_USO_AGENTE.md` contiene las reglas de generación que el agente debe seguir.
