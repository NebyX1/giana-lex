# Estados procedimentales

Guía metodológica para calificar cada etapa de un procedimiento. No inventa
pasos ni normas.

## Estados de etapa

- **`COMPLETA`**: la etapa existió, tiene evidencia y se realizó en el orden
  esperado.
- **`FALTANTE`**: no hay evidencia de que la etapa existió. No debe confundirse
  con `NO APLICA`.
- **`FUERA DE ORDEN`**: la etapa existió pero se realizó en un momento distinto
  del esperado, o sin respetar dependencias.
- **`NO APLICA`**: la etapa no corresponde a este tipo de procedimiento o
  supuesto concreto.
- **`NO VERIFICABLE`**: no hay evidencia suficiente para determinar si la etapa
  existió o cómo se realizó.

## Distinciones clave

- `FALTANTE` requiere ausencia de evidencia de existencia; `NO APLICA` requiere
  que la etapa no corresponda.
- `FUERA DE ORDEN` implica que la etapa existió; `FALTANTE` que no hay
  evidencia de que existió.
- `NO VERIFICABLE` se usa cuando no se puede decidir entre los demás estados.

## Reglas

- No afirmar que un paso es obligatorio sin evidencia.
- Si se desconoce la obligatoriedad, remitir a investigación jurídica.
- Si la obligación depende de norma vigente → `[VERIFICAR NORMA APLICABLE]`.
- Los `references/procedures/*.md` son metodológicos, no autoridad.
