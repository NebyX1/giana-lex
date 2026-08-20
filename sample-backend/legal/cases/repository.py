from uuid import UUID, uuid4

from sqlalchemy import update

from app.extensions import db
from legal.cases.reducer import reduce_case_event
from legal.domain.enums import CaseEventType, LegalCaseState, RiskTier, TaskFamily
from legal.domain.errors import CaseNotFoundError, ConcurrentCaseUpdateError
from legal.domain.events import NewCaseEvent
from legal.domain.models import CaseEvent, CaseEventPayload, CaseSnapshot, LegalCase
from legal.infrastructure.models import (
    CaseEventRecord,
    CaseSnapshotRecord,
    LegalCaseRecord,
)


def _as_uuid(value: str | None) -> UUID | None:
    return UUID(value) if value else None


class LegalCaseRepository:
    def get_record(self, case_id: UUID | str, owner_user_id: int | None = None) -> LegalCaseRecord:
        query = LegalCaseRecord.query.filter_by(id=str(case_id))
        if owner_user_id is not None:
            query = query.filter_by(owner_user_id=owner_user_id)
        record = query.first()
        if record is None:
            raise CaseNotFoundError("Legal case not found")
        return record

    def get(self, case_id: UUID | str, owner_user_id: int | None = None) -> LegalCase:
        record = self.get_record(case_id, owner_user_id)
        return LegalCase(
            id=UUID(record.id),
            owner_user_id=record.owner_user_id,
            title=record.title,
            task_family=TaskFamily(record.task_family),
            resolution_type=record.resolution_type,
            jurisdiction=record.jurisdiction,
            risk_tier=RiskTier(record.risk_tier),
            workflow_pack_id=record.workflow_pack_id,
            workflow_pack_version=record.workflow_pack_version,
            state=LegalCaseState(record.state),
            state_version=record.state_version,
            active_run_id=_as_uuid(record.active_run_id),
            corpus_snapshot_id=_as_uuid(record.corpus_snapshot_id),
            created_at=record.created_at,
            updated_at=record.updated_at,
            completed_at=record.completed_at,
            cancelled_at=record.cancelled_at,
        )

    def list_for_owner(self, owner_user_id: int, limit: int = 100) -> list[LegalCase]:
        records = (
            LegalCaseRecord.query.filter_by(owner_user_id=owner_user_id)
            .order_by(LegalCaseRecord.updated_at.desc())
            .limit(limit)
            .all()
        )
        return [self.get(record.id, owner_user_id) for record in records]

    def get_snapshot(self, case_id: UUID | str, owner_user_id: int | None = None) -> CaseSnapshot:
        case = self.get_record(case_id, owner_user_id)
        record = db.session.get(CaseSnapshotRecord, case.id)
        if record is None:
            return CaseSnapshot(case_id=UUID(case.id))
        return CaseSnapshot.model_validate(record.snapshot_json)

    def append_event(
        self,
        case_id: UUID | str,
        expected_version: int,
        new_event: NewCaseEvent,
    ) -> CaseEvent:
        case = self.get_record(case_id)
        current = self.get_snapshot(case.id)
        if current.state_version != expected_version or case.state_version != expected_version:
            raise ConcurrentCaseUpdateError("Legal case version changed")

        validated_payload = new_event.validated_payload()
        event = CaseEvent(
            id=uuid4(),
            case_id=UUID(case.id),
            sequence_number=current.last_sequence_number + 1,
            event_type=new_event.event_type,
            schema_version=new_event.schema_version,
            command_id=new_event.command_id,
            run_id=new_event.run_id,
            actor_user_id=new_event.actor_user_id,
            payload=CaseEventPayload.model_validate(validated_payload.model_dump()),
            occurred_at=new_event.occurred_at,
        )
        snapshot = reduce_case_event(current, event)
        result = db.session.execute(
            update(LegalCaseRecord)
            .where(
                LegalCaseRecord.id == case.id,
                LegalCaseRecord.state_version == expected_version,
            )
            .values(
                state=snapshot.state.value,
                state_version=expected_version + 1,
                active_run_id=str(snapshot.active_run_id) if snapshot.active_run_id else None,
                completed_at=snapshot.completed_at,
                cancelled_at=snapshot.cancelled_at,
                updated_at=new_event.occurred_at,
            )
        )
        if result.rowcount != 1:
            raise ConcurrentCaseUpdateError("Legal case update lost an optimistic lock")

        db.session.add(
            CaseEventRecord(
                id=str(event.id),
                case_id=case.id,
                sequence_number=event.sequence_number,
                event_type=event.event_type.value,
                schema_version=event.schema_version,
                command_id=str(event.command_id),
                run_id=str(event.run_id) if event.run_id else None,
                actor_user_id=event.actor_user_id,
                payload_json=event.payload.model_dump(mode="json"),
                occurred_at=event.occurred_at,
            )
        )
        snapshot_record = db.session.get(CaseSnapshotRecord, case.id)
        snapshot_json = snapshot.model_dump(mode="json")
        if snapshot_record is None:
            db.session.add(
                CaseSnapshotRecord(
                    case_id=case.id,
                    snapshot_version=snapshot.state_version,
                    last_sequence_number=snapshot.last_sequence_number,
                    state=snapshot.state.value,
                    snapshot_json=snapshot_json,
                    updated_at=new_event.occurred_at,
                )
            )
        else:
            snapshot_record.snapshot_version = snapshot.state_version
            snapshot_record.last_sequence_number = snapshot.last_sequence_number
            snapshot_record.state = snapshot.state.value
            snapshot_record.snapshot_json = snapshot_json
            snapshot_record.updated_at = new_event.occurred_at

        return event

    def list_events(
        self,
        case_id: UUID | str,
        owner_user_id: int,
        after_sequence: int = 0,
        limit: int = 500,
    ) -> list[CaseEvent]:
        case = self.get_record(case_id, owner_user_id)
        rows = (
            CaseEventRecord.query.filter(
                CaseEventRecord.case_id == case.id,
                CaseEventRecord.sequence_number > max(after_sequence, 0),
            )
            .order_by(CaseEventRecord.sequence_number.asc())
            .limit(limit)
            .all()
        )
        return [
            CaseEvent(
                id=UUID(row.id),
                case_id=UUID(row.case_id),
                sequence_number=row.sequence_number,
                event_type=CaseEventType(row.event_type),
                schema_version=row.schema_version,
                command_id=UUID(row.command_id),
                run_id=_as_uuid(row.run_id),
                actor_user_id=row.actor_user_id,
                payload=CaseEventPayload.model_validate(row.payload_json),
                occurred_at=row.occurred_at,
            )
            for row in rows
        ]
