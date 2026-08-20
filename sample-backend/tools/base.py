from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

from pydantic import BaseModel


InputT = TypeVar("InputT", bound=BaseModel)


class Tool(ABC, Generic[InputT]):
    name: str
    description: str
    input_schema: type[InputT]
    permission: str = "allow"

    def definition(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema.model_json_schema(),
            },
        }

    def invoke(self, arguments: dict[str, Any], context: dict[str, Any] | None = None) -> Any:
        validated = self.input_schema.model_validate(arguments)
        return self.execute(validated, context or {})

    @abstractmethod
    def execute(self, arguments: InputT, context: dict[str, Any]) -> Any:
        raise NotImplementedError


class AgentWaitingForUser(Exception):
    def __init__(self, payload: dict[str, Any]):
        super().__init__("El agente espera una respuesta del usuario.")
        self.payload = payload
