from hashlib import sha256
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

from legal.domain.models import FormFieldDefinition


class PackIntent(BaseModel):
    family: Literal["resolution_drafting"]
    subtype: str


class PackSection(BaseModel):
    id: str
    title: str
    description: str | None = None
    field_keys: list[str]


class WorkflowPack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version: int = Field(ge=1)
    status: Literal["active", "inactive"]
    jurisdiction: str
    intent: PackIntent
    precedent_types: list[str]
    fields: list[FormFieldDefinition]
    form_title: str = "Información requerida"
    form_description: str = "Complete únicamente los datos confirmados."
    sections: list[PackSection] = Field(default_factory=list)
    legal_issues: list[str]
    required_sections: list[str]
    require_verified_competence: bool = True


class LoadedWorkflowPack(BaseModel):
    pack: WorkflowPack
    checksum: str
    source_path: str


class WorkflowPackRegistry:
    def __init__(self, root: Path | None = None):
        self.root = root or Path(__file__).with_name("packs")
        self._packs = self._load()

    def _load(self) -> dict[tuple[str, int], LoadedWorkflowPack]:
        loaded = {}
        for path in sorted(self.root.glob("*.yaml")):
            raw = path.read_bytes()
            pack = WorkflowPack.model_validate(yaml.safe_load(raw))
            key = (pack.id, pack.version)
            if key in loaded:
                raise ValueError(f"Duplicate workflow pack {pack.id} v{pack.version}")
            loaded[key] = LoadedWorkflowPack(
                pack=pack, checksum=sha256(raw).hexdigest(), source_path=str(path)
            )
        if not loaded:
            raise RuntimeError("No legal workflow packs are installed")
        return loaded

    def get(self, pack_id: str, version: int | None = None) -> LoadedWorkflowPack:
        if version is None:
            versions = [candidate for (candidate_id, _), candidate in self._packs.items() if candidate_id == pack_id]
            if not versions:
                raise ValueError(f"Unknown workflow pack {pack_id}")
            loaded = max(versions, key=lambda item: item.pack.version)
            if loaded.pack.status != "active":
                raise ValueError(f"Workflow pack {pack_id} v{loaded.pack.version} is inactive")
            return loaded
        try:
            loaded = self._packs[(pack_id, version)]
        except KeyError as exc:
            raise ValueError(f"Unknown workflow pack {pack_id} v{version}") from exc
        if loaded.pack.status != "active":
            raise ValueError(f"Workflow pack {pack_id} v{version} is inactive")
        return loaded

    def list_active(self) -> list[LoadedWorkflowPack]:
        latest = {}
        for item in self._packs.values():
            if item.pack.status == "active" and (
                item.pack.id not in latest or item.pack.version > latest[item.pack.id].pack.version
            ):
                latest[item.pack.id] = item
        return list(latest.values())
