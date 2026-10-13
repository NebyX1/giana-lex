# Informe técnico de Giana-Lex

> Este documento conserva el diagnóstico anterior al rediseño de ejemplos. El estado implementado y las mediciones actuales están en [Informe-Rediseño-Giana-Lex.md](Informe-Rediseño-Giana-Lex.md) y [docs/resoluciones-de-ejemplo.md](docs/resoluciones-de-ejemplo.md).

**Fecha de revisión:** 23 de septiembre de 2026  
**Alcance:** revisión de la estructura del repositorio, ejecución principal, frontend, backend, persistencia, conexión con Ollama, búsqueda de modelos, módulo de conocimiento jurídico/RAG, autenticación, habilidades, `sample-backend`, pruebas y estado operativo local.

## 1. Resumen ejecutivo

Giana-Lex contiene dos implementaciones de backend que deben distinguirse:

1. **El MVP activo**, compuesto por `backend/` y `frontend/`. Es el que corresponde al flujo visible de nueva consulta: React llama a Flask; Flask mantiene las transiciones y el estado; PydanticAI llama a un modelo compatible con OpenAI; los documentos se generan como salida estructurada y luego se exportan a DOCX.
2. **`sample-backend/`**, una implementación más amplia y modular que incluye proveedores configurables, RAG híbrido, herramientas, sesiones, casos jurídicos y un arnés de gobierno de agentes. Tiene valor de referencia y contiene piezas más completas, pero no es el proceso que utiliza el frontend principal del directorio `frontend/`.

En el MVP la cadena principal es:

```text
React/Vite
  -> Flask (/api)
    -> autenticación, CSRF y autorización
    -> Orchestrator + ConversationState
      -> búsqueda local BM25 en backend/examples
      -> búsqueda opcional de tipologías y antecedentes oficiales
         (base relacional + FastEmbed + Qdrant)
      -> molde backend/molds/resolucion_basica.md
      -> PydanticAI/AsyncOpenAI
         -> Ollama OpenAI-compatible http://localhost:11434/v1
      -> formulario dinámico
      -> borrador estructurado
      -> revisión, aprobación y exportación DOCX
```

El entorno local inspeccionado tiene Ollama disponible y el modelo configurado `glm-5.2:cloud`. El endpoint `/api/tags` y el endpoint compatible `/v1/models` respondieron correctamente. Qdrant no está escuchando en `localhost:6333`; además, la base legal que realmente utiliza `DATABASE_URL` (`backend/instance/giana_lex.db`) no tiene tipologías ni resoluciones. Por tanto, el RAG jurídico está implementado en el código y puede habilitarse, pero no está operativo en la configuración actual.

La respuesta rápida cuando no hay un antecedente comparable sí está implementada en el MVP actual. El buscador local exige soporte léxico mínimo para aceptar un ejemplo; si no lo encuentra, el intake devuelve un formulario genérico local sin llamar al LLM. También hay un límite de ocho segundos para la preparación inicial: al agotarse, se entrega el formulario genérico y los resultados tardíos no sustituyen la respuesta que ya recibió el usuario.

## 2. Inventario del repositorio

| Ruta | Función | Estado |
|---|---|---|
| `backend/` | Flask, orquestación, modelos de salida, persistencia, identidad, conocimiento legal y herramientas | Implementación principal |
| `frontend/` | React 18 + Vite + Fluent UI | Interfaz principal |
| `backend/examples/` | 11 modelos administrativos Markdown | Catálogo local usado por BM25 |
| `backend/molds/` | Plantilla base de resolución | Molde de redacción |
| `backend/data/legal/idl/resolutions/` | 151 directorios con HTML, texto normalizado y metadatos | Corpus descargado/normalizado |
| `backend/data/giana_test.sqlite3` | Estado conversacional y datos legales preparados para pruebas | Tiene datos legales |
| `backend/instance/giana_lex.db` | Base indicada por el `.env` actual para el servicio legal | Tiene usuario, pero corpus legal vacío |
| `backend/legal_knowledge/` | Taxonomía, resoluciones, importador, parser, indexación Qdrant y API administrativa | RAG jurídico del MVP |
| `sample-backend/` | Backend alternativo de mayor alcance | No es el camino principal del frontend actual |
| `sample-giana/` | Paquete Electron/Vite adicional | Prototipo/cliente alternativo |
| `docs/` | Documentación y catálogo de modelos | Referencia |
| `pytest.ini`, `alembic.ini`, `README.md` | Pruebas, migraciones y operación | Configuración del proyecto |

