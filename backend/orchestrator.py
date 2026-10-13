import time
from datetime import date
from concurrent.futures import Future, TimeoutError as FutureTimeout
from threading import BoundedSemaphore, Event, Lock, Thread
from typing import Any
from hashlib import sha256

from pydantic import ValidationError

from config import Settings
from conversation_intro import introductory_response
from intake_fallback import generic_intake
from example_verification import Evidence, Finding, verify_draft
from schemas import DynamicForm, ExampleCandidate, LLMRun, SkillOutput
from skills.registry import discover_skills
from state import ConversationState, InvalidTransition, Stage, utc_now
from storage import Storage
from tools.load_mold import load_mold
from tools.search_examples import has_lexical_support, load_selected_examples, search_examples


class NotFoundError(ValueError):
    pass


class OperationError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def validate_form_answers(form: DynamicForm, answers: dict[str, Any]) -> dict[str, Any]:
    errors: dict[str, str] = {}
    validated: dict[str, Any] = {}
    for field in form.fields:
        value = answers.get(field.id)
        missing = value is None or (isinstance(value, str) and not value.strip())
        if missing:
            if field.required:
                errors[field.id] = "Este campo es obligatorio"
            continue
        if field.field_type in {"text", "textarea"}:
            if not isinstance(value, str):
                errors[field.id] = "Debe ser texto"
            else:
                validated[field.id] = value.strip()
        elif field.field_type == "number":
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors[field.id] = "Debe ser un numero"
            else:
                validated[field.id] = value
        elif field.field_type == "boolean":
            if not isinstance(value, bool):
                errors[field.id] = "Debe ser verdadero o falso"
            else:
                validated[field.id] = value
        elif field.field_type == "select":
            if not isinstance(value, str) or value not in (field.options or []):
                errors[field.id] = "Debe elegir una opcion valida"
            else:
                validated[field.id] = value
        elif field.field_type == "date":
            try:
                validated[field.id] = date.fromisoformat(value).isoformat() if isinstance(value, str) else None
                if validated[field.id] is None:
                    raise ValueError
            except ValueError:
                errors[field.id] = "Debe ser una fecha ISO valida (AAAA-MM-DD)"
    if errors:
        detail = "; ".join(f"{field}: {message}" for field, message in errors.items())
        raise OperationError("validation_error", f"Hay campos invalidos o incompletos: {detail}", False)
    return validated


