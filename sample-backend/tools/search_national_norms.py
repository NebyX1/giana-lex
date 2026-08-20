from rag.tool_search import LegalSearchTool


tool = LegalSearchTool(
    name="search_national_norms",
    description="Busca normativa nacional y devuelve fragmentos con fuente y trazabilidad.",
    corpus="nacional",
)