El repositorio tiene cambios locales no confirmados y artefactos de base de datos WAL/SHM. Este informe describe el estado que encontré sin descartar esos cambios.

### Tecnologías

- **Backend MVP:** Python, Flask 3.1, SQLAlchemy/Flask-SQLAlchemy, Pydantic 2, PydanticAI, OpenAI Python SDK, SQLite, Alembic, `rank-bm25`, `python-docx`, `qdrant-client`, FastEmbed, `lxml`, `requests`, `pypdf` y librerías de autenticación/correo.
- **Frontend:** React 18.3, Fluent UI 9, Vite 7, iconos Fluent y `fetch` con cookies/CSRF.
- **Backend alternativo:** Flask, SQLAlchemy, Redis/MariaDB/Qdrant configurables, `httpx`, módulos de RAG, importadores nacionales/departamentales y un runtime de herramientas.
- **Servicios externos/locales:** Ollama para LLM; Qdrant para vectores legales; SMTP para OTP/correo; fuentes `gub.uy` para importar normativa y resoluciones.

## 3. Cómo se inicia y cómo se conectan las piezas

### Backend principal

`backend/wsgi.py` expone la aplicación Flask creada en `backend/app.py`. El README propone iniciar desde la raíz con:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python backend\app.py
```

La aplicación inicializa Flask, SQLAlchemy, Flask-Login, CSRF, mail, rate limiting, CORS y Talisman. También registra el blueprint de autenticación, administración de usuarios y conocimiento legal, además de comandos CLI para administración.

En desarrollo, el frontend se ejecuta desde `frontend/` con `npm run dev`. Vite redirige `/api` hacia `http://127.0.0.1:5000`, por lo que el navegador no llama directamente ni a Ollama ni a Qdrant.

### Configuración efectiva encontrada

`backend/config.py` carga `backend/.env` y resuelve la configuración de esta forma:

- Si existe `LLM_BASE_URL`, lo usa tal cual; si no, transforma `OLLAMA_BASE_URL=http://localhost:11434` en `http://localhost:11434/v1`.
- Si falta `LLM_API_KEY` pero existe `OLLAMA_BASE_URL`, genera la clave lógica `ollama-local`. Ollama local normalmente no exige una clave real.
- El modelo se toma de `LLM_MODEL` o, como compatibilidad, de `OLLAMA_MODEL`.
- El timeout general del LLM es 60 segundos y el timeout de preparación inicial (`INTAKE_TIMEOUT_SECONDS`) es 8 segundos.
- El estado conversacional usa `backend/data/giana_test.sqlite3` por defecto.
- El servicio de conocimiento jurídico usa `DATABASE_URL`; en el entorno revisado apunta a `backend/instance/giana_lex.db`.
- Qdrant se configura en `http://localhost:6333`.
- El indexador legal usa por defecto `jinaai/jina-embeddings-v2-base-es` con dimensión 768. La variable `FASTEMBED_MODEL` presente en el `.env` no reemplaza ese valor en el `Settings` del MVP; para hacerlo debe usarse `LEGAL_EMBEDDING_MODEL`.

La configuración efectiva observada fue:

```text
LLM_BASE_URL       http://localhost:11434/v1
LLM_MODEL          glm-5.2:cloud
LLM_CONFIGURED     True
INTAKE_TIMEOUT     8 segundos
EXAMPLES_DIR       backend/examples
LEGAL DATABASE     backend/instance/giana_lex.db
QDRANT_URL         http://localhost:6333
```