class Orchestrator:
    def __init__(self, settings: Settings, storage: Storage, agents: Any, legal_knowledge=None, example_catalog=None):
        self.settings = settings
        self.storage = storage
        self.agents = agents
        self.skills = discover_skills()
        self.legal_knowledge = legal_knowledge
        self.example_catalog = example_catalog
        self._lock = Lock()
        self._intake_slots = BoundedSemaphore(4)

    def _get(self, conversation_id: str) -> ConversationState:
        state = self.storage.get(conversation_id)
        if not state:
            raise NotFoundError("Conversacion no encontrada")
        return state

    def _tool(self, state: ConversationState, name: str, function, *args):
        started = time.perf_counter()
        try:
            result = function(*args)
        except Exception as exc:
            raise OperationError(f"{name}_error", f"Fallo tecnico en {name}: {exc}", True) from exc
        state.add_event(
            {"type": "tool", "name": name, "duration_ms": round((time.perf_counter() - started) * 1000)}
        )
        return result

    def _record_llm(self, state: ConversationState, operation: str, run: LLMRun) -> None:
        state.add_event(
            {
                "type": "llm",
                "operation": operation,
                **run.usage,
                "duration_ms": run.duration_ms,
            }
        )

    def _set_debug(self, state: ConversationState, before: Stage, tools: list[str]) -> None:
        latest_llm = next((event for event in reversed(state.events) if event.get("type") == "llm"), {})
        state.last_debug = {
            "stage_before": before.value,
            "stage_after": state.stage.value,
            "tools_executed": tools,
            "example_candidates": [candidate.model_dump() for candidate in state.example_candidates],
            "examples_selected": [match.model_dump() for match in state.selected_examples],
            "llm": {key: latest_llm.get(key, 0) for key in (
                "requests", "input_tokens", "output_tokens", "total_tokens", "duration_ms"
            )},
        }

    def _respond_to_intro(self, state: ConversationState, message: str, reply: str) -> ConversationState:
        state.intro_messages.extend([{"role": "user", "text": message}, {"role": "assistant", "text": reply}])
        state.intro_messages = state.intro_messages[-30:]
        state.add_event({"type": "conversation_intro"})
        self._set_debug(state, Stage.NEW, [])
        state.last_debug["message"] = reply
        self.storage.save(state)
        return state

    def create_conversation(self, message: str, owner_user_id: int | None = None,
                            conversation_id: str | None = None) -> ConversationState:
        if not isinstance(message, str) or not message.strip():
            raise OperationError("validation_error", "El mensaje es obligatorio")
        message = message.strip()
        state = self._get(conversation_id) if conversation_id else ConversationState(
            original_request=message, owner_user_id=owner_user_id,
        )
        if state.stage != Stage.NEW:
            raise InvalidTransition("La consulta ya inició la preparación del documento")
        if reply := introductory_response(message):
            return self._respond_to_intro(state, message, reply)
        if self.agents is None:
            raise OperationError("llm_not_configured", "El proveedor LLM no esta configurado", False)
        state.original_request = message
        self.storage.save(state)
        before = state.stage
        state.transition(Stage.SEARCHING_EXAMPLES)
        if self.example_catalog is not None:
            search = self.example_catalog.search(state.original_request, 20)
            state.example_references = search["results"][:5]
            state.example_search_status = search["status"]
            state.example_corpus_version = search["corpus_version"]
            state.example_candidates = [ExampleCandidate(
                filename="catalog:" + item["id"], title=item["title"], score=item["score"],
                excerpt=item["excerpt"], example_id=item["id"], revision_id=item["revision_id"],
                match_class=item["match_class"], scope=item["scope"], reasons=item["reasons"],
                differences=item["differences"], defects=item["defectos_detectados"],
            ) for item in state.example_references]
            state.add_event({"type": "example_search", "status": search["status"], "duration_ms": search["duration_ms"],
                             "count": len(state.example_references)})
        self.storage.save(state)
        future = Future()
        cancelled = Event()
        late_requested = Event()
        response_saved = Event()
        worker_started = False
        working = state.model_copy(deep=True)

        def prepare():
            try:
                prepared = self._prepare_intake(working, cancelled)
                future.set_result(prepared)
                if late_requested.is_set() and response_saved.wait(5):
                    with self._lock:
                        current = self.storage.get(state.id)
                        if current and current.intake_pending:
                            current.intake_pending = False
                            if current.stage == Stage.COLLECTING_INFO and not current.form_history and not current.form_answers:
                                current.taxonomy_candidates = prepared.taxonomy_candidates
                                current.selected_taxonomy_id = prepared.selected_taxonomy_id
                                current.official_references = prepared.official_references
                                current.selected_examples = prepared.selected_examples
                                current.classification_warning = prepared.classification_warning
                                current.add_event({"type": "intake_completed_late"})
                            else:
                                current.add_event({"type": "intake_result_stale"})
                            self.storage.save(current)
            except Exception as exc:
                if not future.done():
                    future.set_exception(exc)
                if late_requested.is_set() and response_saved.wait(5):
                    with self._lock:
                        current = self.storage.get(state.id)
                        if current and current.intake_pending:
                            current.intake_pending = False
                            current.classification_warning = "La comparación detallada no pudo completarse; se conservan las referencias locales."
                            current.add_event({"type": "intake_failed_late"})
                            self.storage.save(current)
            finally:
                self._intake_slots.release()

        try:
            if not self._intake_slots.acquire(blocking=False):
                raise FutureTimeout()
            try:
                Thread(target=prepare, daemon=True, name="giana-intake").start()
                worker_started = True
            except Exception:
                self._intake_slots.release()
                raise
            state = future.result(timeout=max(0.01, self.settings.intake_timeout_seconds))
        except Exception as exc:
            if isinstance(exc, FutureTimeout) and worker_started:
                late_requested.set()
                state.intake_pending = True
            else:
                cancelled.set()
            output = generic_intake(state.original_request, interrupted=True)
            state.current_form = output.form
            state.classification_warning = "La comparación inicial continúa pendiente de revisión." if state.example_references else output.assistant_message
            state.last_debug["message"] = (
                f"Encontré {len(state.example_references)} referencias editoriales para orientar el formulario. "
                "La comparación detallada no terminó en el tiempo disponible; puede completar estos datos mientras tanto."
                if state.example_references else output.assistant_message
            )
            state.add_event({"type": "intake_fallback", "reason": "timeout" if isinstance(exc, FutureTimeout) else "unavailable"})
        state.transition(Stage.COLLECTING_INFO)
        message = state.last_debug["message"]
        tools = [event["name"] for event in state.events if event.get("type") == "tool"]
        self._set_debug(state, before, tools)
        state.last_debug["message"] = message
        self.storage.save(state)
        response_saved.set()
        return state

    def _prepare_intake(self, state: ConversationState, cancelled: Event) -> ConversationState:
        # This isolated copy is never persisted by the worker. Late results cannot
        # overwrite the fallback form or answers already submitted by the user.
        def bounded_call(function, *args):
            if cancelled.is_set():
                raise FutureTimeout()
            result = function(*args)
            if cancelled.is_set():
                raise FutureTimeout()
            return result

        def bounded_tool(state, name, function, *args):
            return bounded_call(self._tool, state, name, function, *args)

        taxonomy_candidates = []
        if self.legal_knowledge is not None:
            try:
                taxonomy_candidates = bounded_tool(
                    state, "search_resolution_types", self.legal_knowledge.search_resolution_types,
                    state.original_request, 5,
                )
            except OperationError:
                state.classification_warning = (
                    "No se pudo consultar el catálogo tipológico. Se continuará con el molde general y los antecedentes disponibles."
                )
            state.taxonomy_candidates = [item.model_dump() for item in taxonomy_candidates]
            if taxonomy_candidates:
                selected_id = None
                if hasattr(self.agents, "classify_resolution"):
                    try:
                        classification_run = bounded_call(self.agents.classify_resolution, {
                            "solicitud": state.original_request,
                            "candidatos": state.taxonomy_candidates,
                        })
                        self._record_llm(state, "resolution_classification", classification_run)
                        classification = classification_run.output
                        valid_ids = {item.taxonomy_node_id for item in taxonomy_candidates}
                        if classification.taxonomy_node_id in valid_ids and not classification.needs_clarification:
                            selected_id = classification.taxonomy_node_id
                        state.resolution_classification = classification.model_dump()
                    except Exception:
                        state.classification_warning = (
                            "No se pudo confirmar una tipología entre los candidatos. Se continuará con el molde general."
                        )
                elif taxonomy_candidates[0].score >= 0.5:
                    selected_id = taxonomy_candidates[0].taxonomy_node_id
                state.selected_taxonomy_id = selected_id
                if selected_id:
                    try:
                        references = bounded_tool(
                            state, "search_resolution_examples", self.legal_knowledge.search_resolution_examples,
                            selected_id, state.original_request, 5,
                        )
                        state.official_references = [item.model_dump() for item in references]
                    except OperationError:
                        state.selected_taxonomy_id = None
                        state.classification_warning = (
                            "La tipología sugerida no pudo verificarse. Se continuará con el molde general y los antecedentes disponibles."
                        )
                else:
                    state.classification_warning = (
                        "No se identificó una tipología suficientemente clara. Se continuará con el molde general y los antecedentes disponibles."
                    )
            elif not state.classification_warning:
                state.classification_warning = (
                    "No se encontró una tipología específica. Se continuará con el molde general y los antecedentes disponibles."
                )
        candidates = state.example_candidates if self.example_catalog is not None else bounded_tool(
            state, "search_examples", search_examples, state.original_request, self.settings.examples_dir,
            self.settings.examples_top_k,
        )
        mold = bounded_tool(state, "load_mold", load_mold, self.settings.molds_dir)
        run = bounded_call(self.agents.intake,
            {
                "solicitud": state.original_request,
                "candidatos": [candidate.model_dump() for candidate in candidates],
                "referencias_editoriales": state.example_references,
                "tipologias_candidatas": state.taxonomy_candidates,
                "clasificacion_tipologica": state.resolution_classification,
                "antecedentes_oficiales": state.official_references,
                "molde": mold,
            }
        )
        self._record_llm(state, "intake", run)
        output = run.output
        available = {candidate.filename: candidate for candidate in candidates}
        output.matched_examples = [
            match
            for match in output.matched_examples
            if match.filename in available and (self.example_catalog is not None or has_lexical_support(state.original_request, available[match.filename]))
        ][:5]
        if output.match_status == "none" and self.example_catalog is None:
            output.matched_examples = []
        if self.example_catalog is not None and not output.matched_examples and state.example_references:
            from schemas import ExampleMatch
            output.matched_examples = [ExampleMatch(filename="catalog:" + item["id"], relevance="strong" if item["match_class"] == "directa" else "partial",
                                                    reason="; ".join(item["reasons"])) for item in state.example_references[:3]]
        if self.example_catalog is not None and state.example_references:
            first = state.example_references[0]
            well_supported = first["match_class"] in {"directa", "cercana"} or any(
                reason.startswith("Términos de contexto:") and len(reason.split(",")) >= 2
                for reason in first["reasons"]
            )
            if well_supported and output.match_status == "none":
                # A model or fallback may fail to recognize a retrieved analogy.
                # Report only what the shared search service has actually found.
                output.match_status = "similar" if first["match_class"] == "directa" else "partial"
                output.assistant_message = (
                    f"Encontré {len(state.example_references)} referencias editoriales relacionadas. "
                    f"La más cercana es «{first['title']}»; su alcance es {first['scope']}. "
                    "Las usaré para orientar la estructura y las preguntas del caso, "
                    "sin trasladar hechos ni normas de otros expedientes."
                )
        state.example_candidates = candidates
        state.selected_examples = output.matched_examples
        state.current_form = output.form
        state.last_debug["message"] = output.assistant_message
        return state

    def submit_form(self, conversation_id: str, answers: dict[str, Any]) -> ConversationState:
        with self._lock:
            state = self._get(conversation_id)
            if state.stage != Stage.COLLECTING_INFO or not state.current_form:
                raise InvalidTransition("El formulario solo puede enviarse al recopilar informacion")
            before = state.stage
            submitted_form = state.current_form.model_dump()
            validated = validate_form_answers(state.current_form, answers)
            merged_answers = {**state.form_answers, **validated}
            try:
                mold = self._tool(state, "load_mold", load_mold, self.settings.molds_dir)
                example_filenames = [match.filename for match in state.selected_examples]
                if self.example_catalog is not None:
                    # Revalidation is essential: cached candidates cannot authorize a suspended revision.
                    fresh = {item["id"]: item for item in self.example_catalog.search(state.original_request, 20)["results"]}
                    examples = [{"id": item["id"], "revision_id": item["revision_id"], "title": item["title"],
                                 "scope": item["scope"], "content": item["authorized_content"],
                                 "differences": item["differences"], "defects": item["defectos_detectados"]}
                                for item in state.example_references if item["id"] in fresh and
                                fresh[item["id"]]["revision_id"] == item["revision_id"]][:5]
                else:
                    examples = self._tool(state, "load_selected_examples", load_selected_examples,
                                          example_filenames, self.settings.examples_dir)
                run = self.agents.draft(
                    {
                        "solicitud": state.original_request,
                        "datos_formulario": merged_answers,
                        "molde": mold,
                        "ejemplos_relevantes": examples,
                        "ejemplos_solo_como_estructura": False,
                        "modo_tipologia_general": state.selected_taxonomy_id is None,
                        "taxonomy_node_id": state.selected_taxonomy_id,
                        "antecedentes_oficiales": state.official_references,
                    }
                )
                self._record_llm(state, "draft", run)
                output = run.output
                state.form_answers = merged_answers
                state.form_history.append({
                    "form": submitted_form,
                    "answers": validated,
                    "submitted_at": utc_now(),
                })
                state.form_history = state.form_history[-30:]
                if output.status == "needs_more_info":
                    state.current_form = output.additional_form
                    state.transition(Stage.COLLECTING_INFO)
                else:
                    state.draft = output.draft_markdown
                    state.verification = None
                    state.verified_draft_hash = None
                    state.current_form = None
                    state.transition(Stage.DRAFT_REVIEW)
                self._set_debug(state, before, ["load_mold", "load_selected_examples"])
                state.last_debug["message"] = output.assistant_message
                self.storage.save(state)
                return state
            except OperationError:
                raise
            except Exception as exc:
                self.storage.save(state)
                raise OperationError("llm_provider_error", str(exc), True) from exc

    def revise(self, conversation_id: str, instructions: str) -> ConversationState:
        with self._lock:
            state = self._get(conversation_id)
            if state.stage != Stage.DRAFT_REVIEW or not state.draft:
                raise InvalidTransition("Solo se puede revisar un borrador pendiente")
            if not isinstance(instructions, str) or not instructions.strip():
                raise OperationError("validation_error", "Las instrucciones son obligatorias")
            before = state.stage
            try:
                run = self.agents.revision(
                    {
                        "borrador_vigente": state.draft,
                        "modificaciones": instructions.strip(),
                        "datos_esenciales": state.form_answers,
                    }
                )
                self._record_llm(state, "revision", run)
                state.draft = run.output.draft_markdown
                state.verification = None
                state.verified_draft_hash = None
                state.revision_count += 1
                state.revision_notes.append(instructions.strip())
                state.revision_notes = state.revision_notes[-10:]
                state.transition(Stage.DRAFT_REVIEW)
                self._set_debug(state, before, [])
                state.last_debug["message"] = run.output.assistant_message
                self.storage.save(state)
                return state
            except Exception as exc:
                self.storage.save(state)
                raise OperationError("llm_provider_error", str(exc), True) from exc

    def approve(self, conversation_id: str) -> ConversationState:
        with self._lock:
            state = self._get(conversation_id)
            if state.stage != Stage.DRAFT_REVIEW or not state.draft:
                raise InvalidTransition("No hay un borrador listo para aprobar")
            current_hash = sha256(state.draft.encode("utf-8")).hexdigest()
            if not state.verification or state.verified_draft_hash != current_hash:
                raise InvalidTransition("Debe comprobar la revisión actual del borrador antes de aprobar")
            if state.verification.get("context_status") == "unavailable":
                raise InvalidTransition("La comprobación contextual no terminó; vuelva a ejecutarla")
            if self.example_catalog:
                for reference in state.verification.get("examples", []):
                    if reference["id"].startswith("legacy:"):
                        continue
                    current_example = self.example_catalog.get(reference["id"])
                    if not current_example or not current_example["enabled"] or current_example["archived"] or current_example["revision_id"] != reference["revision_id"]:
                        raise InvalidTransition("Cambió una referencia usada en la comprobación; compruebe nuevamente")
            if any(item["severity"] == "critical" and not item["resolved"] for item in state.verification["findings"]):
                raise InvalidTransition("Hay contradicciones críticas pendientes de corrección")
            before = state.stage
            state.approved = True
            state.approved_draft_hash = current_hash
            state.transition(Stage.APPROVED)
            self._set_debug(state, before, [])
            state.last_debug["message"] = "Borrador aprobado. ¿Queres realizar algun analisis adicional?"
            self.storage.save(state)
            return state

    def check_draft(self, conversation_id: str, draft: str | None = None, resolved: dict[str, str] | None = None) -> ConversationState:
        with self._lock:
            state = self._get(conversation_id)
            if state.stage != Stage.DRAFT_REVIEW or not state.draft:
                raise InvalidTransition("La comprobación requiere un borrador en revisión")
            if draft is not None and draft != state.draft:
                if not isinstance(draft, str) or not draft.strip() or len(draft) > 200_000:
                    raise OperationError("validation_error", "Borrador inválido o demasiado extenso")
                state.draft = draft
                state.revision_count += 1
                state.verification = None
                state.verified_draft_hash = None
            current_references = []
            if self.example_catalog is not None:
                for reference in state.example_references:
                    item = self.example_catalog.get(reference["id"]) if not reference["id"].startswith("legacy:") else reference
                    if item and item.get("enabled") and item.get("revision_id") == reference.get("revision_id") and not item.get("archived"):
                        current_references.append(reference)
            report = verify_draft(state.draft, state.form_answers, current_references, state.revision_count,
                                  state.example_corpus_version, resolved=resolved)
            if self.agents is not None and hasattr(self.agents, "check"):
                try:
                    run = self.agents.check({"borrador": state.draft[:30000], "datos_del_caso": state.form_answers,
                                             "referencias_editoriales": [{"id": item["id"], "revision_id": item["revision_id"],
                                                                          "scope": item["scope"], "title": item["title"],
                                                                          "differences": item["differences"], "defects": item["defectos_detectados"]}
                                                                         for item in current_references],
                                             "contraste_normativo": report.normative_status})
                    self._record_llm(state, "verification", run)
                    for item in run.output.findings:
                        excerpt = item.draft_excerpt.strip()
                        if len(excerpt) < 6 or excerpt not in state.draft:
                            state.add_event({"type": "verification_invalid_evidence", "category": item.category})
                            continue
                        identifier = sha256(f"context|{item.category}|{excerpt}".encode()).hexdigest()[:12]
                        report.findings.append(Finding(id=identifier, category=item.category, severity=item.severity,
                                                       location=f"carácter {state.draft.index(excerpt)}", explanation=item.explanation,
                                                       evidence=[Evidence(source_kind="draft", source_id="current_draft",
                                                                          location=f"carácter {state.draft.index(excerpt)}", excerpt=excerpt)],
                                                       action=item.action, needs_document=item.needs_document))
                    report.pending_facts.extend(run.output.missing_facts)
                    report.context_status = "complete"
                    if any(item.severity == "critical" and not item.resolved for item in report.findings):
                        report.status = "con_observaciones"
                        report.summary = "Con observaciones"
                    elif report.pending_facts and report.status == "sin_observaciones_materiales":
                        report.status = "informacion_insuficiente"
                        report.summary = "Información insuficiente"
                    report.duration_ms += run.duration_ms
                except Exception as exc:
                    report.context_status = "unavailable"
                    report.status = "informacion_insuficiente"
                    report.summary = "Información insuficiente: la comprobación contextual no terminó"
                    state.add_event({"type": "verification_context_error", "message": str(exc)[:200]})
            state.verification = report.model_dump()
            state.verified_draft_hash = report.draft_hash
            state.add_event({"type": "verification", "status": report.status, "duration_ms": report.duration_ms,
                             "findings": len(report.findings)})
            self.storage.save(state)
            return state

    def create_draft_check(self, draft: str, context: str, facts: dict, owner_user_id: int | None = None) -> ConversationState:
        if not isinstance(draft, str) or not draft.strip() or len(draft) > 200_000:
            raise OperationError("validation_error", "Debe proporcionar un borrador de hasta 200.000 caracteres")
        request_text = (context or "Comprobar resolución redactada")[:2000]
        state = ConversationState(original_request=request_text, owner_user_id=owner_user_id)
        state.transition(Stage.SEARCHING_EXAMPLES)
        if self.example_catalog:
            # Administrative headings, dates and numeral labels in the full draft
            # overwhelm the legal problem in a lexical query. Prefer the user's
            # stated object; fall back to the draft only if no object was given.
            search_text = context.strip() if context and context.strip() else draft
            found = self.example_catalog.search(search_text, 20)
            state.example_references = found["results"][:5]
            state.example_search_status = found["status"]
            state.example_corpus_version = found["corpus_version"]
        state.transition(Stage.COLLECTING_INFO)
        state.transition(Stage.DRAFT_REVIEW)
        state.form_answers = facts if isinstance(facts, dict) else {}
        state.draft = draft
        state.last_debug["message"] = "Borrador recibido para comparación y comprobación."
        self.storage.save(state)
        return self.check_draft(state.id)

    def run_skill(self, conversation_id: str, key: str, answers: dict[str, Any] | None = None) -> ConversationState:
        with self._lock:
            state = self._get(conversation_id)
            if state.stage != Stage.APPROVED or not state.approved or not state.draft:
                raise InvalidTransition("Las skills solo pueden ejecutarse tras aprobar el borrador")
            skill = self.skills.get(key)
            if not skill:
                raise NotFoundError("Skill no encontrada")
            rounds = state.skill_input_rounds.get(key, 0)
            existing = state.skill_results.get(key)
            additional = None
            if answers is not None:
                if rounds != 1 or not existing or existing.get("status") != "needs_input":
                    raise InvalidTransition("Esta skill no espera respuestas")
                additional = validate_form_answers(DynamicForm.model_validate(existing["questions"]), answers)
            elif rounds >= 1 and existing and existing.get("status") == "needs_input":
                raise OperationError("validation_error", "La skill requiere responder su formulario")
            before = state.stage
            try:
                run = skill.run(
                    self.agents,
                    {
                        "borrador_aprobado": state.draft,
                        "datos_relevantes": state.form_answers,
                        "revisiones_aplicadas": state.revision_notes,
                        "regla_de_precedencia": (
                            "El borrador aprobado ya incorpora las revisiones y prevalece ante cualquier dato anterior contradictorio."
                        ),
                        "respuestas_adicionales": additional,
                    },
                )
                self._record_llm(state, key, run)
                output: SkillOutput = run.output
                if output.status == "needs_input":
                    if rounds >= 1:
                        output = output.model_copy(
                            update={
                                "status": "complete",
                                "summary": (
                                    f"{output.summary} Analisis finalizado tras la unica ronda adicional; "
                                    "las incertidumbres restantes requieren revision humana."
                                ),
                                "questions": None,
                            }
                        )
                    else:
                        state.skill_input_rounds[key] = 1
                state.skill_results[key] = output.model_dump()
                self._set_debug(state, before, [])
                state.last_debug["message"] = output.summary
                self.storage.save(state)
                return state
            except OperationError:
                self.storage.save(state)
                raise
            except Exception as exc:
                self.storage.save(state)
                raise OperationError("llm_provider_error", str(exc), True) from exc

    def get(self, conversation_id: str) -> ConversationState:
        state = self._get(conversation_id)
        # Correct untouched greetings created by older versions of the intake.
        reply = introductory_response(state.original_request)
        if (reply and state.stage == Stage.COLLECTING_INFO and not state.form_history
                and not state.form_answers and not state.draft):
            state = ConversationState(id=state.id, owner_user_id=state.owner_user_id,
                                      original_request=state.original_request, created_at=state.created_at,
                                      events=state.events)
            state.add_event({"type": "intro_corrected", "from": Stage.COLLECTING_INFO.value, "to": Stage.NEW.value})
            return self._respond_to_intro(state, state.original_request, reply)
        return state

    def skill_metadata(self) -> list[dict[str, str]]:
        return [skill.metadata() for skill in self.skills.values()]
