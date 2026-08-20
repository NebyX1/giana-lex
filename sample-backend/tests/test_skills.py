import json
from pathlib import Path

import yaml

from agent.skill_loader import SkillLoader

SKILLS_ROOT = Path(__file__).resolve().parents[1] / "skills"
EXPECTED_SKILLS = {
    "analista-legal",
    "analista-politico",
    "auditor-compliance",
    "consultor-redaccion",
    "investigador-normativo",
    "redactor-legal",
    "revisor-procedimental",
    "corrector-estilo-ortografia-legal",
}

REAL_TOOLS = {
    "ask_user",
    "get_current_agent_status",
    "search_departmental_norms",
    "search_national_norms",
    "search_resolutions",
    "search_examples",
    "search_web",
    "fetch_web",
    "read_document",
    "analyze_resolution",
    "extract_legal_references",
    "verify_legal_reference",
    "load_mold",
    "compare_with_mold",
    "review_procedure",
    "compare_documents",
    "create_docx",
}


def _all_skills() -> dict[str, dict]:
    loader = SkillLoader(SKILLS_ROOT)
    skills = loader.discover()
    return {name: _parse_skill_file(skills[name].path) for name, skill in skills.items()}


def _parse_skill_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    frontmatter, _body = text[4:].split("\n---\n", 1)
    return yaml.safe_load(frontmatter)


def test_all_eight_skills_exist():
    dirs = {path.name for path in SKILLS_ROOT.iterdir() if path.is_dir()}
    assert EXPECTED_SKILLS <= dirs


def test_every_skill_has_skill_md():
    for skill in EXPECTED_SKILLS:
        assert (SKILLS_ROOT / skill / "SKILL.md").is_file()


def test_loader_loads_all_eight():
    loader = SkillLoader(SKILLS_ROOT)
    skills = loader.discover()
    assert set(skills) == EXPECTED_SKILLS


def test_names_unique():
    loader = SkillLoader(SKILLS_ROOT)
    names = list(loader.discover())
    assert len(names) == len(set(names)) == 8


def test_every_skill_has_name_and_description():
    for name, metadata in _all_skills().items():
        assert metadata.get("name") == name
        description = metadata.get("description")
        assert isinstance(description, str) and description.strip()


def test_descriptions_differentiate_skills():
    descriptions = {name: metadata["description"] for name, metadata in _all_skills().items()}
    for skill in ("investigador-normativo", "analista-legal"):
        assert "investigar" in descriptions[skill] or "localiza" in descriptions[skill]
    assert "no" in descriptions["analista-legal"].lower()
    corrector = descriptions["corrector-estilo-ortografia-legal"].lower()
    assert "altera" in corrector or "preservando" in corrector
    assert "no determina legalidad" in descriptions["analista-politico"].lower()


def test_declared_tools_are_real():
    for name, metadata in _all_skills().items():
        for tool in metadata.get("tools", []):
            assert tool in REAL_TOOLS, f"{name} declara tool inexistente: {tool}"


def test_no_tool_invented():
    for name, metadata in _all_skills().items():
        for tool in metadata.get("tools", []):
            assert tool not in {"search_laws", "search_cases", "legal_database"}


def test_versions_consistent():
    for name, metadata in _all_skills().items():
        version = metadata.get("version")
        assert isinstance(version, int) and version >= 1
        if name == "corrector-estilo-ortografia-legal":
            assert version == 1
        else:
            assert version >= 2


def test_references_dir_does_not_load_as_skill():
    loader = SkillLoader(SKILLS_ROOT)
    names = set(loader.discover())
    for name in names:
        assert f"{name}/references" not in names
        assert "references" not in names


def test_evals_dir_does_not_load_as_skill():
    loader = SkillLoader(SKILLS_ROOT)
    names = set(loader.discover())
    assert "evals" not in names


def test_every_skill_has_references_and_evals():
    for skill in EXPECTED_SKILLS:
        assert (SKILLS_ROOT / skill / "references").is_dir(), f"{skill} sin references/"
        assert (SKILLS_ROOT / skill / "evals").is_dir(), f"{skill} sin evals/"


def test_evals_are_valid_json():
    for path in SKILLS_ROOT.rglob("evals/*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict)
        for key in ("trigger", "non_trigger", "normal_cases", "adversarial_cases", "missing_information", "hallucination_cases"):
            assert key in data, f"{path} falta clave {key}"


def test_skill_md_not_gigantic():
    for skill in EXPECTED_SKILLS:
        size = (SKILLS_ROOT / skill / "SKILL.md").stat().st_size
        assert size < 12000, f"{skill}/SKILL.md demasiado grande: {size} bytes"


def test_skilles_include_trigger_and_antitrigger():
    for skill in EXPECTED_SKILLS:
        text = (SKILLS_ROOT / skill / "SKILL.md").read_text(encoding="utf-8")
        assert "Trigger" in text or "ACTIVAR" in text, f"{skill} sin trigger"
        assert "Anti-trigger" in text or "NO ACTIVAR" in text, f"{skill} sin anti-trigger"


def test_redactor_has_validation_script():
    script = SKILLS_ROOT / "redactor-legal" / "scripts" / "validate_resolution.py"
    assert script.is_file()
