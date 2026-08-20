from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from .base import AgentWaitingForUser, Tool


class Question(BaseModel):
    id: str = Field(min_length=1, max_length=80)
    type: Literal["text", "single_choice", "multiple_choice", "confirmation"]
    question: str = Field(min_length=1, max_length=1000)
    options: list[str] = Field(default_factory=list, max_length=20)
    required: bool = True

    @model_validator(mode="after")
    def validate_options(self):
        if self.type in {"single_choice", "multiple_choice"} and len(self.options) < 2:
            raise ValueError("Las preguntas de seleccion requieren al menos dos opciones.")
        return self


class AskUserInput(BaseModel):
    questions: list[Question] = Field(min_length=1, max_length=10)


class AskUser(Tool[AskUserInput]):
    name = "ask_user"
    description = "Pausa la ejecucion y solicita al usuario informacion faltante."
    input_schema = AskUserInput

    def execute(self, arguments: AskUserInput, context: dict[str, Any]) -> Any:
        raise AgentWaitingForUser(arguments.model_dump())


tool = AskUser()
