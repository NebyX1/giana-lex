# Giana-Lex

Asistente de inteligencia artificial para compliance y asesoria juridico-administrativa de un Gobierno Departamental.

El proyecto se construye de forma incremental. Actualmente existe una version integrada lista para pruebas tecnicas: autenticacion con email OTP, providers LLM, sesiones persistentes, tool calling, Agent Runtime, `ask_user`, skills externas, RAG Qdrant/FastEmbed, documentos, herramientas juridicas estructurales, ejemplos y moldes externos, web configurable, segunda opinion, DOCX y cliente Electron/React con Fluent UI 2.

## Arquitectura actual

```text
Electron
  -> React + Vite + TypeScript + Fluent UI 2
  -> Flask API
       -> Flask-Login + email OTP
       -> SQLAlchemy + Alembic
       -> MariaDB en produccion / SQLite en desarrollo
       -> Flask-Mail
       -> Redis para rate limiting, con memoria local como fallback
       -> LLM Providers (OpenAI OAuth, Featherless API key, Ollama sin key)
       -> Cifrado Fernet de credenciales
       -> Agent Runtime + Tool Registry + Permissions
       -> Skills Markdown + ask_user + Streaming SSE
       -> Qdrant + FastEmbed + knowledge/ reproducible
       -> Documentos, referencias, moldes, ejemplos y DOCX
```

La modernizacion vNext agrega un agregado persistente `LegalCase`, eventos, snapshots, outbox, SSE reanudable y ejecucion Redis mediante un worker separado. Para sesiones vinculadas, `GET /api/legal/cases/<id>/workspace` es la fuente canónica de estado, actividad, evidencia, draft, capacidades y tareas humanas; los mensajes del asistente no reconstruyen artefactos durables. Consulte `docs/architecture/GIANA_LEX_VNEXT.md`, `docs/adr/ADR-007-durable-workspace-ui-source.md` y el estado verificable en `docs/implementation/GIANA_LEX_VNEXT_PROGRESS.md`.

`sample-backend/` y `sample-rag/` son referencias de implementaciones anteriores. No forman parte del runtime principal y no deben modificarse.

## Frontend

Requiere Node.js compatible con Electron 40 y Vite 8.

```bash
npm install
npm run dev
```

`npm run dev` inicia el backend Flask desde `backend/.venv`, espera sus healthchecks, inicia Vite en `127.0.0.1:5173` y abre Electron. La interfaz usa exclusivamente Fluent UI React v9 mediante `FluentProvider`, `webLightTheme`, componentes Fluent y design tokens. Incluye login, OTP, providers, sesiones, chat SSE, actividad de tools, preguntas, fuentes, upload y exportacion DOCX.

El comando `npm run build` genera por ahora solamente el bundle web de Vite. El empaquetado instalable de Electron todavia no esta implementado.

## Backend

Requiere Python 3.11. Desde `backend/`:

```bash
python -m venv .venv
.venv/Scripts/activate
pip install -r requirements-dev.txt
copy .env.example .env
flask --app wsgi:app db upgrade
flask --app wsgi:app run --host 127.0.0.1 --port 5000
```

En Linux o macOS, la activacion del entorno virtual es `source .venv/bin/activate`.

Crear el primer usuario:

```bash
flask --app wsgi:app create-user --superuser
```

### Endpoints disponibles

