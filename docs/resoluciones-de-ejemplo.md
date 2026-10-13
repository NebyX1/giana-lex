# Resoluciones de ejemplo: operación y alcance

Fecha: 23 de septiembre de 2026. Este módulo pertenece al Flask activo de `backend/` y a la interfaz de `frontend/`.

## Fuente, esquema y carga inicial

La base relacional definida por `DATABASE_URL` es la fuente de verdad. En esta instalación apunta a `backend/instance/giana_lex.db`. El módulo agregó las tablas `example_documents`, `example_source_versions`, `example_revisions`, `example_import_batches` y `example_audit_events`. La migración Alembic es `backend/migrations/versions/0003_editorial_examples.py`; para la base local preexistente, que no llevaba `alembic_version`, `LegalKnowledgeDatabase.ensure_schema()` creó las tablas faltantes sin recrear las demás. No se cambió `DATABASE_URL` a una base de pruebas.

`example_documents` contiene la identidad estable, el ID externo, departamento, órgano, número original y normalizado, fecha, título, URL, clasificación, calidad editorial, habilitación, alcance, versión y revisión activa. `example_source_versions` conserva cada versión importada completa e inmutable, con hash calculado del registro, hash del texto realmente importado y el `sha256_texto_recuperado` declarado por la fuente, que puede corresponder a una etapa anterior a la copia recibida. `example_revisions` conserva las ediciones derivadas, autor, motivo, texto y fragmentos habilitados. Los lotes y operaciones quedan auditados.

La carga inicial se ejecutó sobre `sample-resolutions/Catalogo-Gianna-Lex.html` mediante parser HTML de `lxml` sin red ni JavaScript y `json.loads` del único `script#dataset[type="application/json"]`. Se importaron **235 fichas: 13 preferentes, 187 utilizables con ajustes, 33 excluidas y 2 pendientes**. La reimportación idéntica produjo 235 omitidas y ninguna duplicada. La identidad se basa en procedencia e ID externo, y se concilia con departamento, número normalizado y fecha. Compartir una URL de PDF no fusiona actos. Las rutas internas de investigación se guardan como metadatos, no se abren.

El archivo `Informe-Seleccion-Gianna-Lex.md` fue leído para conocer los criterios y errores de control; no es una resolución ni se importa. ZIP no es un formato admitido. El importador admite HTML de catálogo, JSON array y JSONL; rechaza archivo vacío, más de 20 MB, codificación no UTF-8, estructura errónea, registros sin ID/título/calidad/texto y duplicados internos antes de escribir. Un lote se aplica en una transacción. La vista previa realiza las mismas validaciones y revierte la transacción.

```powershell
cd backend
.\.venv\Scripts\python.exe -m flask --app app import-examples ..\sample-resolutions\Catalogo-Gianna-Lex.html --preview
.\.venv\Scripts\python.exe -m flask --app app import-examples ..\sample-resolutions\Catalogo-Gianna-Lex.html
```

## Política editorial

| Calidad de origen | Búsqueda positiva inicial | Alcance |
|---|---|---|
| Preferente | Sí, 13 fichas | Comparación y referencia editorial; las advertencias y normas sin cotejar se conservan |
| Utilizable con ajustes | Sí, 187 fichas | Estructura y elementos reutilizables; el texto completo queda visible pero no se envía como modelo literal |
| No usar como modelo | No, 33 fichas | Consulta humana y pruebas de errores |
| Pendiente de lectura | No, 2 fichas | Completar lectura; no soporta conclusiones sobre el cuerpo |

Una revisión editorial local no cambia la evaluación histórica de la fuente. Guardar borrador crea una revisión sin publicarla. “Guardar y aplicar a Gianna” publica una revisión y actualiza el buscador local inmediatamente. Si una importación posterior trae cambios para una ficha publicada localmente, se registra un conflicto, se conserva la revisión aplicada y se archiva la nueva versión de fuente para conciliación. Publicar texto completo de una ficha condicionada exige justificar la promoción y resolver todas las observaciones de origen; publicar fragmentos exige pasajes literales expresamente habilitados. Suspender o archivar excluye el documento de la búsqueda positiva. Restaurar genera otra revisión y preserva el historial.

Los 11 Markdown de `backend/examples/` siguen disponibles como referencias heredadas de estructura, sin darles una aprobación editorial inventada. No se confunden con normas vigentes.

## Recuperación y contexto

`ExampleCatalog.search()` es el único servicio usado por la conversación y la herramienta “Probar búsqueda” de Ajustes. Mantiene en memoria un índice BM25 ponderado por título, tipo, familia, funciones, hechos necesarios, elementos reutilizables y texto habilitado. La caché se invalida al editar/importar y se verifica contra el máximo `updated_at` de la base en cada consulta, para detectar publicaciones de otro proceso. No relee los 235 originales por consulta.

