"""Formulario local disponible incluso si la búsqueda o el proveedor no responden."""

from schemas import DynamicForm, FormField, IntakeOutput
from tools.search_examples import normalize_text


def generic_intake(request: str, *, interrupted: bool = False) -> IntakeOutput:
    message = (
        "No pude confirmar un antecedente adecuado en el tiempo disponible."
        if interrupted else "No encontré un antecedente suficientemente parecido para usar como modelo."
    )
    fields = [
        FormField(id="decision", label="Decisión que debe disponer el documento", field_type="textarea",
                  help_text="Detalle el objeto, el alcance y el resultado que necesita."),
        FormField(id="organismo", label="Organismo, área solicitante y autoridad que resolverá", field_type="text"),
        FormField(id="fundamentos", label="Hechos y motivos de la decisión", field_type="textarea"),
        FormField(id="expediente", label="Expediente y actuaciones previas", field_type="textarea", required=False),
        FormField(id="normativa", label="Normas, informes y autorizaciones disponibles", field_type="textarea", required=False,
                  help_text="Incluya únicamente referencias conocidas; si faltan, indique qué debe verificarse."),
    ]
    terms = set(normalize_text(request))
    if any(term.startswith(("contrat", "zafral", "arrendamiento")) for term in terms):
        fields.extend([
            FormField(id="contratado", label="Persona o entidad a contratar e identificación", field_type="textarea"),
            FormField(id="funciones", label="Tareas, destino y condiciones de prestación", field_type="textarea",
                      help_text="Indique área, lugar, horario o dedicación y responsable de supervisión."),
            FormField(id="plazo", label="Plazo y fecha de inicio de la contratación", field_type="text"),
            FormField(id="remuneracion", label="Remuneración o monto y forma de pago", field_type="textarea"),
            FormField(id="presupuesto", label="Disponibilidad presupuestal e imputación del gasto", field_type="textarea", required=False),
            FormField(id="seleccion", label="Procedimiento de selección y autorizaciones previas", field_type="textarea", required=False),
        ])
    else:
        fields.extend([
            FormField(id="destinatarios", label="Personas o entidades alcanzadas", field_type="textarea"),
            FormField(id="plazos", label="Fechas, plazos y condiciones de ejecución", field_type="textarea", required=False),
            FormField(id="recursos", label="Montos, recursos e imputación presupuestal, si corresponde", field_type="textarea", required=False),
        ])
    fields.append(FormField(id="comunicaciones", label="Oficinas o personas a notificar", field_type="textarea", required=False))
    return IntakeOutput(
        match_status="none",
        assistant_message=f"{message} Continuamos con una plantilla genérica. Complete el formulario para adaptarla a su caso.",
        form=DynamicForm(title="Datos para preparar el documento", fields=fields,
                         description="La solicitud original se conserva. Si desconoce un dato, indíquelo para identificar lo que falta confirmar."),
    )
