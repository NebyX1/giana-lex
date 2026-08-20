import json

from flask import g, request

from .extensions import db
from .models import AuditEvent


def record_event(
    event: str,
    status: str,
    user_id: int | None = None,
    *,
    subject_type: str | None = None,
    subject_id: str | int | None = None,
    details: dict | None = None,
) -> None:
    db.session.add(
        AuditEvent(
            user_id=user_id,
            event=event,
            status=status,
            subject_type=subject_type,
            subject_id=str(subject_id) if subject_id is not None else None,
            details=json.dumps(details, ensure_ascii=False, default=str) if details else None,
            request_id=getattr(g, "request_id", None),
            ip_address=request.remote_addr,
        )
    )