## 4. Flujo completo de una consulta

### 4.1 Inicio y preparación

1. El usuario escribe en `ChatPane`.
2. `frontend/src/api.js` obtiene un token CSRF si es necesario y envía `POST /api/conversations` con cookies de sesión.
3. Flask valida autenticación y la configuración de agentes. Si el LLM no está configurado, el endpoint no inicia la conversación, aunque el formulario genérico local pueda existir internamente.
4. `Orchestrator.create_conversation` crea un `ConversationState`, guarda el pedido original y pasa de `NEW` a `SEARCHING_EXAMPLES`.
5. La preparación se ejecuta en un hilo con un máximo de cuatro trabajos simultáneos y un `BoundedSemaphore`. El hilo trabaja sobre una copia del estado para que una respuesta tardía no sobrescriba el formulario que ya se entregó.
6. La solicitud espera hasta `INTAKE_TIMEOUT_SECONDS`, por defecto 8 segundos. Si el tiempo se agota o un servicio no responde, se registra `intake_fallback`, se entrega un formulario genérico y se corta la posibilidad de persistir el resultado tardío.

### 4.2 Clasificación y antecedentes

Cuando el servicio legal está disponible, el orquestador busca primero tipologías activas. Si obtiene candidatos, puede solicitar a `PydanticAgents.classify_resolution` que elija únicamente uno de esos identificadores. Después intenta recuperar antecedentes oficiales para la tipología seleccionada.

En paralelo se ejecuta `tools/search_examples.py`, que busca en los Markdown locales. Finalmente se carga el molde `backend/molds/resolucion_basica.md` y se entrega al intake una combinación de:

- pedido original;
- candidatos locales;
- candidatos oficiales/taxonomía, si existen;
- referencias oficiales;
- molde de redacción.

La clasificación y el intake no pueden iniciar búsquedas adicionales del conocimiento jurídico por sí mismos. La recuperación la controla el orquestador para acotar tiempos y fuentes.

### 4.3 Formulario

El resultado estructurado del intake puede ser un formulario dinámico o un borrador si ya tiene todos los datos. `DynamicForm.jsx` pinta campos de texto, área de texto, número, booleano, selección y fecha. El backend vuelve a validar tipos, campos obligatorios y opciones; la validación del navegador no es la autoridad final.

La transición normal es:

```text
NEW -> SEARCHING_EXAMPLES -> COLLECTING_INFO -> DRAFT_REVIEW -> APPROVED
```

El estado registra transiciones, herramientas, consumo LLM, duración, candidatos y advertencias en los últimos 50 eventos. No guarda prompts completos ni claves.

### 4.4 Generación, revisión y aprobación

`POST /api/conversations/<id>/form` mezcla respuestas nuevas con respuestas previas, valida el formulario y llama al agente de borrador. El agente recibe el molde, las respuestas, los ejemplos seleccionados y las referencias oficiales. Los ejemplos se presentan como estructura de estilo; no deben tratarse como autoridad jurídica.

Si faltan datos indispensables, el agente puede pedir una ronda adicional de formulario. Si no, devuelve un borrador estructurado con secciones administrativas. El usuario puede llamar a `revise`, que conserva el borrador y aplica instrucciones de cambio, o a `approve`, que deja el documento listo para exportar. `GET /export` genera el DOCX únicamente cuando la conversación está aprobada.

### 4.5 Habilidades posteriores

`backend/skills/registry.py` descubre dinámicamente módulos que exponen una instancia `Skill`. El MVP incluye:

- `legal_risk`: detecta riesgos potenciales de competencia, motivación, presupuesto, procedimiento, notificación, plazos y contratación sin declarar ilegalidad sin fuente.
- `political_risk`: analiza actores afectados, reacciones posibles y conflictos institucionales, distinguiendo hechos, hipótesis e información faltante.

