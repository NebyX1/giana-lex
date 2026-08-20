# Corpus juridico local

Esta carpeta es la fuente primaria y reproducible de la ingesta RAG. Coloque
documentos `.txt`, `.md` o `.pdf` en la categoria correspondiente. Un archivo
opcional `<documento>.<ext>.json` puede definir `title`, `number`, `year`,
`document_type` y `source_url`; los demas metadatos se calculan durante la
ingesta.

No cambie documentos directamente en Qdrant: ejecute
`python -m ingestion.pipeline` desde `backend/`. Use `--rebuild` para recrear
ambas colecciones.
