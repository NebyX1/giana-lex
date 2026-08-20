from rag.tool_search import LegalSearchTool


tool = LegalSearchTool(
    name="search_resolutions",
    description="Busca resoluciones departamentales como antecedentes, preservando su fuente.",
    corpus="departamental",
    fixed_category="resoluciones",
)