Las habilidades se ejecutan después de la aprobación y permiten como máximo una ronda adicional de preguntas esenciales.

## 5. Conexión con Ollama

### MVP activo

`backend/llm.py` crea un `AsyncOpenAI` con:

```text
base_url = http://localhost:11434/v1
api_key  = ollama-local
timeout  = 60 s
max_retries = 1
```

Ese cliente se entrega a `OpenAIProvider` de PydanticAI y se construye un `OpenAIChatModel` con `glm-5.2:cloud`. En consecuencia, el MVP no usa la API nativa `/api/generate` de Ollama: usa la compatibilidad de Ollama con OpenAI Chat Completions bajo `/v1`.

El frontend nunca conoce esta URL ni la clave. Todas las llamadas pasan por Flask. El backend fija temperatura y máximo de tokens desde configuración, registra uso/duración y reintenta la validación de salida una sola vez. No existe streaming SSE/WebSocket en el flujo principal: cada acción espera una respuesta HTTP completa.

### Comprobación realizada

- `GET http://127.0.0.1:11434/api/tags`: respondió `200` y devolvió modelos instalados/disponibles.
- `GET http://127.0.0.1:11434/v1/models`: respondió `200` y mostró, entre otros, `glm-5.2:cloud`.
- Esto demuestra conectividad del servidor, no que el modelo haya completado una consulta del usuario ni que tenga un rendimiento adecuado.

### Qué ocurre si el LLM no responde

El timeout de intake cubre la preparación inicial. Si no hay antecedente comparable, `PydanticAgents.intake` puede devolver directamente un `generic_intake` con consumo LLM cero. Si la búsqueda o la llamada se bloquea, `Orchestrator` entrega el formulario local al llegar a ocho segundos. El resto del flujo sigue requiriendo que exista una instancia de agentes; por eso una instalación sin ningún LLM configurado debe mostrar una condición de configuración antes de aceptar una consulta.

## 6. Modelos, prompts y salidas estructuradas

`backend/schemas.py` define los contratos Pydantic para intake, formularios, borradores, revisiones, referencias y habilidades. El LLM no controla la máquina de estados: devuelve datos con esquema y Python decide qué transición es válida.

`PydanticAgents._run` construye un agente con `PromptedOutput`, instrucciones globales para no inventar datos y prioridad del molde. Según la operación, limita el uso a dos o cinco llamadas/iteraciones y puede adjuntar las herramientas legales. El intake y la clasificación inicial no reciben esas herramientas; borrador, revisión y habilidades sí pueden recibirlas cuando el servicio jurídico está disponible.

La política de contenido distingue tres fuentes:

- **Fuentes oficiales:** referencias legales recuperadas del corpus jurídico.
- **Ejemplos:** documentos usados para estructura y estilo.
- **Plantilla:** orden y campos esperados del documento.

La aplicación intenta impedir que el modelo convierta un ejemplo en una norma aplicable, aunque la búsqueda de archivos Markdown no valida por sí misma el campo `authority_level` de sus frontmatter. La instrucción del agente es la barrera principal para esa distinción.

## 7. Cómo busca y usa los modelos administrativos

### Catálogo disponible

`backend/examples/` contiene 11 modelos:

1. compensación de funcionario;
2. transferencia presupuestal;
3. contratación de funcionario;
4. contratación zafral;
5. arrendamiento de obra;
6. concurso;
7. renovación zafral;
8. adjudicación de licitación;
9. aprobación de convenio;
10. traslado de funcionario;
11. exoneración de patente.

El catálogo y sus fuentes están documentados en `docs/modelos-administrativos.md`. Los Markdown con enlaces oficiales son antecedentes editoriales; el buscador local no los convierte automáticamente en registros del corpus oficial.

### Algoritmo local

`search_examples.py` lee los `.md` de la carpeta en cada búsqueda y:

