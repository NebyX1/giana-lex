import pytest

from orchestrator import OperationError, validate_form_answers
from schemas import DynamicForm, FormField


@pytest.fixture
def generic_form():
    return DynamicForm(
        title="Datos",
        fields=[
            FormField(id="name", label="Nombre", field_type="text"),
            FormField(id="detail", label="Detalle", field_type="textarea", required=False),
            FormField(id="amount", label="Monto", field_type="number"),
            FormField(id="date", label="Fecha", field_type="date"),
            FormField(id="kind", label="Tipo", field_type="select", options=["A", "B"]),
            FormField(id="confirmed", label="Confirmado", field_type="boolean"),
        ],
    )


def test_form_accepts_supported_types(generic_form):
    answers = validate_form_answers(
        generic_form,
        {"name": "Ana", "amount": 10.5, "date": "2026-08-19", "kind": "A", "confirmed": False},
    )
    assert answers["amount"] == 10.5
    assert answers["confirmed"] is False


@pytest.mark.parametrize(
    "answers",
    [
        {"amount": 2, "date": "2026-08-19", "kind": "A", "confirmed": True},
        {"name": "Ana", "amount": "dos", "date": "2026-08-19", "kind": "A", "confirmed": True},
        {"name": "Ana", "amount": 2, "date": "2026-08-19", "kind": "C", "confirmed": True},
        {"name": "Ana", "amount": 2, "date": "ayer", "kind": "A", "confirmed": True},
        {"name": "Ana", "amount": 2, "date": "2026-08-19", "kind": "A", "confirmed": "si"},
    ],
)
def test_form_rejects_missing_and_invalid_values(generic_form, answers):
    with pytest.raises(OperationError) as error:
        validate_form_answers(generic_form, answers)
    assert error.value.code == "validation_error"
