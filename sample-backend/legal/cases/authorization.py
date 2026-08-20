from uuid import UUID

from legal.domain.errors import CaseNotFoundError
from legal.infrastructure.models import LegalCaseRecord


def require_owned_case(case_id: UUID | str, owner_user_id: int) -> LegalCaseRecord:
    record = LegalCaseRecord.query.filter_by(
        id=str(case_id), owner_user_id=owner_user_id
    ).first()
    if record is None:
        raise CaseNotFoundError("Legal case not found")
    return record
