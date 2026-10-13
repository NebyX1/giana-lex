# Informe final: ejemplos y comprobación de resoluciones de Gianna Lex

**Fecha:** 23 de septiembre de 2026. **Aplicación intervenida:** `backend/` (Flask) y `frontend/` (React/Vite). `sample-backend/` no participa del flujo visible.

## Resultado funcional

El catálogo editorial es ahora persistente y compartido por Ajustes y las conversaciones. Una consulta recupera referencias locales antes de iniciar las etapas lentas de tipología o LLM; si estas se demoran, conserva las referencias y muestra un formulario utilizable. La ausencia de un tipo idéntico no elimina analogías. El panel de borrador permite comprobar una resolución nueva o una ya redactada antes de aprobarla. Una contradicción crítica, un informe de otra revisión o una comprobación contextual interrumpida impiden la aprobación; la exportación DOCX exige la misma huella del texto aprobado.

La navegación real de Ajustes permite buscar, filtrar, ver original y revisión, añadir un modelo interno, guardar una revisión, publicarla, suspenderla, archivarla, restaurarla, importar un archivo y probar la recuperación. Las mutaciones pasan por Flask, roles y CSRF. La prueba manual creó un modelo interno en una base aislada, lo publicó, lo recuperó como primer resultado de una búsqueda y lo vio como primera referencia en una consulta nueva. También comprobó un borrador cuyo RESULTANDO decía «clausura» y cuyo RESUELVE decía «paralización»: el panel mostró un hallazgo crítico y deshabilitó Aprobar.

## Base y carga inicial

La base activa configurada por `DATABASE_URL` es `backend/instance/giana_lex.db`; no se sustituyó por la base poblada de pruebas. Se incorporaron `example_documents`, `example_source_versions`, `example_revisions`, `example_import_batches` y `example_audit_events`, con migración `backend/migrations/versions/0003_editorial_examples.py`. Como esta instalación local no tenía tabla `alembic_version`, la creación de las tablas faltantes se realizó mediante `LegalKnowledgeDatabase.ensure_schema()`; la migración quedó preparada para instalaciones con historial Alembic.

Se ejecutó la carga inicial del `script#dataset` JSON del HTML proporcionado: **235 creadas**, distribuidas en **13 preferentes, 187 utilizables con ajustes, 33 excluidas y 2 pendientes**. Una segunda ejecución idéntica produjo **235 omitidas y 0 duplicadas**. El informe Markdown de selección se usó para comprender el corpus y no se indexó. El importador preserva texto y metadatos de fuente, hash declarado y hash realmente calculado, historial de versiones, decisiones editoriales y campos desconocidos. La identidad combina procedencia e ID externo y se concilia con departamento, número y fecha, sin fusionar actos por URL compartida. La importación valida todo el lote antes de escribir y aplica los cambios en una transacción. Admite HTML del catálogo, JSON y JSONL; ZIP queda fuera del contrato y se rechaza.

Para repetir la carga o previsualizar sus efectos:

```powershell
cd backend
.\.venv\Scripts\python.exe -m flask --app app import-examples ..\sample-resolutions\Catalogo-Gianna-Lex.html --preview
.\.venv\Scripts\python.exe -m flask --app app import-examples ..\sample-resolutions\Catalogo-Gianna-Lex.html
```

## Recuperación y alcance editorial

Los preferentes están habilitados como referencias editoriales, sin certificar sus citas. Los 187 ajustables participan como estructura y elementos reutilizables, con defectos y adaptaciones adjuntos; su texto original completo es consultable pero no está autorizado para imitación íntegra. Los 33 excluidos y 2 pendientes quedan fuera de la búsqueda positiva. Los 11 Markdown previos de `backend/examples/` siguen disponibles como ejemplos heredados de estructura, separados del lote importado.

`backend/example_catalog.py` implementa una sola búsqueda ponderada BM25 para Ajustes, intake, redacción y comprobación, con equivalencias funcionales y búsqueda progresiva por analogías. Mantiene índice local en memoria, invalida la caché tras cambios y consulta la versión de la base para detectar cambios de otros procesos. Recupera hasta 20 candidatos y selecciona hasta 5 referencias diversas para el flujo. El contexto de redacción usa hasta dos unidades administrativas completas y 360 palabras por referencia; evita cortar condiciones jurídicas a mitad de cláusula. Antes de incorporar una referencia se comprueba de nuevo su revisión y habilitación en la base.

