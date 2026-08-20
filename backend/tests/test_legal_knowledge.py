from dataclasses import replace
from pathlib import Path

from config import settings
from orchestrator import Orchestrator
from schemas import DynamicForm, FormField, IntakeOutput, LLMRun, ResolutionClassification
from storage import Storage
from legal_knowledge.database import LegalKnowledgeDatabase
from legal_knowledge.models import SyncOutbox
from legal_knowledge.schemas import ManualResolutionInput, ResolutionAssignmentInput, ResolutionPatch, TaxonomyNodeInput, TaxonomyNodePatch
from legal_knowledge.service import LegalKnowledgeService


class FakeIndex:
    def __init__(self):
        self.down = False
        self.taxonomy = {}
        self.resolutions = {}

    def health(self):
        return {"connected": not self.down, "taxonomy_exists": bool(self.taxonomy), "resolutions_exists": bool(self.resolutions)}

    def search_taxonomy(self, query, limit):
        return []

    def search_resolutions(self, taxonomy_node_id, query, limit):
        return []

    def upsert_taxonomy(self, document, payload):
        if self.down:
            raise ConnectionError("Qdrant no disponible")
        self.taxonomy[payload["taxonomy_node_id"]] = payload

    def delete_taxonomy(self, node_id):
        self.taxonomy.pop(node_id, None)

    def upsert_resolution(self, resolution, revision, assignments):
        if self.down:
            raise ConnectionError("Qdrant no disponible")
        self.resolutions[resolution["id"]] = {"revision": revision["id"], "assignments": assignments}
        return 1

    def update_resolution_payload(self, resolution_id, payload):
        if self.down:
            raise ConnectionError("Qdrant no disponible")
        self.resolutions.setdefault(resolution_id, {}).update(payload)

    def delete_resolution(self, resolution_id):
        self.resolutions.pop(resolution_id, None)

    def resolution_point_count(self, resolution_id):
        return 1 if resolution_id in self.resolutions else 0


def make_service(tmp_path):
    test_settings = replace(
        settings,
        legal_database_url=f"sqlite:///{(tmp_path / 'legal.sqlite3').as_posix()}",
        legal_storage_dir=tmp_path / "documents",
        legal_report_dir=tmp_path / "reports",
    )
    index = FakeIndex()
    service = LegalKnowledgeService(
        test_settings,
        database=LegalKnowledgeDatabase(test_settings.legal_database_url),
        index=index,
    )
    return service, index


def create_tree(service):
    family = service.create_taxonomy(TaxonomyNodeInput(level="family", code="TEST", slug="test", name="TEST", status="active"), sync=False)
    type_node = service.create_taxonomy(TaxonomyNodeInput(parent_id=family["id"], level="type", code="TEST.experimental", slug="experimental", name="Resoluciones experimentales", status="active"), sync=False)
    subtype = service.create_taxonomy(TaxonomyNodeInput(
        parent_id=type_node["id"], level="subtype", code="TEST.experimental.authorization", slug="authorization",
        name="Autorización experimental", description="Autoriza una actuación experimental", positive_signals=["autorizar", "experimental"],
        required_facts=["objeto", "beneficiario"], status="active",
    ), sync=False)
    return family, type_node, subtype


def test_taxonomy_resolution_revision_and_assignment_versioning(tmp_path):
    service, _index = make_service(tmp_path)
    _family, _type_node, subtype = create_tree(service)
    changed = service.update_taxonomy(subtype["id"], TaxonomyNodePatch(description="Descripción corregida", expected_version=1), sync=False)
    assert changed["version"] == 2
    deprecated = service.update_taxonomy(subtype["id"], TaxonomyNodePatch(status="deprecated", expected_version=2), sync=False)
    assert deprecated["status"] == "deprecated"
    active = service.update_taxonomy(subtype["id"], TaxonomyNodePatch(status="active", expected_version=3), sync=False)

    resolution = service.create_manual_resolution(ManualResolutionInput(
        resolution_number="1/026", title="Autorización experimental", status="active",
        normalized_text="VISTO: la solicitud\nCONSIDERANDO: su mérito\nATENTO: a las facultades\nRESUELVE:\n1º.- Autorízase.",
        assignments=[ResolutionAssignmentInput(taxonomy_node_id=active["id"], role="canonical")],
    ), sync=False)
    assert resolution["assignments"][0]["role"] == "canonical"
    updated = service.update_resolution(resolution["id"], ResolutionPatch(
        normalized_text=resolution["revisions"][0]["normalized_text"] + "\n2º.- Comuníquese.",
        change_reason="Agregar comunicación",
        assignments=[ResolutionAssignmentInput(taxonomy_node_id=active["id"], role="secondary")],
        expected_version=1,
    ), sync=False)
    assert len(updated["revisions"]) == 2
    assert updated["assignments"][0]["role"] == "secondary"


