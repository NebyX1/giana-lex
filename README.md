# Giana Lex MVP

MVP experimental para validar un flujo de redaccion administrativa con Flask, Pydantic AI, React/Fluent UI y SQLite. Python controla todas las transiciones; el LLM solo genera contenido estructurado dentro de cada etapa.

## Requisitos

- Python 3.11 o superior
- Node.js 20 o superior

## Backend en Windows

Desde la raiz del proyecto:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
python backend\app.py
```

El backend queda disponible en `http://127.0.0.1:5000`. El health check es `GET /api/health`.

## Configuracion LLM

Completar `backend/.env` sin versionarlo:

```env
LLM_BASE_URL=https://proveedor-compatible.example/v1
LLM_API_KEY=
LLM_MODEL=
LLM_TIMEOUT_SECONDS=60
INTAKE_TIMEOUT_SECONDS=8
LLM_MAX_OUTPUT_TOKENS=4000
LLM_TEMPERATURE=
EXAMPLES_TOP_K=3
```

El proveedor debe ser compatible con OpenAI Chat Completions. La clave nunca se expone por API ni en Debug. Los outputs estructurados usan `PromptedOutput` y una sola revalidacion como maximo.

La búsqueda editorial local se ejecuta antes del presupuesto de ocho segundos del intake (`INTAKE_TIMEOUT_SECONDS`). Si una etapa posterior se demora, se conservan las referencias encontradas, se ofrece un formulario utilizable y se consulta el estado de la tarea; un resultado tardío sólo se incorpora si la conversación no avanzó. Sin referencias pertinentes, el formulario local no requiere llamadas al LLM. La clasificación y el intake no pueden iniciar búsquedas adicionales.

Como compatibilidad con instalaciones existentes, si `LLM_*` no esta definido tambien se aceptan `OLLAMA_BASE_URL` y `OLLAMA_MODEL`; la aplicacion utiliza automaticamente el endpoint OpenAI-compatible `/v1`.

## Frontend

En otra terminal:

```powershell
cd frontend
npm install
npm run dev
```

Vite redirige `/api` a Flask. Para compilar:

```powershell
cd frontend
npm run build
```

## Tests

Desde la raiz:

```powershell
pytest
```

La suite predeterminada usa mocks y `TestModel`: no realiza llamadas pagas. Las pruebas marcadas `live` quedan excluidas por defecto.

## Flujo

La biblioteca anterior incluye 11 Markdown administrativos, conservados como referencias heredadas. El catálogo relacional incorpora además 235 fichas editoriales de resoluciones comparadas, con fuente, calidad, alcance y revisiones. Véase el [catálogo anterior y sus fuentes](docs/modelos-administrativos.md).

1. Buscar ejemplos relacionales y heredados por función, materia, etapa y términos, con BM25 cacheado y fusión vectorial opcional.
2. Clasificar antecedentes y generar un formulario dinámico.
3. Validar respuestas y generar el borrador.
4. Revisar y comprobar el borrador actual antes de aprobar.
5. Aprobar, ejecutar skills descubiertas dinámicamente y exportar el DOCX aprobado.

El estado se guarda como JSON en `backend/data/giana_test.sqlite3`. Los ultimos 50 eventos registran tools, transiciones y consumo LLM sin prompts completos ni secretos. La base relacional indicada por `DATABASE_URL` guarda usuarios, conocimiento legal y el nuevo catálogo editorial; puede ser un archivo distinto de la base de conversaciones.

## Resoluciones de ejemplo y comprobación

El catálogo editorial se administra desde **Configurar → Resoluciones de ejemplo**. La carga inicial del archivo `sample-resolutions/Catalogo-Gianna-Lex.html` se ejecutó sobre la base activa: 235 fichas (13 preferentes, 187 utilizables con ajustes, 33 excluidas y 2 pendientes). La importación es idempotente y preserva el original y las revisiones locales. `sample-resolutions/Informe-Seleccion-Gianna-Lex.md` se usa como metodología y no se indexa.

Para futuras cargas, desde `backend/`:

```powershell
.\.venv\Scripts\python.exe -m flask --app app import-examples ..\sample-resolutions\Catalogo-Gianna-Lex.html --preview
.\.venv\Scripts\python.exe -m flask --app app import-examples ..\sample-resolutions\Catalogo-Gianna-Lex.html
```

El mismo servicio de recuperación alimenta la conversación y la prueba de búsqueda de Ajustes. Funciona localmente con SQLite y BM25 cacheado aun sin Qdrant. Si Qdrant está operativo, puede construirse su índice editorial opcional con `flask --app app index-examples`; las habilitaciones y revisiones se revalidan siempre en la base relacional.

Un borrador puede comprobarse antes de aprobarlo desde el panel de trabajo, o pegarse directamente en **Comprobar borrador**. El informe queda ligado al hash de esa revisión, enumera cobertura, referencias, hallazgos y alcance del contraste normativo. Una contradicción crítica impide aprobar hasta corregir el texto; una falta de norma comprobada se informa como información insuficiente, sin convertir similitud en legalidad. La exportación usa exactamente el texto aprobado.

Las rutas API, estados editoriales, esquema, resultados de evaluación y límites operativos están documentados en [docs/resoluciones-de-ejemplo.md](docs/resoluciones-de-ejemplo.md).

## Límites actuales

El conocimiento jurídico vectorial de `backend/legal_knowledge` requiere una base legal poblada y Qdrant; en la configuración local revisada la base legal activa no tenía resoluciones y Qdrant no respondía. La comparación editorial local funciona de forma independiente. No hay streaming, WebSockets ni un corpus normativo nacional completo integrado en el MVP. Las vistas administrativas de otros módulos conservan partes de prototipo.
