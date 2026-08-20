import re
import unicodedata
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class CaseConversationIntent(str, Enum):
    SHOW_RESULT = "SHOW_RESULT"
    SHOW_STATUS = "SHOW_STATUS"
    CONTINUE = "CONTINUE"
    SHOW_PENDING_ACTION = "SHOW_PENDING_ACTION"
    OPEN_REVIEW = "OPEN_REVIEW"
    EXPORT_REQUEST = "EXPORT_REQUEST"
    GENERAL_LEGAL_CHAT = "GENERAL_LEGAL_CHAT"


class CaseConversationDecision(BaseModel):
    intent: CaseConversationIntent
    text: str
    action: Literal["focus_draft", "focus_review", "focus_form", "focus_blocker"]


def normalize_phrase(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.lower())
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", without_accents).strip()


class CaseConversationRouter:
    _PATTERNS = (
        (CaseConversationIntent.SHOW_RESULT, re.compile(
            r"^(?:dame|muestra(?:me)?|mostra(?:me)?|mostrar|quiero ver|ver) (?:el )?(?:resultado|borrador|documento)(?: de (?:tu|su|este) trabajo)?$"
        )),
        (CaseConversationIntent.SHOW_STATUS, re.compile(
            r"^(?:estado|como va|cual es el estado|dame el estado|ver el estado|muestra(?:me)? el estado|mostra(?:me)? el estado|termino|ya termino|esta trabajando|que esta haciendo)(?: el sistema| del expediente)?$"
        )),
        (CaseConversationIntent.CONTINUE, re.compile(
            r"^(?:si )?(?:continua|continuar|continuemos|segui|sigue|procede|avanza)(?: con el expediente)?$"
        )),
        (CaseConversationIntent.SHOW_PENDING_ACTION, re.compile(
            r"^(?:que falta|dime que falta|que queda pendiente|cual es el proximo paso|muestra(?:me)? las acciones pendientes|mostra(?:me)? las acciones pendientes)$"
        )),
        (CaseConversationIntent.OPEN_REVIEW, re.compile(
            r"^(?:abrir|abre|mostrar|muestra|ir a|quiero abrir) (?:la )?(?:revision|revision humana)$|^(?:quiero )?revisar (?:el )?borrador$"
        )),
        (CaseConversationIntent.EXPORT_REQUEST, re.compile(
            r"^(?:quiero )?(?:exporta|exportar|genera|generar|descarga|descargar)(?: el| la| a| en)? (?:docx|documento|borrador)(?: en docx)?$"
        )),
    )

    def classify(self, content: str) -> CaseConversationIntent:
        phrase = normalize_phrase(content)
        for intent, pattern in self._PATTERNS:
            if pattern.fullmatch(phrase):
                return intent
        return CaseConversationIntent.GENERAL_LEGAL_CHAT

    def decide(
        self,
        content: str,
        *,
        state: str,
        has_draft: bool,
        has_open_review: bool,
        has_open_form: bool,
        draft_version: int | None = None,
        active_run_id: str | None = None,
        current_step: str | None = None,
    ) -> CaseConversationDecision | None:
        intent = self.classify(content)
        if intent == CaseConversationIntent.GENERAL_LEGAL_CHAT:
            return None
        action = self._action(state, has_draft, has_open_review, has_open_form)

        if intent == CaseConversationIntent.SHOW_RESULT:
            if state == "ready_for_human_review" and has_draft:
                text = (
                    "El borrador ya está generado y se encuentra disponible en el panel derecho. "
                    f"Versión: {draft_version or 'actual'}. Estado: listo para revisión humana."
                )
                action = "focus_draft"
            elif state == "completed" and has_draft:
                text = "El borrador está generado y el expediente está completado."
                action = "focus_draft"
            elif state == "blocked":
                text = "El expediente está bloqueado. Revise el motivo del bloqueo antes de usar un resultado."
                action = "focus_blocker"
            elif has_draft:
                text = "Ya existe un borrador. Puede abrirlo para consultar su versión actual."
                action = "focus_draft"
            else:
                text = "Todavía no hay un borrador generado. Complete la acción pendiente del expediente."
        elif intent == CaseConversationIntent.SHOW_STATUS:
            if active_run_id:
                text = f"Giana está trabajando actualmente en: {(current_step or 'workflow jurídico').replace('_', ' ')}."
            elif state == "ready_for_human_review" and has_open_review:
                text = "La automatización terminó. El expediente está esperando revisión humana."
                action = "focus_review"
            elif state == "completed":
                text = "El expediente está finalizado."
                action = "focus_draft" if has_draft else action
            else:
                text = f"El estado actual del expediente es {state.replace('_', ' ')}."
        elif intent == CaseConversationIntent.CONTINUE:
            text = (
                f"Giana ya está trabajando en: {(current_step or 'workflow jurídico').replace('_', ' ')}."
                if active_run_id else self._pending_text(state)
            )
        elif intent == CaseConversationIntent.SHOW_PENDING_ACTION:
            text = self._pending_text(state)
        elif intent == CaseConversationIntent.OPEN_REVIEW:
            if state == "ready_for_human_review" and has_draft and has_open_review:
                text = "La revisión humana está disponible para el borrador actual."
                action = "focus_review"
            else:
                text = "La revisión humana todavía no está disponible para el estado actual."
        else:
            if state in {"ready_for_human_review", "completed"} and has_draft:
                text = "Abra el borrador para solicitar la exportación DOCX; el servidor verificará nuevamente todos los gates."
                action = "focus_draft"
            else:
                text = "La exportación DOCX no está habilitada hasta que exista un borrador que supere los gates."

        return CaseConversationDecision(intent=intent, text=text, action=action)

    @staticmethod
    def _action(state: str, has_draft: bool, has_open_review: bool, has_open_form: bool):
        if state in {"blocked", "failed"}:
            return "focus_blocker"
        if state == "ready_for_human_review" and has_open_review:
            return "focus_review"
        if has_open_form or state in {"form_ready", "awaiting_facts", "validating_facts"}:
            return "focus_form"
        if has_draft:
            return "focus_draft"
        return "focus_form"

    @staticmethod
    def _pending_text(state: str) -> str:
        if state == "ready_for_human_review":
            return "La acción pendiente es revisar el borrador actual."
        if state in {"form_ready", "awaiting_facts"}:
            return "La acción pendiente es completar el formulario del expediente."
        if state == "validating_facts":
            return "La acción pendiente es confirmar los hechos registrados."
        if state == "blocked":
            return "El expediente requiere resolver el bloqueo indicado antes de continuar."
        if state == "failed":
            return "La ejecución falló. Revise el error antes de reintentar."
        if state == "completed":
            return "El expediente está completado y no tiene una acción de workflow pendiente."
        return "No hay una acción humana pendiente; consulte el estado para ver el avance actual."
