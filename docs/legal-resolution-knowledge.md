# Conocimiento jurídico de resoluciones IDL

## Arquitectura

La biblioteca se integra al backend Flask existente bajo `backend/legal_knowledge`.

```text
React / Fluent UI
        |
Flask /api/settings/legal
        |
SQLAlchemy repository
        |
MariaDB (producción) o SQLite (desarrollo local)
        |
sync_outbox
        |
FastEmbed + Qdrant
        |
Pydantic AI tools / Orchestrator
```

La base relacional es la fuente de verdad. Qdrant es un índice derivado y puede reconstruirse. Los originales HTML o archivos cargados se preservan una sola vez bajo `backend/data/legal/idl/resolutions/<uuid>`; las relaciones con tipologías viven exclusivamente en la base.

El proyecto local no contenía credenciales para la MariaDB nativa. Por eso la configuración predeterminada conserva el SQLite existente. Producción debe configurar un usuario y una base dedicados mediante:

```env
DATABASE_URL=mysql+pymysql://giana_legal:password@127.0.0.1:3306/giana_lex?charset=utf8mb4
```

No use las credenciales del Compose de muestra ni las colecciones Qdrant preexistentes.

## Tablas

- `taxonomy_nodes`: árbol genérico, estado, señales, facts, notas y versiones.
- `resolutions`: identidad oficial, deduplicación, estado y versión vigente.
- `resolution_revisions`: texto histórico y estructura jurídica inmutable.
- `resolution_taxonomy_assignments`: rol contextual canónico, secundario, relacionado o negativo.
- `resolution_originals`: hashes y ubicación de originales auditables.
- `resolution_catalog`: catálogo incremental liviano del índice oficial.
- `sync_outbox`: sincronización transaccional con Qdrant.
- `legal_audit_events`: actor, acción y estados anterior/nuevo.

La migración Alembic `0001_legal_resolution_knowledge` es aditiva y no modifica `conversations`.

## Qdrant y embeddings

Colecciones verificadas:

```env
QDRANT_RESOLUTION_TAXONOMY_COLLECTION=giana_resolution_taxonomy_v2
QDRANT_RESOLUTION_EXAMPLES_COLLECTION=giana_resolution_examples_v2
LEGAL_EMBEDDING_MODEL=jinaai/jina-embeddings-v2-base-es
LEGAL_EMBEDDING_DIMENSION=768
```

Se crearon colecciones versionadas porque el modelo de las colecciones compartidas existentes era desconocido. Las colecciones `_v1` creadas durante la evaluación no se borraron, pero no son la configuración activa: FastEmbed 0.7.3 cambió el pooling del modelo MiniLM y la evaluación exacta falló.

Los IDs de points son UUIDv5 determinísticos. Reindexar no duplica puntos. Cambiar solo estado o relaciones actualiza payload; cambiar el texto normalizado crea una revisión, vuelve a chunkear por secciones y sustituye los chunks anteriores.

Solamente tipologías y resoluciones `active` son recuperables.

## Importador

`LavallejaResolutionImporter` separa descarga, parsing, normalización y persistencia. Solo permite HTTPS en `gub.uy` bajo `/intendencia-lavalleja/institucional/normativa`, valida DNS público, controla redirects, limita la respuesta a 5 MB, aplica timeout, retry, backoff, rate limiting y un User-Agent identificable.

El resolver intenta primero el slug derivado, valida el heading y el número normalizado y luego consulta `resolution_catalog`. Nunca persiste una ficha con número diferente.

El parser conserva HTML, texto crudo, normalización y secciones VISTO, RESULTANDO, CONSIDERANDO, ATENTO y RESUELVE cuando existen. Una corrección manual crea una nueva revisión.

## Retrieval del agente

El orquestador ejecuta obligatoriamente:

1. `search_resolution_types` sobre la colección de taxonomía.
2. Clasificación estructurada únicamente entre los IDs candidatos.
3. Recuperación de la ficha tipológica y facts.
4. `search_resolution_examples` filtrado por `taxonomy_node_id`.
5. Antecedente canónico explícito y secundarios semánticos.

Las tools Pydantic AI reciben `LegalKnowledgeService` mediante `LegalKnowledgeDeps`; no hay Enums ni catálogo hardcodeado en prompts.

## API administrativa

Prefijo: `/api/settings/legal`.

- `GET/POST /taxonomy`
- `GET/PATCH /taxonomy/<id>`
- `POST /taxonomy/<id>/duplicate`
- `POST /taxonomy/<id>/reindex`
- `GET/POST /resolutions`
- `GET/PATCH /resolutions/<id>`
- `POST /resolutions/import-url`
- `POST /resolutions/import-file`
- `POST /resolutions/<id>/reindex`
- `GET /overview`
- `GET /index/status`
- `POST /index/retry-failed`
- `POST /index/check`

La lectura es utilizable por el agente. Las mutaciones exigen `LEGAL_ADMIN_KEY`; mientras no se configure y el proyecto siga sin auth backend, solo se admiten desde loopback si `LEGAL_ALLOW_LOCAL_ADMIN=true`. Antes de exposición multiusuario debe reemplazarse este modo transitorio por la sesión/RBAC institucional.

## Frontend

Ruta lógica actual, sin router adicional:

```text
Configuración > Conocimiento jurídico
```

Incluye Resumen, Tipologías, Resoluciones, Importar y Estado del índice. Las búsquedas de resoluciones son paginadas en servidor. El flujo URL exige preview y confirmación administrativa. También admite creación manual y archivos PDF, DOCX, TXT o MD de hasta 10 MB.

## Comandos

Desde `backend`, con `PYTHONPATH` apuntando al directorio actual:

```powershell
python -m flask --app app:app legal seed --dry-run
python -m flask --app app:app legal seed --taxonomy-only
python -m flask --app app:app legal seed --only "2.826/026"
python -m flask --app app:app legal import-url URL --dry-run
python -m flask --app app:app legal crawl-catalog --limit 10
python -m flask --app app:app legal index-pending --limit 100
python -m flask --app app:app legal retry --limit 100
python -m flask --app app:app legal check-index
python -m flask --app app:app legal rebuild-index --dry-run
python -m flask --app app:app legal rebuild-index
python -m flask --app app:app legal status
python -m flask --app app:app legal manifest
```

## Outbox y recuperación

Toda mutación indexable crea un evento en la misma transacción. Si Qdrant falla, el cambio relacional permanece y el evento pasa a `failed`. `legal retry` lo reprocesa. El consistency checker informa versiones diferentes, puntos huérfanos, chunks duplicados, relaciones inválidas, documentos archivados recuperables y subtipos sin canónico; nunca repara destructivamente de forma automática.

## Troubleshooting

- `failed` en outbox: revisar `last_error`, Qdrant y el modelo local; ejecutar `legal retry`.
- Ranking degradado: ejecutar las consultas de evaluación antes de cambiar modelo; use una colección nueva y después cambie configuración.
- MariaDB inaccesible: verificar usuario dedicado, permisos y `DATABASE_URL`; no adivinar credenciales root.
- UI recibe 403: configure autenticación/RBAC o use loopback durante desarrollo.
- Importación en revisión: comprobar el documento oficial y asignar manualmente; no promover automáticamente a canónico.
