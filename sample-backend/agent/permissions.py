from enum import Enum
from pathlib import Path

import yaml


class Permission(str, Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"


class PermissionPolicy:
    def __init__(self, rules: dict[str, Permission]):
        self.rules = rules

    @classmethod
    def load(cls, path: Path) -> "PermissionPolicy":
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            raise ValueError("permissions.yaml debe contener un mapa.")
        return cls({str(name): Permission(str(value).lower()) for name, value in raw.items()})

    def check(self, tool_name: str) -> Permission:
        return self.rules.get(tool_name, Permission.DENY)
