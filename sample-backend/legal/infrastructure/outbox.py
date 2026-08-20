from datetime import datetime, timedelta
from uuid import UUID

from app.extensions import db
from legal.domain.enums import OutboxStatus
from legal.infrastructure.models import OutboxEventRecord
from legal.workflows.dispatcher import WorkflowDispatcher


class OutboxPublisher:
    def __init__(self, dispatcher: WorkflowDispatcher, max_attempts: int = 5):
        self.dispatcher = dispatcher
        self.max_attempts = max_attempts

    def publish_command(self, command_id: UUID) -> bool:
        row = OutboxEventRecord.query.filter_by(
            topic="legal.workflow.command",
            aggregate_id=str(command_id),
        ).first()
        if row is None or row.status == OutboxStatus.PUBLISHED.value:
            return True
        try:
            self.dispatcher.dispatch(command_id)
            row.status = OutboxStatus.PUBLISHED.value
            row.published_at = datetime.utcnow()
            row.attempts += 1
            row.last_error = None
            db.session.commit()
            return True
        except Exception as exc:
            db.session.rollback()
            row = db.session.get(OutboxEventRecord, row.id)
            row.attempts += 1
            row.last_error = str(exc)[:2000]
            row.status = (
                OutboxStatus.FAILED.value
                if row.attempts >= self.max_attempts
                else OutboxStatus.PENDING.value
            )
            row.available_at = datetime.utcnow() + timedelta(seconds=min(2 ** row.attempts, 60))
            db.session.commit()
            return False

    def publish_pending(self, limit: int = 100) -> int:
        rows = (
            OutboxEventRecord.query.filter(
                OutboxEventRecord.topic == "legal.workflow.command",
                OutboxEventRecord.status == OutboxStatus.PENDING.value,
                OutboxEventRecord.available_at <= datetime.utcnow(),
            )
            .order_by(OutboxEventRecord.created_at.asc())
            .limit(limit)
            .all()
        )
        published = 0
        for row in rows:
            if self.publish_command(UUID(row.aggregate_id)):
                published += 1
        return published
