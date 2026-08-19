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
LLM_MAX_OUTPUT_TOKENS=4000
LLM_TEMPERATURE=
EXAMPLES_TOP_K=3
```

El proveedor debe ser compatible con OpenAI Chat Completions. La clave nunca se expone por API ni en Debug. Los outputs estructurados usan `PromptedOutput` y una sola revalidacion como maximo.

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

1. Buscar ejemplos Markdown localmente con BM25.
2. Clasificar antecedentes y generar un formulario dinamico.
3. Validar respuestas y generar el borrador.
4. Revisar hasta aprobar.
5. Ejecutar skills descubiertas dinamicamente.
6. Exportar el borrador aprobado a DOCX.

El estado se guarda como JSON en `backend/data/giana_test.sqlite3`. Los ultimos 50 eventos registran tools, transiciones y consumo LLM sin prompts completos ni secretos.

## Fuera del MVP

No incluye autenticacion, RAG vectorial, embeddings, normativa externa, MCP, Redis, Docker, streaming, WebSockets ni orquestacion multiagente.
