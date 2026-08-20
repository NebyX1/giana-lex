# Skills de Giana-Lex

Este directorio contiene las **competencias especializadas** del agente jurídico-administrativo. Un skill no es un "personaje": es un procedimiento con finalidad delimitada, trigger, anti-trigger, metodología, reglas de evidencia, output y handoffs.

## Qué es un skill

Cada skill representa una competencia. Se activa solo cuando aporta valor. La arquitectura conceptual es:

```
INVESTIGADOR NORMATIVO
        ↓
   ANALISTA LEGAL
        ↓
AUDITOR ─ REVISOR ─ ANALISTA POLÍTICO
        ↓
 CONSULTOR REDACCIÓN
        ↓
    REDACTOR LEGAL
        ↓
CORRECTOR ESTILO Y ORTOGRAFÍA LEGAL
        ↓
     OUTPUT FINAL
```

Esto NO significa que todos se ejecuten siempre. Cada skill se activa según la necesidad.

## Cómo se activa

- El frontend/API envía `active_skills` (lista de nombres) al ejecutar una sesión.
- `SkillLoader` descubre `*/SKILL.md`, valida frontmatter (`name`, `description`, `version`, `tools`) y carga el cuerpo como instrucciones.
- No existe router automático: la selección es explícita. Un futuro router podría usar la `description` para decidir.
- Si no se indica ningún skill, se usa por defecto `analista-legal`.

## Cómo se crea un nuevo skill

1. Crear una carpeta con el nombre del skill.
2. Crear `SKILL.md` con frontmatter YAML:
   ```yaml
   ---
   name: nombre-del-skill
   description: Descripción clara que permite distinguir cuándo usarlo y cuándo no.
   version: 1
   tools:
     - tool_existente_1
     - tool_existente_2
   ---
   ```
3. Añadir el cuerpo con: objetivo, trigger, anti-trigger, entradas, metodología, reglas, output, handoffs.
4. Agregar `references/` (conocimiento bajo demanda) y `evals/` (evaluaciones).
5. Crear `scripts/` solo si hay validación determinista útil.

El loader globa `*/SKILL.md`, por lo que `references/`, `evals/` y `scripts/` **no se cargan como skills separados**.

## References

Conocimiento extenso cargado solo cuando hace falta. Cada SKILL.md lista sus `references/` bajo demanda (progressive disclosure). Esto reduce ruido, tokens e interferencia.

## Evals

Cada skill incluye `evals/<nombre>.json` con casos: `trigger`, `non_trigger`, `normal_cases`, `adversarial_cases`, `missing_information`, `hallucination_cases`. Estas evaluaciones son semánticas (para revisión humana o LLM) y se complementan con tests de infraestructura en `tests/test_skills.py`.

## Handoffs

Los skills se derivan entre sí de forma acotada (ver SKILL.md de cada uno). No hay recursión descontrolada. Ejemplos: `investigador-normativo → analista-legal`, `redactor-legal → corrector-estilo-ortografia-legal`.

## Cómo se agregan herramientas

Las tools viven en `backend/tools/` (una por archivo) y se descubren automáticamente con `ToolRegistry`. Para autorizar una tool, agregarla a `config/permissions.yaml`. Solo declarar en un skill herramientas que existan realmente.

## Cómo probar un skill

- Ejecutar los tests de infraestructura: `pytest tests/test_skills.py -v`.
- Revisar los `evals/*.json` de cada skill.
- Ejecutar toda la suite: `pytest -v`.

## Matriz de responsabilidades

| Skill | Hace | No hace principalmente |
| --- | --- | --- |
| investigador-normativo | Recupera y verifica derecho | No decide por sí solo el caso |
| analista-legal | Aplica derecho a hechos | No busca exhaustivamente normativa |
| auditor-compliance | Evalúa requisitos | No reconstruye principalmente secuencia |
| revisor-procedimental | Revisa trayectoria del expediente | No sustituye auditoría general |
| analista-politico | Analiza impactos y escenarios | No determina legalidad |
| consultor-redaccion | Estructura comunicación institucional | No crea principalmente actos jurídicos |
| redactor-legal | Redacta actos/documentos jurídicos | No inventa fundamento |
| corrector-estilo-ortografia-legal | Corrige forma y coherencia lingüística | No altera decisión jurídica |
