ACT_LABELS = {
    "fund_transposition": "transposición de rubros",
    "contract_renewal": "renovación contractual",
    "donation": "donación",
    "new_contract": "nueva contratación",
    "hours_removal": "quita o reducción de horas",
    "generic": "resolución administrativa",
}


def intake_act_label(subtype: str) -> str:
    return ACT_LABELS.get(subtype, subtype.replace("_", " "))


def required_missing_groups(form) -> list[str]:
    if form is None:
        return []
    groups = []
    for section in (form.schema_json or {}).get("sections", []):
        if any(field.get("required") for field in section.get("fields", [])):
            groups.append(str(section.get("title") or "Datos requeridos"))
    return groups
