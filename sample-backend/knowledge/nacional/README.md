# Normativa nacional - Giana-Lex

Este directorio es la fuente local de normativa nacional uruguaya para el agente Giana-Lex.

## Contenido

```text
knowledge/nacional/
├── constitucion/     Constitución de la República
├── decretos/         Decretos del Poder Ejecutivo
├── leyes/            Leyes, Decretos-Ley y Códigos
├── reglamentos/      Reglamentos independientes
├── impo_seed_manifest.json   Manifiesto de normas semilla (86 URLs IMPO)
├── registry.json     Registro persistente de normas importadas
└── README.md         Este documento
```

## IMPO Datos Abiertos

IMPO expone cada norma en formato JSON mediante el parámetro `?json=true`:

```text
https://www.impo.com.uy/bases/leyes/18381-2008?json=true
```

Documentación oficial: https://www.impo.com.uy/datos-abiertos/

El JSON contiene campos como `tipoNorma`, `nroNorma`, `anioNorma`, `nombreNorma`,
`fechaPromulgacion`, `fechaPublicacion`, `vistos`, `referenciasNorma`,
`indexacionNorma`, `articulos` (con `nroArticulo`, `textoArticulo`,
`notasArticulo`, `referenciasAlArticulo`, `urlArticulo`), entre otros.

La codificación del JSON de IMPO es ISO-8859-1 (no UTF-8).

## Estructura de archivos por norma

Cada norma importada se almacena en su propio directorio:

```text
knowledge/nacional/leyes/ley_18381_2008/
├── source.impo.json    JSON original recibido de IMPO (latin-1 decodificado a UTF-8)
├── normalized.json     Representación normalizada para Giana
├── normalized.txt       Texto plano para ingesta RAG
└── metadata.json       Metadatos locales persistentes
```

## Registro local

`registry.json` es un índice persistente de todas las normas importadas.
Cada entrada contiene: `id`, `tipo`, `numero`, `anio`, `title`,
`canonical_url`, `json_url`, `active`, `checksum`, `downloaded_at`,
`last_synced_at`, `index_status`, `article_count`, `chunk_count`, etc.

El registro puede reconstruirse desde el disco ejecutando:

```python
from impo.storage import rebuild_registry_from_disk
rebuild_registry_from_disk()
```

## Identidad y deduplicación

La identidad única de cada norma se construye deterministamente desde los
metadatos del JSON de IMPO:

```text
tipoNorma:nroNorma:anioNorma
```

Ejemplos:

```text
ley:18381:2008
decreto:500:1991
codigo-tributario:14306:1974
```

Si una norma ya existe, no se crea otro archivo. Se ofrece la opción
"Actualizar desde IMPO". El checksum SHA-256 del JSON original se compara
para detectar cambios reales.

## Activación y desactivación

Cada norma tiene un flag `active` en su metadata.

- **Activa**: indexada en Qdrant con `active=true` en el payload; recuperable
  por el agente mediante búsqueda semántica.
- **Inactiva**: el payload en Qdrant se actualiza a `active=false`; la norma
  deja de aparecer en los resultados de búsqueda inmediatamente. No se borra
  el archivo local ni se pierden metadatos.

El retriever (`LegalRetriever`) filtra `active=true` en todas las búsquedas
de normativa nacional.

## Actualización desde IMPO

La actualización individual:

1. Vuelve a consultar el JSON de IMPO.
2. Calcula el checksum.
3. Compara con el almacenado.
4. Si no cambió: informa "Sin cambios" (no reindexa).
5. Si cambió: actualiza archivos, conserva identidad, regenera
   representación normalizada y reindexa solo esa norma.

## Importación manual

Desde la interfaz de Configuración → Normativa nacional, pegue una URL de
IMPO (por ejemplo `https://www.impo.com.uy/bases/leyes/18381-2008`) y haga
clic en "Descargar normativa". El sistema:

1. Valida la URL (SSRF protection: solo `impo.com.uy`).
2. Normaliza a la URL canónica.
3. Descarga el JSON oficial con `?json=true`.
4. Valida la estructura del JSON.
5. Almacena el JSON original + versión normalizada + metadatos.
6. Registra en `registry.json`.
7. Indexa en Qdrant (si está activa).
8. La norma queda disponible para Giana.

## Seed inicial

El manifiesto `impo_seed_manifest.json` contiene 86 URLs de normas semilla.
Para importarlas todas:

```bash
cd backend/
py -3.14 -m scripts.seed_impo_nacional
```

El script es idempotente: si una norma ya existe, la salta. Si una URL
falla, continúa con las demás y reporta el resumen final.

## Relación con Qdrant

La colección `giana_lex_nacional` en Qdrant contiene los chunks de normativa
nacional. Cada chunk tiene en su payload:

```text
corpus = nacional
scope = nacional
norma_id = ley:18381:2008
active = true/false
article = 1
source_url = https://www.impo.com.uy/bases/leyes/18381-2008/1
```

Las búsquedas del agente filtran `active=true` para excluir normas
desactivadas.

## Recuperación ante errores

- Si `registry.json` se pierde o corrompe, ejecute
  `rebuild_registry_from_disk()` para reconstruirlo desde los
  `metadata.json` de cada directorio.
- Si una descarga falla a mitad de camino, la escritura atómica garantiza
  que la versión anterior queda intacta.
- Los archivos `.tmp` se mueven atómicamente al definitivo solo cuando la
  escritura completa exitosamente.