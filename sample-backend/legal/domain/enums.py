from enum import Enum


class TaskFamily(str, Enum):
    LEGAL_QUESTION = "legal_question"
    RESOLUTION_DRAFTING = "resolution_drafting"
    DOCUMENT_REVIEW = "document_review"
    NORMATIVE_RESEARCH = "normative_research"
    GENERAL_CONVERSATION = "general_conversation"


class RiskTier(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class LegalCaseState(str, Enum):
    NEW = "new"
    INTENT_COMPILED = "intent_compiled"
    WORKFLOW_SELECTED = "workflow_selected"
    SEARCHING_PRECEDENTS = "searching_precedents"
    PRECEDENT_SELECTED = "precedent_selected"
    FORM_READY = "form_ready"
    AWAITING_FACTS = "awaiting_facts"
    VALIDATING_FACTS = "validating_facts"
    FACTS_COMPLETE = "facts_complete"
    LEGAL_ISSUES_PLANNED = "legal_issues_planned"
    RESEARCHING = "researching"
    VERIFYING_EVIDENCE = "verifying_evidence"
    EVIDENCE_READY = "evidence_ready"
    DRAFTING = "drafting"
    DRAFT_READY = "draft_ready"
    COMPLIANCE_REVIEW = "compliance_review"
    CITATION_REVIEW = "citation_review"
    READY_FOR_HUMAN_REVIEW = "ready_for_human_review"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    FAILED = "failed"


class CaseCommandType(str, Enum):
    CREATE_LEGAL_CASE = "create_legal_case"
    START_LEGAL_WORKFLOW = "start_legal_workflow"
    SUBMIT_INITIAL_REQUEST = "submit_initial_request"
    SUBMIT_FORM_ANSWERS = "submit_form_answers"
    CONFIRM_FACTS = "confirm_facts"
    RETRY_WORKFLOW_STEP = "retry_workflow_step"
    CANCEL_WORKFLOW = "cancel_workflow"
    RESUME_BLOCKED_CASE = "resume_blocked_case"
    REQUEST_DRAFT = "request_draft"
    SUBMIT_HUMAN_REVIEW = "submit_human_review"
    APPROVE_MEMORY_PROPOSAL = "approve_memory_proposal"
    REJECT_MEMORY_PROPOSAL = "reject_memory_proposal"


class CaseEventType(str, Enum):
    CASE_CREATED = "case.created"
    INTENT_COMPILED = "intent.compiled"
    INTAKE_INTENT_PERSISTED = "intake.intent.persisted"
    INTAKE_PLANNING_STARTED = "intake.planning.started"
    INTAKE_QUESTIONS_COMPILED = "intake.questions.compiled"
    INTAKE_WAITING_USER = "intake.waiting_user"
    INTAKE_ANSWERS_SUBMITTED = "intake.answers.submitted"
    INTAKE_ANSWERS_VALIDATED = "intake.answers.validated"
    INTAKE_RESUMED = "intake.resumed"
    INTAKE_FAILED = "intake.failed"
    WORKFLOW_SELECTED = "workflow.selected"
    PRECEDENT_SEARCH_STARTED = "precedent.search.started"
    PRECEDENT_SEARCH_COMPLETED = "precedent.search.completed"
    PRECEDENT_SELECTED = "precedent.selected"
    PRECEDENT_FALLBACK_SELECTED = "precedent.fallback.selected"
    PRECEDENT_NOT_FOUND = "precedent.not_found"
    INTAKE_QUESTION_REQUESTED = "intake.question.requested"
    INTAKE_QUESTION_PARTIAL = "intake.question.partial"
    INTAKE_QUESTION_ANSWERED = "intake.question.answered"
    FORM_CREATED = "form.created"
    HUMAN_INPUT_REQUIRED = "human_input.required"
    FORM_ANSWERS_SUBMITTED = "form.answers.submitted"
    FACTS_VALIDATED = "facts.validated"
    FACTS_REJECTED = "facts.rejected"
    LEGAL_ISSUES_PLANNED = "legal_issues.planned"
    RESEARCH_STARTED = "research.started"
    AUTHORITY_RETRIEVED = "authority.retrieved"
    AUTHORITY_VERIFIED = "authority.verified"
    AUTHORITY_REJECTED = "authority.rejected"
    AUTHORITY_CONFLICT_DETECTED = "authority.conflict_detected"
    EVIDENCE_READY = "evidence.ready"
    DRAFT_CREATED = "draft.created"
    DRAFT_VALIDATION_FAILED = "draft.validation_failed"
    COMPLIANCE_COMPLETED = "compliance.completed"
    CITATION_GATE_COMPLETED = "citation_gate.completed"
    HUMAN_REVIEW_REQUIRED = "human_review.required"
    HUMAN_REVIEW_COMPLETED = "human_review.completed"
    CASE_BLOCKED = "case.blocked"
    CASE_COMPLETED = "case.completed"
    CASE_CANCELLED = "case.cancelled"
    CASE_FAILED = "case.failed"
    WORKFLOW_RUN_STARTED = "workflow.run.started"
    WORKFLOW_RUN_COMPLETED = "workflow.run.completed"
    WORKFLOW_RUN_RETRIED = "workflow.run.retried"
    WORKFLOW_STEP_COMPLETED = "workflow.step.completed"
    MEMORY_PROPOSAL_APPROVED = "memory.proposal.approved"
    MEMORY_PROPOSAL_REJECTED = "memory.proposal.rejected"


class WorkflowRunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class WorkflowStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CommandStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class OutboxStatus(str, Enum):
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
