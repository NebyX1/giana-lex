import importlib
import pkgutil

import skills
from skills.base import Skill


def discover_skills() -> dict[str, Skill]:
    discovered: dict[str, Skill] = {}
    for module_info in pkgutil.iter_modules(skills.__path__):
        if module_info.name in {"base", "registry"} or module_info.name.startswith("_"):
            continue
        module = importlib.import_module(f"skills.{module_info.name}")
        candidate = getattr(module, "skill", None)
        if isinstance(candidate, Skill):
            discovered[candidate.key] = candidate
    return discovered
