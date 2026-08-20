from collections.abc import Callable
from uuid import UUID


class InlineWorkflowDispatcher:
    def __init__(self, handler: Callable[[UUID], None]):
        self.handler = handler

    def dispatch(self, command_id: UUID) -> None:
        self.handler(command_id)