1. normaliza minúsculas y acentos con NFKD;
2. tokeniza palabras;
3. elimina términos genéricos comunes de una solicitud;
4. calcula BM25 sobre el texto completo;
5. suma un componente de coincidencia léxica;
6. devuelve los mejores candidatos, por defecto tres, con nombre, título, puntuación y extracto de hasta 1.200 caracteres.

`has_lexical_support` exige al menos dos términos de contenido compartidos. Si ningún candidato supera esa compuerta, el sistema limpia los matches y no le presenta al modelo un antecedente forzado.

Esta búsqueda no usa embeddings, Qdrant, chunks ni índice persistente. Es rápida, local y fácil de actualizar agregando un Markdown, pero no entiende bien paráfrasis, sinónimos complejos o relaciones jurídicas que no compartan vocabulario.

### Carga para el borrador

`load_selected_examples` solo abre archivos que permanecen dentro de la raíz de ejemplos, limita a dos archivos y a 10.000 caracteres por archivo. Es una medida de seguridad contra rutas arbitrarias y también limita el contexto enviado al LLM.

### Formulario genérico

`backend/intake_fallback.py` adapta los campos al texto de la solicitud. Para contrataciones, zafrales y arrendamiento de obra pide, entre otros:

- decisión y organismo competente;
- fundamentos, expediente y normativa si existen;
- persona o entidad contratada;
- funciones/objeto;
- plazo;
- remuneración;
- imputación presupuestal;
- procedimiento de selección y comunicaciones.

Para solicitudes no contractuales ofrece destino, fechas, recursos, fundamentos y otros datos generales. El formulario permite avanzar aunque no exista un antecedente exacto y advierte que deberá completarse la información jurídica faltante.

## 8. Conocimiento legal y RAG del MVP

### Modelo de datos

`backend/legal_knowledge/models.py` define, entre otras, estas entidades:

- `TaxonomyNode`: familia, tipo y subtipo jerárquico;
- `Resolution`: identidad, número, año, título, fuente, estado y versión;
- `ResolutionRevision`: texto vigente dividido en VISTO, RESULTANDO, CONSIDERANDO, ATENTO y RESUELVE;
- `ResolutionTaxonomyAssignment`: vínculo canónico, secundario, relacionado o ejemplo negativo;
- `ResolutionOriginal`: archivo/HTML original;
- `ResolutionCatalogEntry`: catálogo de importación;
- `SyncOutbox`: trabajos pendientes de sincronizar con el índice;
- `LegalAuditEvent`: auditoría de cambios.

La base relacional es la fuente de verdad. Qdrant es un índice derivado y no debe editarse como si fuera la base canónica.

### Importación y normalización

El importador acepta HTTPS de `gub.uy` y restringe la ruta de la Intendencia de Lavalleja (`/intendencia-lavalleja/institucional/normativa`). Valida redirecciones, DNS público/no privado, tipo HTML, tamaño máximo de 5 MB, timeout, reintentos y frecuencia entre solicitudes.

`parser.py` usa `lxml` para identificar número de resolución, encabezado, secciones administrativas y firmantes. El resultado normalizado se guarda con hash y metadatos. Los comandos Flask relevantes son `legal seed`, `import-url`, `index-pending`, `retry`, `check-index`, `rebuild-index`, `status`, `manifest` y `crawl-catalog`.

### Indexación vectorial

`legal_knowledge/indexing.py` usa FastEmbed de forma perezosa y Qdrant con dos colecciones:

- `giana_resolution_taxonomy_v2`: un vector por subtipo/tipología;
- `giana_resolution_examples_v2`: vectores de antecedentes oficiales.

Cada resolución genera un chunk de metadata y chunks de sus secciones, con cortes de aproximadamente 1.400 caracteres. Los puntos tienen identificadores UUID deterministas y payload con resolución, revisión, año, roles taxonómicos, sección, estado, versión, URL y texto. Se crean índices de payload para filtros por estado, tipología, número y sección.