La clasificación heurística versionada reconoce acciones como rectificar, investigar, restituir, delegar, ampliar, adjudicar, exonerar, revocar, aceptar, sancionar, autorizar, prorrogar y reglamentar. Distingue inicio, cierre, modificación y decisión. Expande unas relaciones de contexto de modo conservador: “devolver un local al vencer el préstamo” puede orientar a restitución de comodato; “aumentar prestaciones” no se equipara a prórroga de plazo. Una función negada se penaliza. Los resultados indican clase de correspondencia, motivos, diferencias territoriales, alcance y defectos.

La ruta local funciona sin Qdrant. Si se construye la colección opcional `giana_editorial_examples_v1`, FastEmbed usa el modelo y la dimensión de `LEGAL_EMBEDDING_MODEL`/`LEGAL_EMBEDDING_DIMENSION`, y los rankings local/vectorial se fusionan por Reciprocal Rank Fusion con constante 60. El índice vectorial es derivado: sólo se admiten IDs y revisiones que sigan activos en SQLite. Si el índice no responde, `capabilities.vector_error` explica la degradación y los resultados locales permanecen. Para reconstruirlo cuando Qdrant esté disponible:

```powershell
cd backend
.\.venv\Scripts\python.exe -m flask --app app index-examples
```

El flujo recupera hasta 20 candidatos y presenta hasta 5 referencias al intake. Para la redacción envía únicamente texto editorial autorizado o elementos de estructura, junto con defectos y diferencias; no envía HTML del catálogo ni el original íntegro de las fichas condicionadas. El contexto editorial se divide por encabezados, numerales y párrafos: selecciona hasta dos unidades jurídicas completas por referencia y un máximo conservador de 360 palabras por referencia. Una unidad que no cabe se omite sin cortarla a mitad de una condición. Esto deja espacio en la ventana del modelo para hechos, borrador y respuesta. Cada resultado seleccionado se revalida en la base antes del contexto y antes de aprobar. El timeout de intake no borra referencias locales ya recuperadas. Si una comparación posterior termina tarde, sólo actualiza fuentes cuando la conversación sigue en la revisión inicial; el frontend consulta `intake_pending` por polling autenticado. Si el agente niega la existencia de antecedentes pese a una coincidencia sustentada por el recuperador, la respuesta se corrige con las referencias efectivamente encontradas.

## Comprobación previa a la aprobación

Hay dos entradas: el formulario que genera un borrador y “Comprobar borrador” para pegar uno existente. Ambas usan `verify_draft`. Los controles deterministas revisan padrones, expedientes, importes numéricos con `Decimal`, fechas ISO, secuencia de numerales, rangos de articulado, años discordantes de citas, efecto y motivación básica. Se probaron contra cuerpos reales: LVR-004 (4876/4786), CAN-023 (UR 2584,80/2584,40), MVT-018 (clausura/paralización), MVT-021 (D.4090.7.17 frente a .16), MAL-013 (4118/2016 frente a 4118/2026) y MVP-033 (motivación de prórroga).

Cuando el LLM está configurado, una llamada estructurada adicional analiza objeto, competencia, antecedentes, motivación, procedimiento, audiencia, presupuesto, efecto, plazos, notificación y congruencia. El servidor acepta sólo pasajes que estén literalmente en el borrador; no acepta IDs de ejemplo ni citas normativas inventadas por el modelo. Si esta etapa falla, el informe queda como `context_status=unavailable` y no se puede aprobar como si el análisis hubiese terminado.

El informe Pydantic queda asociado al hash SHA-256 y número de revisión del borrador, las referencias utilizadas y sus revisiones. Cada hallazgo lleva categoría, severidad, ubicación, pasaje de evidencia, explicación, acción y necesidad de documento. Los resultados visibles son “Sin observaciones materiales en los controles ejecutados”, “Con observaciones” e “Información insuficiente”. Una contradicción crítica requiere corregir el texto; una nota libre no la resuelve. La aprobación rechaza un hash diferente, una referencia suspendida o modificada, un análisis contextual fallido o una contradicción crítica activa. El DOCX se genera sólo si el texto actual coincide con el hash aprobado.

El contraste normativo tiene campos separados para existencia, contenido, versión temporal y aplicabilidad territorial. En esta instalación ninguno se certifica automáticamente: la base legal activa no tiene resoluciones y no hay un corpus normativo nacional/territorial completo conectado al comprobador. Las citas importadas son registros históricos de una ficha, no una verificación nueva. No se trasladan reglas de Montevideo, Canelones o Maldonado a Lavalleja.

## API

Todas las rutas requieren sesión; mutaciones requieren CSRF. La lectura del catálogo está permitida a usuarios autenticados. Altas, cambios e importaciones requieren `corpus_curator` o `technical_admin` (o superusuario mediante los roles reales). Un conflicto de versión devuelve HTTP 409.

