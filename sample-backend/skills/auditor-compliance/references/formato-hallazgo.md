# Formato de hallazgo

Guía metodológica para estructurar la salida de un hallazgo de auditoría.
Plantilla de contenido.

## Estructura interna

```
HALLAZGO C-001
Estado:
Severidad:
Requisito:
Fuente jurídica:
Evidencia requerida:
Evidencia encontrada:
Evidencia faltante:
Análisis:
Acción correctiva:
```

## Contenido por campo

### HALLAZGO C-XXX
Identificador único del hallazgo.

### Estado
Resultado del control: `CUMPLE`, `NO CUMPLE`, `CUMPLE PARCIALMENTE`,
`NO EVALUABLE`, `NO APLICA`.

### Severidad
Nivel de gravedad según `niveles-severidad.md`.

### Requisito
Obligación o condición que se controla.

### Fuente jurídica
Norma o documento donde consta el requisito, con su estado de verificación.
Si no está verificada: `[VERIFICAR NORMA APLICABLE]`.

### Evidencia requerida
Qué documento o dato demuestra el cumplimiento.

### Evidencia encontrada
Qué se encontró realmente.

### Evidencia faltante
Qué no se encontró y por qué importa.

### Análisis
Razonamiento que vincula requisito, evidencia y resultado. No inventar
evidencia ni normas.

### Acción correctiva
Qué debería hacerse para subsanar, si corresponde.

## Reglas

- Cada hallazgo debe citar su fuente.
- `NO ENCONTRÉ EVIDENCIA` ≠ `NO CUMPLE` (puede ser `NO EVALUABLE`).
- Un requisito de un EXAMPLE jamás es obligación.
