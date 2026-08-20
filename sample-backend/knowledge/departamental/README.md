# Normativa departamental de Lavalleja - Giana-Lex

Digesto computacional del derecho departamental de Lavalleja (UY-LA) para el
agente Giana-Lex. El objetivo no es una carpeta de PDFs, sino un corpus que
representa la **norma base → modificaciones → derogaciones → restablecimientos
→ interpretaciones → reglamentaciones → resoluciones que la aplican**.

## Estructura

```text
knowledge/departamental/
├── decretos/
├── ordenanzas/
├── resoluciones/
├── presupuestos/
├── instrumentos-territoriales/
├── estatutos/
├── reglamentos/
├── fuentes-indirectas/
├── manifests/
│   └── lavalleja_seed_manifest.json
├── registry.json
├── relationships.json
├── MISSING_SOURCES.md
├── NORMATIVE_RELATIONSHIPS.md
└── README.md
```

## Un directorio por norma

Cada norma con entidad suficiente se almacena en su propio directorio:

```text
decretos/decreto_3842_2023/
├── source.html        # HTML original (si procede)
├── source.pdf         # PDF original (si procede)
├── source.txt         # texto extraído
├── normalized.json    # representación normalizada (artículos + relaciones)
└── metadata.json      # metadatos persistentes
```

Una **fuente indirecta** (norma cuya existencia se confirma pero cuyo original
no se localizó) se guarda como stub:

```text
fuentes-indirectas/decreto_524_1977/
├── metadata.json
└── evidence.json
```

## Tipos de fuente (`source_quality`)

| Valor | Descripción |
|-------|-------------|
| `primary_full_text` | Página IDL/Junta con texto completo |
| `primary_partial` | Texto parcial |
| `official_republication` | Texto completo publicado (IMPO, MVOT, Diario Oficial) |
| `historical_scan` | PDF histórico oficial |
| `official_indirect_reference` | Norma citada en otra, sin texto completo |
| `unknown` | Calidad de fuente desconocida |

## Identidad normativa

IDs determinísticos:

```text
decreto:3842:2023
decreto:524:1977
ordenanza:cementerios:1944
resolucion:3836:2024
```

Cuando el año no está reconciliado se usa `unknown` (p. ej. `decreto:3473:unknown`).

## Registro

`registry.json` es el índice persistente. Cada entrada incluye: `id`, `norm_id`,
`jurisdiction=UY-LA`, `scope=departamental`, `department=Lavalleja`, `type`,
`number`, `year`, `title`, `status`, `text_available`, `source_quality`,
`active_for_rag`, `downloaded`, `normalized`, `indexed`, `checksum`,
`normative_family`, `modifies`, `modified_by`, `derogates`, `derogated_by`,
`evidence_sources`, `extraction_method`.

## Grafo de relaciones

`relationships.json` almacena relaciones entre normas:

```json
{ "from": "decreto:3842:2023", "relation": "MODIFIES", "to": "decreto:994:1982", "status": "verified", "evidence_source": "https://..." }
```

Relaciones soportadas: `MODIFIES`, `MODIFIED_BY`, `MODIFIES_ARTICLE`,
`DEROGATES`, `DEROGATED_BY`, `PARTIALLY_DEROGATES`, `RESTORES`, `REPLACES`,
`INTERPRETS`, `REGULATES`, `INCORPORATES`, `BASED_ON`, `APPLIES`,
`RELATED_TO`, `SUCCESSOR_OF`, `PREDECESSOR_OF`.

Cada relación conserva `evidence_source` y un estado (`verified` / `candidate`
/ `manual_review`).

## Familias normativas

`estatuto_funcionario`, `procedimiento_administrativo`,
`ordenamiento_territorial`, `patrimonio_departamental`,
`interes_departamental`, `interes_cultural_departamental`, `cementerios`,
`edificacion_arquitectura`, `arbolado_publico`, `veredas`,
`tributaria_departamental`, `bromatologia`, `limpieza_publica`,
`ruidos_molestos`, `transito_sucive`, `zona_azul`, `pirotecnia`,
`espacios_publicos`, `municipios`, `fideicomiso_departamental`,
`institucion_destacada`, `presupuestos_departamentales`.

## Importador

El servicio `DepartmentalNormImporter` (backend/depto/service.py) soporta:

```text
HTML (gub.uy, Junta, IDL)
PDF (IDL, IMPO, MVOT, Junta, Diario Oficial)
```

- Conserva original (HTML o PDF).
- Extrae texto (HTML sin navbar/footer; PDF con `pypdf`, OCR solo si el PDF
  es realmente imagen y no hay texto).
- Detecta artículos (`Artículo 1`, `Artículo 35 BIS`, etc.).
- Detecta relaciones candidatas por patrones (`modifícase`, `derógase`,
  `incorpórase`, `reglamenta`, etc.).
- Escribe de forma atómica (nunca destruye la versión buena).
- Checksum SHA-256; si no cambió, no reindexa.

## Fuentes indirectas

Una norma sin texto completo (`text_available=false`) NO produce embeddings
ficticios. Se registra como stub con `active_for_rag=false` y su existencia
se confirma mediante `evidence_sources`. Las relaciones del stub pueden usarse
para expandir el retrieval, pero nunca se cita un artículo inexistente.

## Seed

```bash
cd backend/
py -3.14 -m scripts.seed_lavalleja_departamental
py -3.14 -m scripts.seed_lavalleja_relations   # relaciones iniciales
```

El seed es idempotente: detecta existentes, descarga faltantes, continúa ante
errores y reporta un resumen final.

## Qdrant

Se reutiliza la colección existente `giana_lex_departamental`. Metadata de cada
chunk:

```text
scope = departamental
jurisdiction = UY-LA
department = Lavalleja
norm_id
normative_family
article
active
```

El retriever filtra `active=true`. Normas sin texto no se indexan.

## Actualización

Al actualizar una fuente:
1. descarga y calcula checksum;
2. si no cambió → no reindexa;
3. si cambió → reextrae y reindexa solo esa norma.

## Recuperación ante errores

- Descargas fallidas no destruyen la versión previa (escritura atómica).
- Normas cuyos originales no se localizan quedan documentadas en
  `MISSING_SOURCES.md`, listas para continuar la reconstrucción del digesto.
- `NORMATIVE_RELATIONSHIPS.md` se genera desde `relationships.json`.