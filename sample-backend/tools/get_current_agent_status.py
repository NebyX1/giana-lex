from typing import Any

from pydantic import BaseModel

from .base import Tool


class StatusInput(BaseModel):
    include_session: bool = True


class GetCurrentAgentStatus(Tool[StatusInput]):
    name = "get_current_agent_status"
    description = "Obtiene el estado observable de la ejecucion actual del agente."
    input_schema = StatusInput

    def execute(self, arguments: StatusInput, context: dict[str, Any]) -> dict[str, Any]:
        result = {"status": context.get("status", "running")}
        if arguments.include_session:
            result["session_id"] = context.get("session_id")
        return result


tool = GetCurrentAgentStatus()