La búsqueda de tipologías filtra nodos activos. La búsqueda de resoluciones exige estado activo y pertenencia a la tipología. El `SyncOutbox` permite que una mutación relacional quede pendiente si Qdrant está temporalmente caído; existen comandos para reintentar, reconstruir y verificar consistencia. El verificador identifica puntos faltantes, obsoletos, huérfanos, duplicados o inactivos sin reparar destructivamente de forma automática.

### Herramientas disponibles para el agente

`legal_knowledge/agent_tools.py` expone:

- `search_resolution_types`;
- `get_resolution_type`;
- `search_resolution_examples`;
- `get_resolution`;
- `get_required_facts`.

Solo se conectan a agentes posteriores al intake inicial. El orquestador ya hace la recuperación inicial de forma determinista; el agente puede consultar el servicio en borrador, revisión o habilidades cuando corresponde.

### Estado real observado

| Base/servicio | Estado observado |
|---|---|
| `backend/data/giana_test.sqlite3` | 250 nodos, 151 resoluciones, 151 revisiones, 136 asignaciones, 391 trabajos de outbox y 5 conversaciones |
| `backend/instance/giana_lex.db` | 1 usuario; 0 nodos, 0 resoluciones, 0 revisiones, 0 asignaciones y 0 outbox |
| Qdrant `localhost:6333` | No responde; conexión rechazada |
| Archivos `backend/data/legal/idl/resolutions` | 151 directorios de resoluciones con original/normalizado/metadatos |

El `.env` actual hace que el servicio legal use `backend/instance/giana_lex.db`, no la base poblada de `backend/data/giana_test.sqlite3`. Esta discrepancia explica por qué el código puede estar preparado para RAG y, a la vez, el runtime no devolver antecedentes oficiales. Para activarlo hay que elegir una única base legal, aplicar migraciones/seed, levantar Qdrant, descargar o disponer del modelo de embeddings y procesar el outbox o reconstruir los índices.

El buscador local de `backend/examples` sigue funcionando aunque Qdrant esté detenido, porque son dos caminos distintos.

## 9. API y frontend

### Endpoints principales del MVP

| Endpoint | Uso |
|---|---|
| `GET /api/health` | Estado del LLM, ejemplos, molde y conocimiento legal |
| `GET/POST /api/auth/*` | CSRF, sesión, login, OTP y logout |
| `GET/POST /api/conversations` | Listar y crear conversaciones |
| `GET/DELETE /api/conversations/<id>` | Consultar/eliminar una conversación |
| `POST /api/conversations/<id>/form` | Entregar respuestas y generar borrador |
| `POST /api/conversations/<id>/revise` | Revisar borrador |
| `POST /api/conversations/<id>/approve` | Aprobar borrador |
| `GET /api/conversations/<id>/export` | Descargar DOCX aprobado |
| `GET /api/skills` | Habilidades disponibles |
| `POST /api/conversations/<id>/skills/<key>` | Ejecutar una habilidad |
| `/api/settings/legal/*` | Taxonomía, resoluciones, importación, indexación y consistencia |

`frontend/src/api.js` centraliza `fetch`, incluye credenciales, obtiene CSRF y añade `X-CSRFToken` en mutaciones. No hay conexión directa de React con Ollama.

### Componentes principales

- `App.jsx`: sesión, tema, navegación, lista de conversaciones y vistas de configuración.
- `ChatPane.jsx`: mensajes, estado de procesamiento y formulario dinámico.
- `DynamicForm.jsx`: render del esquema recibido y envío de respuestas.
- `RightPanel.jsx`: antecedentes oficiales, ejemplos consultados y borrador.
- `DraftPanel.jsx`: revisión y aprobación.
- `SettingsCenter`/`KnowledgeCenter`: gestión del conocimiento legal y configuración.

La interfaz de chat, autenticación y centro de conocimiento usan APIs reales. Algunas vistas administrativas siguen siendo prototipo local: `NormsManager` tiene filas codificadas y un diálogo de importación sin contrato backend completo; `ProviderManager`, usuarios y auditoría conservan estado o filas de ejemplo en el componente. No debe interpretarse la presencia de esas pantallas como prueba de que cada acción administrativa persiste en servidor.

