"""Real cloud smoke test for the complete legal-agent workflow.

The test uses an in-memory database and synthetic facts. It does not read or
modify production conversations. It exits non-zero unless a validated
resolution reaches ``completed``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app
from app.api.agent import _prompt_and_tools, _tool_context
from app.extensions import db
from app.models import AgentSession, Message, ProviderConnection, ToolCall, User
from agent.permissions import PermissionPolicy
from agent.runtime import AgentRuntime
from harness import HarnessOrchestrator, HarnessSettings
from llm.openai_compatible import OpenAICompatibleProvider
from tools.registry import ToolRegistry


SYNTHETIC_REQUEST = """
Redactá una resolución departamental de transposición de fondos con estos datos ya confirmados:
- Intendencia Departamental de Lavalleja, Minas, 16 de agosto de 2026.
- Monto: $ 100.000 UYU.
- Origen: Programa 101, Objeto de Gasto 0, partida 0.1.1, con saldo disponible.
- Destino: Programa 202, Objeto de Gasto 2, partida 2.1.1; no corresponde a Transferencias/OG 5.
- Finalidad: adquisición de insumos para mantenimiento vial.
- Informe previo favorable de la Dirección de Hacienda N.º 88/2026, de 15/08/2026.
- Norma presupuestal aplicable: Decreto Departamental N.º 4.076/2026.
- Firma el Intendente; debe comunicarse al Tribunal de Cuentas y a la Junta Departamental.
Usá únicamente fuentes oficiales recuperadas y devolvé el borrador estructurado completo.
""".strip()

SYNTHETIC_CONTRACT_REQUEST = """
Redactá un contrato de arrendamiento de obra completo con datos exclusivamente sintéticos para una prueba:
- Comitente: Intendencia Departamental de Lavalleja, representada por el Intendente; domicilio en Minas.
- Contratada ficticia: Ing. Ana Silva, profesional independiente; sus identificadores fiscales quedan para revisión humana.
- Objeto: elaborar un diagnóstico estructural y un proyecto ejecutivo para la recuperación de un puente rural.
- Entregables: relevamiento, memoria de cálculo, planos, presupuesto y cronograma; recepción por la Dirección General de Obras.
- Plazo: 60 días corridos desde la firma.
- Precio: $ 480.000 UYU más IVA si corresponde; 30% al aprobar el relevamiento y 70% al aceptar el proyecto ejecutivo.
- La profesional trabaja con autonomía técnica, confidencialidad y obligación de corregir observaciones dentro de 10 días.
- Expediente, procedimiento de contratación, crédito e intervenciones quedan expresamente sujetos a revisión antes de firmar.
Investigá sólo lo indispensable, no inventes referencias y entregá el BORRADOR contractual completo.
""".strip()

SYNTHETIC_CONTRACT_MINIMAL_REQUEST = (
    "Quiero redactar una contratación por arrendamiento de obra, para el arquitecto Martín Lupo"
)


def synthetic_answer(question: dict, scenario: str) -> str:
    if scenario != "contract-minimal":
        options = question.get("options") or []
        return options[0] if options else "Confirmado según los datos sintéticos del expediente."
    text = str(question.get("question") or "").casefold()
    options = question.get("options") or []
    if options:
        direct = next((option for option in options if "direct" in str(option).casefold()), None)
        return str(direct or options[0])
    if any(word in text for word in ("gobierno", "comitente", "contratante", "intendencia")):
        return "Intendencia Departamental de Lavalleja."
    if any(word in text for word in ("objeto", "trabajo", "resultado", "entregable")):
        return "Asesoramiento y entrega de un plan departamental de obras urbanas para Minas, período 2027-2028."
    if any(word in text for word in ("plazo", "duración", "inicio", "fecha")):
        return "Del 1 de setiembre al 31 de diciembre de 2026."
    if any(word in text for word in ("precio", "monto", "pago", "honorario")):
        return "$ 100.000 UYU más IVA por mes, contra entrega y conformidad del informe mensual."
    if any(word in text for word in ("lugar", "dependencia", "supervisión", "contraparte")):
        return "Coordinación institucional de Secretaría General, sin subordinación técnica."
    if any(word in text for word in ("expediente", "procedimiento", "crédito", "imputación")):
        return "Pendiente de incorporar y verificar antes de la firma."
    return "Martín Lupo; los identificadores personales y fiscales quedan pendientes de verificación antes de firmar."


def answer_pending(session: AgentSession, scenario: str) -> None:
    pending = (
        ToolCall.query.filter_by(session_id=session.id, status="waiting_for_user")
        .order_by(ToolCall.id.desc())
        .first()
    )
    if pending is None:
        raise RuntimeError("Session waits for user without a pending ask_user call")
    payload = json.loads(session.pending_question or "{}")
    answers = {}
    for question in payload.get("questions", []):
        answers[question["id"]] = synthetic_answer(question, scenario)
    result = json.dumps({"answers": answers}, ensure_ascii=False)
    pending.status = "completed"
    pending.result = result
    db.session.add(Message(session_id=session.id, role="tool", content=result, tool_call_id=pending.call_id))
    session.pending_question = None
    session.status = "ready"
    db.session.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:11434/v1")
    parser.add_argument("--model", default="deepseek-v4-flash:0731-cloud")
    parser.add_argument("--max-phases", type=int, default=3)
    parser.add_argument(
        "--scenario",
        choices=("transposition", "contract", "contract-minimal"),
        default="transposition",
    )
    args = parser.parse_args()

    app = create_app("testing")
    app.config.update(
        HARNESS_ENABLED=True,
        HARNESS_MODE="adaptive",
        HARNESS_MAX_RETRIES=2,
        HARNESS_MAX_LLM_CALLS=10,
        HARNESS_RETRY_BACKOFF_SECONDS=0.25,
        LLM_FALLBACK_MODELS="glm-5.2:cloud",
    )
    with app.app_context():
        db.create_all()
        user = User(email="cloud-e2e@example.invalid", display_name="Cloud E2E", password_hash="unused")
        db.session.add(user)
        db.session.flush()
        connection = ProviderConnection(
            user_id=user.id,
            provider="ollama",
            display_name="Ollama Cloud E2E",
            auth_mode="none",
            base_url=args.base_url,
            default_model=args.model,
        )
        db.session.add(connection)
        db.session.flush()
        if args.scenario == "contract":
            synthetic_request = SYNTHETIC_CONTRACT_REQUEST
        elif args.scenario == "contract-minimal":
            synthetic_request = SYNTHETIC_CONTRACT_MINIMAL_REQUEST
        else:
            synthetic_request = SYNTHETIC_REQUEST
        session = AgentSession(
            user_id=user.id,
            provider_connection_id=connection.id,
            title=f"Cloud E2E {args.scenario}",
            status="ready",
            model=args.model,
            active_skills=json.dumps(["redactor-legal"]),
        )
        db.session.add(session)
        db.session.flush()
        db.session.add(Message(session_id=session.id, role="user", content=synthetic_request))
        db.session.commit()

        registry = ToolRegistry().discover()
        permissions = PermissionPolicy.load(BACKEND_ROOT / "config" / "permissions.yaml")
        settings = HarnessSettings.from_config(app.config)
        harness = HarnessOrchestrator(synthetic_request, settings)
        event_names: list[str] = []

        for _phase in range(args.max_phases):
            system_prompt, allowed_tools = _prompt_and_tools(session, registry, harness)
            runtime = AgentRuntime(
                OpenAICompatibleProvider(connection),
                registry,
                permissions,
                app.config["AGENT_MAX_STEPS"],
                observer=harness,
            )
            events = list(runtime.run(session, system_prompt, allowed_tools, _tool_context(session)))
            event_names.extend(event["event"] for event in events)
            if session.status == "completed":
                break
            if session.status != "waiting_for_user":
                break
            answer_pending(session, args.scenario)
            harness.resume_execution()

        final_message = next((message for message in reversed(session.messages) if message.role == "assistant" and message.content.strip()), None)
        payload = None
        if final_message and final_message.content.strip().startswith("{"):
            try:
                payload = json.loads(final_message.content)
            except json.JSONDecodeError:
                payload = None
        calls = list(session.tool_calls)
        executed_calls = [call for call in calls if call.status != "skipped"]
        tool_counts: dict[str, int] = {}
        for call in executed_calls:
            tool_counts[call.tool_name] = tool_counts.get(call.tool_name, 0) + 1
        contract_ok = bool(
            final_message
            and "BORRADOR" in final_message.content.upper()
            and "CONTRATO" in final_message.content.upper()
            and ("OBJETO" in final_message.content.upper() or "CLÁUSULA" in final_message.content.upper())
        )
        report = {
            "status": session.status,
            "scenario": args.scenario,
            "model": args.model,
            "events": event_names,
            "tool_calls": [{"name": call.tool_name, "status": call.status} for call in calls],
            "first_tool": calls[0].tool_name if calls else None,
            "tool_counts": tool_counts,
            "failed_tools": sum(call.status == "failed" for call in calls),
            "retrieval_calls": sum(tool_counts.get(name, 0) for name in (
                "search_national_norms", "search_departmental_norms", "search_resolutions",
                "search_examples", "search_web", "fetch_web", "verify_legal_reference",
            )),
            "final_json": bool(payload),
            "final_keys": sorted(payload) if isinstance(payload, dict) else [],
            "resuelve_count": len(payload.get("resuelve", [])) if isinstance(payload, dict) else 0,
            "contract_complete": contract_ok,
            "final_chars": len(final_message.content) if final_message else 0,
            "validation_errors": harness.state.validation_errors,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2))
        document_flow = args.scenario in {"transposition", "contract", "contract-minimal"}
        example_first = bool(calls and calls[0].tool_name == "search_examples") if document_flow else True
        bounded = (
            report["failed_tools"] == 0
            and report["retrieval_calls"] <= 6
            and tool_counts.get("search_national_norms", 0) <= 1
            and tool_counts.get("search_departmental_norms", 0) <= 1
        )
        scenario_ok = contract_ok if args.scenario in {"contract", "contract-minimal"} else bool(payload and payload.get("resuelve"))
        if session.status != "completed" or not scenario_ok or not bounded or not example_first:
            raise SystemExit(1)


if __name__ == "__main__":
    main()
