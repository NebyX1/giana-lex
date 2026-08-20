from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    version: int
    tools: tuple[str, ...]
    instructions: str
    path: Path


class SkillLoader:
    def __init__(self, root: Path):
        self.root = root
        self.skills: dict[str, Skill] = {}

    def discover(self) -> dict[str, Skill]:
        discovered: dict[str, Skill] = {}
        for path in sorted(self.root.glob("*/SKILL.md")):
            skill = self._load(path)
            if skill.name in discovered:
                raise ValueError(f"Skill duplicada: {skill.name}")
            discovered[skill.name] = skill
        self.skills = discovered
        return discovered

    def _load(self, path: Path) -> Skill:
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---\n") or "\n---\n" not in text[4:]:
            raise ValueError(f"Frontmatter YAML faltante: {path}")
        frontmatter, body = text[4:].split("\n---\n", 1)
        metadata = yaml.safe_load(frontmatter) or {}
        name = metadata.get("name")
        description = metadata.get("description")
        version = metadata.get("version")
        tools = metadata.get("tools", [])
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"Nombre de skill invalido: {path}")
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"Descripcion de skill invalida: {path}")
        if not isinstance(version, int) or version < 1:
            raise ValueError(f"Version de skill invalida: {path}")
        if not isinstance(tools, list) or not all(isinstance(tool, str) for tool in tools):
            raise ValueError(f"Tools de skill invalidas: {path}")
        return Skill(name.strip(), description.strip(), version, tuple(tools), body.strip(), path)

    def get(self, name: str) -> Skill | None:
        return self.skills.get(name)