El build de producción genera un bundle JavaScript de aproximadamente 638 kB minificado, por encima de la advertencia de 500 kB de Vite; no impide compilar, pero convendría aplicar división de código si el cliente crece.

## 10. Persistencia, identidad y seguridad

### Persistencia

El MVP tiene dos responsabilidades de SQLite:

- `Storage` guarda conversaciones como JSON con `ConversationState`, propietario, timestamps y eventos.
- `LegalKnowledgeService` usa SQLAlchemy para taxonomía, resoluciones, revisiones, outbox y auditoría.

La separación permite que el estado conversacional funcione con archivos locales aunque el índice legal no esté disponible, pero también permite que `DATABASE_URL` y la base de conversaciones apunten a archivos diferentes, como ocurre ahora.

### Autenticación y controles

- Flask-Login mantiene la sesión.
- Contraseñas se procesan con Argon2.
- El login puede requerir código OTP de seis dígitos por correo.
- CSRF está habilitado en mutaciones.
- Rate limiting, CORS con orígenes configurados y Talisman/cabeceras de seguridad se inicializan en Flask.
- Los cambios de conocimiento legal requieren roles `corpus_curator` o `technical_admin`.
- Las respuestas incluyen `X-Request-ID` y `Cache-Control: no-store`.

### Hallazgo de seguridad

`backend/.env` existe en el equipo y contiene valores que parecen secretos operativos —clave de aplicación, contraseña SMTP, clave de proveedor y material de cifrado— aunque el archivo esté ignorado por Git. No se reproducen aquí. Deben mantenerse fuera de commits, rotarse si estuvieron expuestos o compartidos, y reemplazarse por secretos de un gestor seguro en despliegue. También debe comprobarse que los archivos `.env` del `sample-backend` no se distribuyan.

## 11. `sample-backend`: segunda arquitectura

`sample-backend` funciona como una aplicación distinta, con su propio `app.py`, configuración, migraciones, modelos, API y base de datos. Incluye:

- sesiones de agentes y runtime de herramientas;
- proveedores OpenAI, Featherless, Ollama y compatibles personalizados;
- credenciales cifradas por usuario;
- endpoints de proveedores, documentos, casos, normativa nacional y departamental;
- `harness/` para presupuesto, trazas, ledger de evidencia, verificación, reintentos y fail-safe;
- `rag/` con Qdrant, FastEmbed, BM25, recuperación densa, fusión por Reciprocal Rank Fusion, filtros, reranking opcional y expansión por grafo de modificadores;
- `impo/` para normativa nacional y `depto/` para normativa departamental;
- flujos legales durables, tareas humanas, precedentes y ledger de claims/evidence.

### Ollama en `sample-backend`

`app/services/provider_service.py` define el proveedor `ollama` con base por defecto `http://localhost:11434/v1` y autenticación `none`. `llm/openai_compatible.py` envía `POST /chat/completions` con `model`, `messages`, herramientas y `tool_choice=auto`; usa `httpx`, timeouts separados de conexión/lectura y parsea texto, tool calls y uso. OpenAI es una excepción que usa `/responses`.

### RAG en `sample-backend`

El recuperador alternativo puede buscar en colecciones nacionales y departamentales, combinar BM25 con vectores densos, limitar `top_k`, filtrar por categoría/tipo/año/caso/fuente y devolver evidencias trazables. Es más general que el RAG legal específico del MVP, pero exige su propia configuración de bases, Qdrant y corpus. No se activa simplemente por ejecutar `backend/app.py`.

## 12. Pruebas y validación ejecutadas