| Ruta | Método | Resultado |
|---|---|---|
| `/api/settings/examples` | GET | `items`, `total`, `page`, `page_size`; filtros `q`, `department`, `family`, `type`, `function`, `date_from`, `date_to`, `decision`, `scope`, `order` |
| `/api/settings/examples/<id>` | GET | Original, revisión activa, metadatos, historial y versiones de fuente |
| `/api/settings/examples` | POST | Modelo interno en borrador (`title`, `text`, `family`, `function`, `origin`) |
| `/api/settings/examples/<id>` | PATCH | Nueva revisión con `expected_version`; `publish=true` la aplica, `suspend`/`archive` cambian disponibilidad |
| `/api/settings/examples/<id>/restore/<revision_id>` | POST | Crea una revisión restaurada con `expected_version` y `reason` |
| `/api/settings/examples/import` | POST multipart | Archivo `file` y `preview=true/false`; cuentas y conflictos por registro |
| `/api/settings/examples/search-preview?q=...` | GET | Misma recuperación que usa Gianna, con alcance, motivos y versión |
| `/api/conversations/check-draft` | POST | Crea conversación y comprueba `draft`, `context`, `facts` |
| `/api/conversations/<id>/check` | POST | Comprueba la revisión actual o un nuevo `draft`; devuelve `verification` |
| `/api/conversations/<id>/approve` | POST | Valida informe, hash, revisiones y hallazgos críticos |

Ejemplo de creación de borrador propio:

```json
{"title":"Modelo interno de delegación","text":"VISTO: ...\nRESUELVE: ...","family":"Organización y gobierno","function":"delegar","origin":"equipo jurídico"}
```

Ejemplo de actualización con control de concurrencia:

```json
{"expected_version":3,"text":"VISTO: ...\nRESUELVE: ...","scope":"structure","reason":"Ajuste editorial","publish":true}
```

## Validación medida y límites

- Pruebas automáticas del proyecto y del catálogo importan el HTML real, repiten la carga, comprueban búsqueda/edición/suspensión/conflictos y verifican discrepancias de cuerpos reales.
- En el conjunto de 20 consultas usado para ajustar el recuperador se alcanzó Recall@5 de 20/20. Es una medición interna, no una estimación independiente de calidad general.
- Un segundo conjunto de 20 consultas formulado antes de los últimos ajustes dio 15/20. Falló en ampliación de contrato, restitución de local cedido, beneficio tributario, bases de concurso e interinato; se añadieron distinciones léxicas y funcionales después, por lo que ese segundo conjunto ya no es una prueba ciega.
- Un tercer conjunto de 20 consultas nuevas, fijado tras los ajustes y sin modificar el buscador después de ejecutarlo, dio **19/20 (Recall@5 de 95%)**. El fallo restante fue MVC-015 al pedir cesión de crédito de un contratista a un banco; el recuperador priorizó referencias ajenas a la cesión. Se conserva como caso pendiente, sin ocultarlo ni codificar una excepción por ID.
- En un AMD Ryzen 5 7430U de 12 hilos, 100 búsquedas calientes sobre 20 consultas tuvieron mediana de 116,5 ms y p95 de 123,8 ms. La primera consulta en un proceso nuevo tomó 929,2 ms por carga del índice y comprobación del vector opcional; el objetivo de p95 <500 ms se cumple para el índice caliente, no para la primera búsqueda fría.
- Tres consultas reales a Ollama `glm-5.2:cloud` usando las referencias recuperadas devolvieron MVP-003, LAV-004 y MVC-023 en 9,55 s, 5,79 s y 6,96 s. Con un límite de 160 tokens las tres respuestas tuvieron contenido vacío; con 1.000 tokens y `think=false` devolvieron texto. La configuración del MVP permite 4.000 tokens.
- Una comprobación contextual real con PydanticAI/Ollama tardó 21,99 s y devolvió hallazgos estructurados sobre un borrador de apertura de investigación. Eso verifica el proveedor y el contrato, pero no demuestra exhaustividad jurídica.
- La navegación E2E local comprobó Ajustes → Resoluciones de ejemplo → lista de 235 → detalle; alta de modelo propio, edición y publicación; búsqueda de la revisión publicada y presencia como primera referencia en una consulta de Gianna; comprobación directa de un borrador con contradicción de efecto y aprobación deshabilitada. Esta prueba detectó y permitió corregir un import faltante de Fluent UI que dejaba en blanco el panel de borrador. El servidor E2E usó base SQLite temporal y agente simulado; la prueba real de Ollama se midió por separado.

Limitaciones actuales: no se comparan de forma fiable todos los importes escritos en letras; los controles de importes distintos pueden pedir revisión aun cuando correspondan a operaciones diferentes; la ausencia de textos normativos comprobados deja `normative_status` incompleto; Qdrant no estaba disponible en el entorno revisado y su índice editorial opcional no pudo construirse; el análisis contextual sigue siendo una llamada HTTP sin streaming. No se interpreta una similitud como probabilidad de legalidad.
