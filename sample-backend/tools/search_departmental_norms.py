from rag.tool_search import LegalSearchTool


tool = LegalSearchTool(
    name="search_departmental_norms",
    description="Busca normativa departamental y devuelve fragmentos con fuente y trazabilidad.",
    corpus="departamental",
)