- Backend: `backend\.venv\Scripts\python.exe -m pytest -q` → **48 passed**.
- Frontend: `npm run build` → compilación correcta; Vite transformó 2.125 módulos y emitió la advertencia de bundle grande indicada arriba.
- Ollama: `/api/tags` y `/v1/models` → HTTP 200.
- Qdrant: `http://127.0.0.1:6333/collections` → conexión rechazada.
- Revisión de configuración: se confirmaron URL, modelo, timeout, rutas de bases y directorio de ejemplos sin imprimir claves.

El resultado de pruebas no equivale a una prueba de integración contra Ollama: la suite usa mocks/TestModel y no consume el modelo remoto por defecto. Tampoco valida un ciclo RAG real mientras Qdrant esté detenido.

## 13. Riesgos y prioridades técnicas

### Prioridad alta

1. **Unificar la base legal activa.** Decidir si el runtime debe usar `backend/data/giana_test.sqlite3` o una base de producción separada; migrar/sembrar la elegida y verificar que usuarios, conversaciones y corpus no se mezclen accidentalmente.
2. **Levantar y comprobar Qdrant.** Crear las dos colecciones, asegurar dimensión 768 compatible con el modelo de embeddings y ejecutar `index-pending`/`rebuild-index`.
3. **Configurar el embedding correcto.** Usar explícitamente `LEGAL_EMBEDDING_MODEL` y documentar caché, descarga y tamaño del modelo.
4. **Rotar secretos locales.** Revisar `.env` y `sample-backend/.env` antes de compartir el proyecto o crear un despliegue.

### Prioridad media

5. **Aclarar la documentación.** El README todavía describe “RAG vectorial” como fuera del MVP, aunque `backend/legal_knowledge` ya lo implementa. Debe explicar qué parte es local BM25 y qué parte requiere Qdrant.
6. **Instrumentar tiempos por etapa.** El evento de intake ya registra duración; conviene exponer por separado búsqueda local, búsqueda legal, embedding, Qdrant y LLM para diagnosticar bloqueos.
7. **Mejorar el buscador de modelos.** BM25 es suficiente para un catálogo pequeño, pero conviene agregar sinónimos, metadatos de tipología y una ruta vectorial opcional cuando se necesite recuperar por paráfrasis.
8. **Completar pantallas administrativas.** Conectar las vistas que todavía usan filas/estado local con los endpoints de configuración o marcarlas explícitamente como prototipo.
9. **Considerar streaming o progreso por etapa.** El frontend solo ve un spinner mientras una solicitud HTTP está abierta; SSE/WebSocket o polling permitirían comunicar “buscando”, “formulario genérico por timeout” y “borrador”.

### Prioridad de calidad jurídica

10. Mantener separadas las etiquetas de ejemplo y autoridad en cada recuperación.
11. Exigir referencias oficiales para afirmaciones normativas.
12. No presentar una plantilla genérica como precedente jurídico.
13. Registrar la versión de la taxonomía, revisión y fuente que sustentaron cada borrador aprobado.

## 14. Diagnóstico final

Giana-Lex ya tiene una base funcional sólida para el flujo “consulta → formulario → resolución → revisión → aprobación”: el backend controla el estado, el modelo devuelve estructuras Pydantic, el catálogo local se consulta rápidamente y existe un fallback genérico que evita quedar bloqueado buscando un antecedente idéntico.

La conexión con Ollama está correctamente planteada mediante el protocolo OpenAI-compatible y está accesible en la máquina revisada. La búsqueda local de ejemplos no es RAG: es BM25 sobre Markdown. El RAG jurídico sí está diseñado —taxonomía relacional, resoluciones normalizadas, embeddings FastEmbed, Qdrant, filtros, outbox y herramientas—, pero la configuración efectiva no lo alimenta: el runtime apunta a una base legal vacía y Qdrant está apagado.

El paso que más valor aportaría ahora es poner en línea una única base legal poblada, iniciar Qdrant, indexar las 151 resoluciones ya presentes y probar una consulta de extremo a extremo midiendo: tiempo hasta el formulario, tipología seleccionada, antecedente oficial recuperado, llamada a Ollama, borrador y trazabilidad de fuentes.
