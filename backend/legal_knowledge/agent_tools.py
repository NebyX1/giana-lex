from __future__ import annotations

from dataclasses import dataclass

from pydantic_ai import RunContext, Tool


@dataclass
class LegalKnowledgeDeps:
    service: object


def search_resolution_types(ctx: RunContext[LegalKnowledgeDeps], query: str, limit: int = 5):
    """Busca tipologías dinámicas activas apropiadas para una solicitud administrativa."""
    return [item.model_dump() for item in ctx.deps.service.search_resolution_types(query, limit)]


def get_resolution_type(ctx: RunContext[LegalKnowledgeDeps], taxonomy_node_id: str):
    """Obtiene la ficha completa y vigente de una tipología por su identificador."""
    return ctx.deps.service.get_taxonomy(taxonomy_node_id)


def search_resolution_examples(
    ctx: RunContext[LegalKnowledgeDeps], taxonomy_node_id: str, query: str | None = None, limit: int = 5
):
    """Recupera antecedentes oficiales filtrados por tipología, priorizando el rol canónico."""
    return [item.model_dump() for item in ctx.deps.service.search_resolution_examples(taxonomy_node_id, query, limit)]


def get_resolution(ctx: RunContext[LegalKnowledgeDeps], resolution_id: str):
    """Obtiene una resolución oficial, su revisión vigente y sus relaciones tipológicas."""
    return ctx.deps.service.get_resolution(resolution_id)


def get_required_facts(ctx: RunContext[LegalKnowledgeDeps], taxonomy_node_id: str):
    """Obtiene los hechos obligatorios configurados administrativamente para una tipología."""
    return ctx.deps.service.get_required_facts(taxonomy_node_id)


def legal_knowledge_tools():
    return [
        Tool(search_resolution_types, takes_ctx=True),
        Tool(get_resolution_type, takes_ctx=True),
        Tool(search_resolution_examples, takes_ctx=True),
        Tool(get_resolution, takes_ctx=True),
        Tool(get_required_facts, takes_ctx=True),
    ]