| Metodo | Ruta | Funcion |
| --- | --- | --- |
| `GET` | `/health` | Liveness del proceso |
| `GET` | `/ready` | Readiness con comprobacion de base de datos |
| `GET` | `/api/auth/csrf` | Token CSRF para operaciones de sesion |
| `POST` | `/api/auth/login` | Valida password y envia email OTP |
| `POST` | `/api/auth/verify` | Completa el inicio de sesion con email OTP |
| `GET` | `/api/auth/me` | Devuelve el usuario autenticado |
| `POST` | `/api/auth/logout` | Cierra la sesion |
| `GET` | `/api/providers` | Lista conexiones LLM del usuario |
| `POST` | `/api/providers` | Crea una conexion LLM |
| `DELETE` | `/api/providers/<id>` | Elimina una conexion LLM |
| `POST` | `/api/providers/openai/authorize` | Inicia OAuth ChatGPT Plus/Pro |
| `GET` | `/api/providers/openai/callback` | Callback OAuth de OpenAI |
| `POST` | `/api/chat` | Streaming SSE de chat mediante connection_id |
| `POST` | `/api/sessions` | Crea una sesion persistente |
| `GET` | `/api/sessions` | Lista sesiones del usuario |
| `GET` | `/api/sessions/<id>` | Abre historial, tools y estado |
| `DELETE` | `/api/sessions/<id>` | Elimina una sesion propia |
| `POST` | `/api/agent/sessions/<id>/run` | Ejecuta el loop agentico mediante SSE |
| `POST` | `/api/agent/sessions/<id>/answer` | Responde ask_user y reanuda |
| `POST` | `/api/agent/sessions/<id>/second-opinion` | Revision compliance en contexto limpio |
| `GET` | `/api/agent/skills` | Lista skills descubiertas desde Markdown |
| `POST` | `/api/documents/sessions/<id>` | Carga PDF, DOCX, TXT o MD |
| `POST` | `/api/documents/sessions/<id>/generate-docx` | Renderiza JSON validado como BORRADOR DOCX |

Los `POST` requieren el token devuelto por `/api/auth/csrf` en el encabezado `X-CSRFToken`. El cliente debe conservar la cookie de sesion. Los streams se consumen con `fetch()` y conservan la proteccion CSRF.

### Providers LLM

Giana-Lex soporta dos vias de acceso a un LLM:

1. **ChatGPT Plus/Pro (OAuth PKCE)**: El usuario inicia sesion en chatgpt.com mediante un flujo OAuth con PKCE. Los tokens de acceso y refresco se almacenan cifrados con Fernet en la base de datos. El backend refresca los tokens automaticamente cuando expiran. Requiere configurar `OPENAI_CLIENT_ID`, `OPENAI_REDIRECT_URI` y opcionalmente `OPENAI_CLIENT_SECRET` en `.env`.

2. **API key (OpenAI-compatible)**: Para proveedores como Featherless, Ollama u otros endpoints compatibles con la API de OpenAI. El usuario ingresa su API key, que se almacena cifrada. Ollama puede funcionar sin API key (`auth_mode=none`).

Las credenciales nunca se envian al frontend, no aparecen en logs, y se cifran con Fernet usando claves independientes de `SECRET_KEY`.

### Variables de entorno

La lista vigente esta en `backend/.env.example`. En produccion son obligatorias:

```text
FLASK_CONFIG=production
SECRET_KEY=
DATABASE_URL=
CREDENTIAL_ENCRYPTION_KEYS=
CREDENTIAL_ACTIVE_KEY_ID=
```

Para habilitar ChatGPT Plus/Pro:

```text
OPENAI_CLIENT_ID=
OPENAI_REDIRECT_URI=http://localhost:1455/auth/callback
```

Generar una clave de cifrado Fernet:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

La URL esperada para MariaDB sigue el patron probado en `sample-backend`:

```text
mariadb+mariadbconnector://user:password@host:3306/giana_lex
```

El segundo factor implementado es un codigo de un solo uso enviado por correo, no TOTP de aplicacion autenticadora. Los codigos se almacenan con Argon2, caducan, tienen limite de intentos, se invalidan al emitir uno nuevo y nunca se escriben en logs.

## Agente, tools y skills

Las tools viven en archivos independientes bajo `backend/tools/` y son descubiertas automaticamente por `ToolRegistry`. Los schemas Pydantic se convierten a JSON Schema para el LLM. La politica `ALLOW/ASK/DENY` vive en `backend/config/permissions.yaml`.

Las skills viven en `backend/skills/<nombre>/SKILL.md` con YAML frontmatter. El prompt principal vive en `backend/agent/prompts/GIANA_LEX.md`. Agregar una tool o skill no exige modificar el runtime.