El adaptador `backend/example_vector.py` puede fusionar rankings con FastEmbed/Qdrant usando RRF (constante 60), pero Qdrant no respondía en `localhost:6333` y **no se pudo construir ni validar el índice vectorial**. El buscador local sí funciona sin ese servicio. Para construirlo cuando esté operativo:

```powershell
cd backend
.\.venv\Scripts\python.exe -m flask --app app index-examples
```

El corpus legal activo carece de textos normativos completos verificados. Por ello, el comprobador informa por separado que existencia, contenido, versión temporal y aplicabilidad de normas no fueron contrastados; no convierte las citas de una resolución de Montevideo, Canelones o Maldonado en derecho aplicable a Lavalleja.

## Comprobación y controles

`backend/example_verification.py` ejecuta controles deterministas de padrones, expedientes, importes numéricos con `Decimal`, fechas, numerales, artículos, años citados, efecto y motivación. Se contrastó con los cuerpos reales LVR-004 (4876/4786), CAN-023 (UR 2584,80/2584,40), MVT-018 (clausura/paralización), MVT-021 (artículo .17/.16), MAL-013 (4118/2016 frente a 4118/2026) y MVP-033 (fundamento de prórroga). Una llamada contextual estructurada a Ollama, si está disponible, revisa los elementos sustantivos; el servidor acepta como evidencia del modelo sólo pasajes presentes literalmente en el borrador. Si la llamada falla, el estado se declara insuficiente y no valida la aprobación.

El informe guarda hash y revisión del borrador, cobertura, hallazgos con ubicación y evidencia, hechos pendientes, alcance de ejemplos, estado normativo, estado contextual y duración. El servidor rechaza aprobar una revisión diferente, fuentes suspendidas o modificadas, contradicciones críticas y comprobaciones incompletas. Una nota libre no resuelve una contradicción crítica: hace falta corregir y comprobar de nuevo. No se asigna un porcentaje ficticio de legalidad.

## Validación medida

Las pruebas automatizadas del backend terminaron con **65 aprobadas** tras los últimos ajustes; las nuevas pruebas cubren importación real, repetición, conflicto de fuente frente a edición publicada, catálogo, recuperación, controles de errores, API, aprobación y exportación. El build de Vite se completó. Una prueba E2E manual en navegador local confirmó las operaciones visibles; detectó además un import faltante de `Text` de Fluent UI en `DraftPanel.jsx`, corregido durante la verificación. Al repetir la consulta tras reiniciar Flask, la pantalla informó las cinco referencias reales y dejó de decir que no había antecedente.

En 20 consultas de ajuste se obtuvo Recall@5 de 20/20. En 20 consultas nuevas posteriores se obtuvo **19/20 (95%)**; falló MVC-015 para la paráfrasis de cesión de crédito a un banco. Este fallo permanece documentado, sin excepción codificada por ID. En AMD Ryzen 5 7430U (12 hilos), 100 búsquedas calientes dieron mediana **116,5 ms** y p95 **123,8 ms**; una primera búsqueda fría tardó **929,2 ms**. Tres consultas reales a Ollama `glm-5.2:cloud` devolvieron los referentes esperados MVP-003, LAV-004 y MVC-023 en **9,55 s, 5,79 s y 6,96 s**. Una comprobación contextual real mediante PydanticAI/Ollama tardó **21,99 s** y devolvió hallazgos estructurados. La prueba E2E del formulario usó un agente simulado y base temporal; no se presenta como ejecución real del LLM.

## Archivos principales y límites

Los servicios nuevos son `backend/example_catalog.py`, `backend/example_vector.py`, `backend/example_verification.py` y `backend/example_api.py`; la migración es `backend/migrations/versions/0003_editorial_examples.py`. La integración se realizó en `backend/app.py`, `backend/orchestrator.py`, `backend/agents.py`, `backend/state.py` y `backend/schemas.py`. La UI funcional está en `frontend/src/components/ExampleManager.jsx`, `frontend/src/components/CheckExistingDraft.jsx` y las adaptaciones de `App.jsx`, `SettingsCenter.jsx`, `RightPanel.jsx` y `DraftPanel.jsx`. Los contratos y comandos se detallan en `docs/resoluciones-de-ejemplo.md` y el README.

Quedan límites concretos: sin corpus normativo conectado no puede certificarse vigencia ni territorialidad de las normas; las cifras escritas en letras no se comparan exhaustivamente; algunos importes diferentes pueden corresponder a conceptos distintos y pedir revisión humana; la inferencia contextual del LLM puede tardar decenas de segundos; el vector opcional no se probó por indisponibilidad de Qdrant. El componente BM25 aún tiene una falsa negativa en la consulta de cesión de créditos señalada arriba.
