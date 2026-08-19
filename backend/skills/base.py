from abc import ABC
from typing import Any

from schemas import LLMRun


class Skill(ABC):
    key: str
    name: str
    description: str
    instructions: str

    def metadata(self) -> dict[str, str]:
        return {"key": self.key, "name": self.name, "description": self.description}

    def run(self, agents: Any, context: dict) -> LLMRun:
        return agents.skill(self.key, self.instructions, context)
