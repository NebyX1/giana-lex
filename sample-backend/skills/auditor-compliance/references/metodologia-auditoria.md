# Metodología de auditoría de compliance

Guía metodológica original. No es autoridad legal ni inventa requisitos.

## Propósito

Comprobar si un documento o actuación cumple las obligaciones jurídicas,
reglamentarias o administrativas aplicables, convirtiendo cada requisito en
controles verificables.

## Método

1. **Determinar el alcance.** Fijar qué documento o actuación se audita y qué
   materias se cubren.
2. **Identificar obligaciones aplicables.** Recopilar los requisitos que el
   ordenamiento impone, partiendo de derecho verificado.
3. **Convertir cada requisito en controles verificables.**

```
NORMA / REQUISITO
   ↓
CONTROLES VERIFICABLES
```

4. **Registrar por cada control**:
   - ID;
   - requisito;
   - fuente;
   - evidencia requerida;
   - evidencia encontrada;
   - excepción;
   - resultado;
   - severidad;
   - acción correctiva.
5. **Emitir hallazgos.** Resumir cada desviación con su evidencia y severidad.

## Estados de control

- `CUMPLE`
- `NO CUMPLE`
- `CUMPLE PARCIALMENTE`
- `NO EVALUABLE`
- `NO APLICA`

**Importante**: `NO ENCONTRÉ EVIDENCIA` no significa automáticamente
`NO CUMPLE`; puede ser `NO EVALUABLE`.

## Reglas

- Cada hallazgo debe citar su fuente.
- No asignar severidad arbitrariamente: seguir `niveles-severidad.md`.
- Un requisito proveniente de un EXAMPLE jamás es obligación.
- Si una obligación depende de norma vigente no verificada, pedir
  investigación.
- No inventar requisitos ni normas.
