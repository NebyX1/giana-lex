import importlib
import pkgutil
from pathlib import Path
from typing import Any

from .base import Tool


class ToolRegistry:
    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        if not tool.name or tool.name in self._tools:
            raise ValueError(f"Tool duplicada o invalida: {tool.name}")
        self._tools[tool.name] = tool

    def discover(self, package_name: str = "tools") -> "ToolRegistry":
        package = importlib.import_module(package_name)
        for module_info in pkgutil.iter_modules(package.__path__):
            if module_info.name in {"base", "registry"} or module_info.name.startswith("_"):
                continue
            module = importlib.import_module(f"{package_name}.{module_info.name}")
            tool = getattr(module, "tool", None)
            if isinstance(tool, Tool):
                self.register(tool)
        return self

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def definitions(self, allowed_names: set[str] | None = None) -> list[dict[str, Any]]:
        return [
            tool.definition()
            for name, tool in sorted(self._tools.items())
            if allowed_names is None or name in allowed_names
        ]

    def execute(self, name: str, arguments: dict[str, Any], context: dict[str, Any]) -> Any:
        tool = self.get(name)
        if tool is None:
            raise KeyError(f"Tool desconocida: {name}")
        return tool.invoke(arguments, context)

    @property
    def names(self) -> set[str]:
        return set(self._tools)
