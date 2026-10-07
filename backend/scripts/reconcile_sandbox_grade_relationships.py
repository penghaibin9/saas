"""Apply sandbox historical-grade course, term and provenance reconciliation."""
from __future__ import annotations

import json

from app.core.tenant_identity import SANDBOX_SCHOOL
from app.db.session import get_sessionmaker
from app.services.sandbox_school_grade_relationship_reconcile import (
    reconcile_sandbox_grade_relationships,
)


def main() -> None:
    with get_sessionmaker()() as db:
        result = reconcile_sandbox_grade_relationships(db, int(SANDBOX_SCHOOL.tenant_id))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