## RAG y conocimiento

`backend/knowledge/` es la fuente primaria y conserva separados corpus departamental/nacional y normativa/resoluciones. Qdrant usa:

```text
giana_lex_departamental
giana_lex_nacional
```

Reconstruir el indice desde `backend/`:

```bash
python -m ingestion.pipeline --rebuild
```

La indexacion usa FastEmbed, metadata trazable y chunking que reconoce estructura juridica cuando existe. No se incluye legislacion ficticia. La utilidad juridica debe evaluarse con corpus real validado.

## Documentos

Los uploads se confinan por usuario y sesion bajo `backend/instance/uploads/`. Las tools soportan lectura DOCX/PDF/TXT/MD, estructura de resoluciones, extraccion/verificacion conservadora de referencias, comparacion, ejemplos, moldes y revision procedimental. La salida DOCX parte de JSON validado y siempre se marca como BORRADOR.

## Tests

Desde `backend/`:

```bash
pytest
```

La suite actual cubre auth, providers, sesiones, provider adapters, tool calling, registry, permisos, Agent Runtime, ask_user con pausa/reanudacion, skills, RAG, chunking, documentos, tools juridicas, uploads, DOCX y segunda opinion mediante providers falsos.

## Docker y Coolify

El `backend/Dockerfile` usa una imagen multi-stage, un usuario sin privilegios, Gunicorn y un healthcheck. El entrypoint no migra por defecto: `RUN_MIGRATIONS_ON_START=false` evita carreras entre replicas. Produccion debe ejecutar una unica tarea de release antes de iniciar o actualizar web y worker.

```bash
docker build -t giana-lex-backend backend
docker run --rm --env-file backend/.env giana-lex-backend flask --app wsgi:app db upgrade
docker run --rm -p 5000:5000 --env-file backend/.env giana-lex-backend
docker run --rm --env-file backend/.env giana-lex-backend python -m workers.legal_workflow_worker
```

En Coolify deben configurarse MariaDB, Redis, Qdrant y SMTP como servicios externos y definirse las variables de `backend/.env.example`. Despliegue tres procesos desde la misma imagen: job unico `flask --app wsgi:app db upgrade`, web (comando por defecto) y worker `python -m workers.legal_workflow_worker`. Detalles y rollback: `docs/operations/DEPLOYMENT_MIGRATION.md`.

Coolify termina TLS en su proxy, por lo que `FORCE_HTTPS=false` es el valor normal. Si Flask debe redirigir HTTP por si mismo, active `FORCE_HTTPS=true` y configure `TRUSTED_PROXY_COUNT` de acuerdo con la cantidad real de proxies confiables.

### Stack local con Compose

`compose.yaml` levanta MariaDB, Redis, Qdrant, backend y worker con valores exclusivamente locales. La migracion es intencionalmente separada:

```bash
docker compose --profile tools run --rm migrate
docker compose up --build mariadb redis qdrant backend worker
```

Los valores del compose no son secretos de produccion. Antes de exponer el servicio cambie claves, contrasenas, CORS y configuracion SMTP/proxy.

## Integracion continua

`.github/workflows/ci.yml` ejecuta pytest con configuracion de testing y fakes, un smoke de migraciones SQLite, lint y build frontend. Ejecuta tests frontend y Playwright solo cuando el repositorio tenga sus respectivos scripts/configuracion; actualmente no existen y CI informa el skip sin fingir cobertura.

## Estado para pruebas

La plataforma esta lista para pruebas tecnicas y de interfaz. Para pruebas juridicas reales faltan insumos externos que el sistema no debe inventar:

- corpus departamental y nacional validado dentro de `backend/knowledge/`;
- ejemplos institucionales reales dentro de `backend/ejemplos/`;
- validacion institucional de los moldes marcados como pendientes;
- credenciales de un provider LLM y, si se usa, proveedor de busqueda web;
- casos juridicos validados en `backend/evals/`.

Hasta incorporar y evaluar esos insumos no debe considerarse validada la calidad juridica del producto.
