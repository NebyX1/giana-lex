from uuid import UUID

from legal.cases.repository import LegalCaseRepository


class LegalQueryService:
    def __init__(self, repository: LegalCaseRepository | None = None):
        self.repository = repository or LegalCaseRepository()

    def get_case(self, case_id: UUID, owner_user_id: int):
        return self.repository.get(case_id, owner_user_id)

    def list_cases(self, owner_user_id: int, limit: int = 100):
        return self.repository.list_for_owner(owner_user_id, limit)

    def get_snapshot(self, case_id: UUID, owner_user_id: int):
        return self.repository.get_snapshot(case_id, owner_user_id)

    def list_events(self, case_id: UUID, owner_user_id: int, after: int = 0, limit: int = 500):
        return self.repository.list_events(case_id, owner_user_id, after, limit)
