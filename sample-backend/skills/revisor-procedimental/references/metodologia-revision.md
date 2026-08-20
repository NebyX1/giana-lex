# Metodología de revisión procedimental

Guía metodológica original. No es autoridad legal ni inventa pasos obligatorios.

## Propósito

Analizar la trayectoria de un expediente: si recorrió correctamente los pasos
que debía recorrer, en el orden y con las intervenciones requeridas. Se enfoca
en la secuencia, no solo en el resultado.

## Representación

Tratar el procedimiento como una máquina de estados con una secuencia general
de referencia:

```
INICIO → SOLICITUD → COMPETENCIA → ANTECEDENTES → INFORMES
→ INTERVENCIÓN JURÍDICA → INTERVENCIÓN CONTABLE → CONTRALOR
→ ACTO → NOTIFICACIÓN → EJECUCIÓN → ARCHIVO
```

Esta secuencia es una guía de referencia, no una lista fija obligatoria. El
conjunto exacto y la obligatoriedad de cada etapa dependen del tipo de
procedimiento (ver `procedures/`).

## Método

1. **Identificar el tipo de procedimiento** (compras, RRHH, exoneraciones,
   convenios, gastos observados, resoluciones).
2. **Determinar la secuencia esperada** para ese tipo.
3. **Por cada etapa evaluar**:
   - requisito;
   - evidencia de que existió;
   - orden;
   - obligatoriedad;
   - dependencia (qué etapa debe precederla);
   - excepción;
   - estado.
4. **Reconstruir la trayectoria** real del expediente a partir de sus
   actuaciones.
5. **Comparar trayectoria real con la esperada**.
6. **Emitir observaciones** sobre etapas faltantes, fuera de orden o no
   verificables.

## Estados de etapa

- `COMPLETA`
- `FALTANTE`
- `FUERA DE ORDEN`
- `NO APLICA`
- `NO VERIFICABLE`

## Reglas

- Si se desconoce si un paso es jurídicamente obligatorio, pedir investigación
  jurídica.
- No inventar pasos obligatorios.
- Distinguir `FALTANTE` (sin evidencia de que existió) de `NO APLICA`.
- Si la obligación depende de norma vigente → `[VERIFICAR NORMA APLICABLE]`.
- Los `references/procedures/*.md` son metodológicos, no autoridad.
