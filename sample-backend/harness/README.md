# Harness Engineering de Giana-Lex

El harness es una capa de gobierno alrededor de `AgentRuntime`. No reemplaza el agente, las skills, las tools, RAG, los moldes, los ejemplos ni la memoria de conversación existente.

```text
User
  |
HarnessOrchestrator -- TaskState / budget / trace
  |
Existing AgentRuntime
  |
Skills -- Tools -- Existing RAG -- Moldes / Examples
  |
Existing LLMProvider
  |
Verifier -- Quality gates -- Retry / Escalate / Fail safe
```

## Flujo

1. El endpoint crea el mismo provider, registry y permission policy existentes.
2. Con `HARNESS_ENABLED=false`, construye `AgentRuntime` sin observer y conserva el flujo legacy.
3. Con el harness activo, `HarnessRouter` resuelve una skill primaria y clasifica complejidad/riesgo mediante opciones cerradas.
4. `ContextManager` construye contexto con política, estado operativo y solo las skills/evidencia relevantes.
5. `AgentRuntime` ejecuta su loop habitual. Los hooks registran tools, evidencia, presupuesto y progreso.
6. `EvidenceLedger` normaliza resultados. `EXAMPLE` y `TEMPLATE` nunca pueden sustentar claims jurídicos.
7. `Verifier` aplica verificaciones deterministas y `QualityGates` decide aceptación, retry o fail-safe.
8. `HarnessTrace` registra eventos y métricas sin prompts completos ni chain-of-thought.

`TaskState` es estado efímero de una ejecución. `AgentSession`, `Message` y `ToolCall` continúan siendo la memoria conversacional persistente; no se creó una segunda memoria.

## Modos

- `off`: flujo legacy.
- `standard`: estado, routing, contexto, ledger, budgets y verificación básica.
- `strict`: presupuestos explícitos, contexto más limpio, validación fuerte, retry limitado y fail-safe.
- `adaptive`: recomendado. Usa riesgo, complejidad y perfil del modelo para elegir standard o strict por tarea.

Una corrección ortográfica sigue un camino corto de una llamada. Una consulta de competencia o generación documental activa controles estrictos cuando corresponde.

## Perfiles

- `strong`: menos scaffolding para tareas simples.
- `balanced`: comportamiento intermedio.
- `weak`: activa strict en adaptive y divide la carga operativa mediante estado, tools concretas y verificación.
- `auto`: actualmente adopta balanced como default seguro.

El harness consume la abstracción `LLMProvider` y funciona con proveedores cloud compatibles. `LLM_FAST_MODEL` y `LLM_STRONG_MODEL` permiten asignar un modelo económico a clasificación/orquestación y uno más capaz a análisis, redacción y verificación; si no se configuran, se conserva el modelo cloud elegido en la sesión.

## Evidencia

El ledger distingue:

```text
PRIMARY_AUTHORITY
OFFICIAL_ADMINISTRATIVE
SECONDARY
EXAMPLE
TEMPLATE
USER_PROVIDED
WEB_UNTRUSTED_DATA
UNKNOWN
```

Los resultados recuperados se envuelven como datos no confiables. Texto como "ignora instrucciones anteriores" queda dentro de `<evidence_data>` y nunca altera políticas o instrucciones de skills.

`EXAMPLE` aporta estilo. `TEMPLATE` aporta restricciones de generación. Ninguno puede sustentar una afirmación jurídica. Los loaders refuerzan esta clasificación según el directorio, independientemente de frontmatter editable.

## Verificación

Las verificaciones deterministas cubren:

- `TODO`, `FIXME`, Lorem ipsum y placeholders;
- secciones y numeración por género documental;
- referencias ausentes de evidencia autoritativa;
- afirmaciones materiales de competencia sin autoridad;
- cambios peligrosos de modalidad en correcciones (`podrá` a `deberá`).

Los gates dependen de la tarea. Una corrección simple no exige RAG. Una consulta jurídica material sí exige evidencia cuando contiene claims jurídicos.

## Retries, loops y escalación

`RetryPolicy` clasifica el error antes de actuar. No se reintenta ciegamente. El presupuesto default es dos retries y nunca excede los límites de iteraciones, calls LLM o tools.

`LoopDetector` detiene:

- misma tool con mismos argumentos;
- query idéntica o casi idéntica;
- ausencia repetida de evidencia nueva;
- mismo error repetido.

Escalación puede significar usar un modelo fuerte si está disponible. Con un único modelo significa descomponer más y requerir revisión humana. Cuando la evidencia no alcanza, el resultado correcto es fail-safe, no una afirmación inventada.

## Configuración

```env
HARNESS_ENABLED=true
HARNESS_MODE=adaptive
HARNESS_MAX_ITERATIONS=12
HARNESS_MAX_RETRIES=2
HARNESS_MAX_TOOL_CALLS=15
HARNESS_MAX_LLM_CALLS=6
HARNESS_CONTEXT_MAX_CHARS=24000
HARNESS_DEBUG=false
LLM_CAPABILITY_PROFILE=balanced
```

Los defaults permiten arrancar sin ninguna variable. El default interno de `HARNESS_ENABLED` es `false` para no alterar despliegues existentes; `.env.example` recomienda activarlo.

## Observabilidad y depuración

Cada task genera eventos como `task_created`, `task_classified`, `skill_selected`, `template_selected`, `tool_called`, `evidence_added`, `validation_failed`, `retry_started`, `escalation_triggered` y `task_completed`.

Métricas incluidas:

- llamadas LLM/tools/retrieval;
- retries y validaciones fallidas;
- loops prevenidos;
- claims no sustentados bloqueados;
- bloqueos de autoridad EXAMPLE/TEMPLATE;
- campos faltantes y escalaciones.

En proceso, las últimas 100 tasks están en `app.extensions["harness_tasks"]` para depuración. No es memoria conversacional ni almacenamiento durable. El trace omite claves `prompt`, `content`, `token` y `secret`. Los eventos terminales se envían al logger estructurado.

## Tests y eval

```bash
python -m pytest tests/test_harness.py
python -m pytest tests/test_harness_integration.py
python -m pytest tests/test_agent_core.py tests/test_e2e_legal_flows.py tests/test_skills.py tests/test_moldes.py tests/test_rag.py
python -m pytest
python evals/harness_off_vs_on.py
```