def test_outbox_survives_qdrant_failure_and_retries(tmp_path):
    service, index = make_service(tmp_path)
    _family, _type_node, subtype = create_tree(service)
    index.down = True
    result = service.process_outbox(limit=100)
    assert result["failed"] > 0
    assert service.get_taxonomy(subtype["id"])["name"] == "Autorización experimental"
    with service.database.session() as session:
        assert session.query(SyncOutbox).filter_by(status="failed").count() > 0
    index.down = False
    retried = service.process_outbox(limit=100, only_failed=True)
    assert retried["completed"] > 0
    assert service.get_taxonomy(subtype["id"])["index_status"] == "synced"


def test_dynamic_typology_is_retrieved_then_excluded_when_deactivated(tmp_path):
    service, _index = make_service(tmp_path)
    _family, _type_node, subtype = create_tree(service)
    matches = service.search_resolution_types("Necesito autorizar una actuación experimental")
    assert matches[0].taxonomy_node_id == subtype["id"]
    resolution = service.create_manual_resolution(ManualResolutionInput(
        resolution_number="99/026", title="Autorización experimental", status="active",
        normalized_text="VISTO: prueba\nATENTO: prueba\nRESUELVE:\n1º.- Autorízase.",
        assignments=[ResolutionAssignmentInput(taxonomy_node_id=subtype["id"], role="canonical")],
    ), sync=False)
    references = service.search_resolution_examples(subtype["id"], "actuación experimental")
    assert references[0].resolution_id == resolution["id"]
    service.update_taxonomy(subtype["id"], TaxonomyNodePatch(status="deprecated", expected_version=1), sync=False)
    assert service.search_resolution_types("Necesito autorizar una actuación experimental") == []


def test_orchestrator_routes_taxonomy_before_filtered_precedent(tmp_path):
    service, _index = make_service(tmp_path)
    _family, _type_node, subtype = create_tree(service)
    resolution = service.create_manual_resolution(ManualResolutionInput(
        resolution_number="100/026", title="Autorización experimental", status="active",
        normalized_text="VISTO: prueba\nATENTO: prueba\nRESUELVE:\n1º.- Autorízase.",
        assignments=[ResolutionAssignmentInput(taxonomy_node_id=subtype["id"], role="canonical")],
    ), sync=False)

    class RoutingAgents:
        def classify_resolution(self, context):
            assert context["candidatos"][0]["taxonomy_node_id"] == subtype["id"]
            return LLMRun(output=ResolutionClassification(
                taxonomy_node_id=subtype["id"], confidence=.8, rationale="Coincide con la actuación", needs_clarification=False,
            ), usage={"requests": 1, "input_tokens": 1, "output_tokens": 1, "total_tokens": 2}, duration_ms=1)

        def intake(self, context):
            assert context["clasificacion_tipologica"]["taxonomy_node_id"] == subtype["id"]
            assert context["antecedentes_oficiales"][0]["resolution_id"] == resolution["id"]
            return LLMRun(output=IntakeOutput(
                match_status="none", assistant_message="Complete los datos", matched_examples=[],
                form=DynamicForm(title="Datos", fields=[FormField(id="objeto", label="Objeto", field_type="text")]),
            ), usage={"requests": 1, "input_tokens": 1, "output_tokens": 1, "total_tokens": 2}, duration_ms=1)

    orchestrator = Orchestrator(
        service.settings, Storage(tmp_path / "conversations.sqlite3"), RoutingAgents(), legal_knowledge=service
    )
    state = orchestrator.create_conversation("Necesito autorizar una actuación experimental")
    assert state.selected_taxonomy_id == subtype["id"]
    assert state.official_references[0]["role"] == "canonical"
    assert state.last_debug["tools_executed"][:2] == ["search_resolution_types", "search_resolution_examples"]
