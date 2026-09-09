"""分阶段建设标准沙箱学校：阶段 7，统一消息与学生待办。"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import func, select

sys.path[:0] = [str(Path(__file__).resolve().parent), str(Path(__file__).resolve().parent.parent)]


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--confirm", action="store_true")
    args = parser.parse_args()

    from app.core.tenant_identity import SANDBOX_SCHOOL, TRIAL_SCHOOL
    from app.db.session import db_enabled, get_sessionmaker
    from app.models import Tenant, UnifiedMessage, UnifiedTodo
    from app.services.sandbox_school_domain_seed import _roster, _seed_messages_and_todos
    from app.services.sandbox_school_domain_validation import validate_core_domain_facts_20k

    if not db_enabled():
        return 2
    tenant_id = SANDBOX_SCHOOL.tenant_id
    db = get_sessionmaker()()
    try:
        old_tenant = db.get(Tenant, TRIAL_SCHOOL.tenant_id)
        new_tenant = db.get(Tenant, tenant_id)
        if old_tenant is None or old_tenant.tenant_code != TRIAL_SCHOOL.tenant_code:
            return 3
        if new_tenant is None or new_tenant.tenant_code != SANDBOX_SCHOOL.tenant_code:
            return 4
        messages = int(db.scalar(select(func.count()).select_from(UnifiedMessage).where(
            UnifiedMessage.tenant_id == tenant_id,
            UnifiedMessage.is_deleted.is_(False),
        )) or 0)
        student_todos = int(db.scalar(select(func.count()).select_from(UnifiedTodo).where(
            UnifiedTodo.tenant_id == tenant_id,
            UnifiedTodo.source_biz_type == "STUDENT_TASK",
            UnifiedTodo.is_deleted.is_(False),
        )) or 0)
        current = {"messages": messages, "studentTodos": student_todos}
        print(json.dumps({"tenantId": str(tenant_id), "current": current}, ensure_ascii=False))
        if args.dry_run:
            return 0 if current in ({"messages": 0, "studentTodos": 0}, {"messages": 20000, "studentTodos": 4263}) else 5
        if current == {"messages": 20000, "studentTodos": 4263}:
            print(json.dumps({"resumed": True, "acceptance": validate_core_domain_facts_20k(db, tenant_id)}, ensure_ascii=False, indent=2))
            return 0
        if current != {"messages": 0, "studentTodos": 0}:
            return 5
        roster = _roster(db, tenant_id)
        if len(roster) != 20000:
            raise RuntimeError(f"学生主档范围异常: {len(roster)}")
        result = _seed_messages_and_todos(db, tenant_id, roster)
        acceptance = validate_core_domain_facts_20k(db, tenant_id)
        print(json.dumps({"result": result, "acceptance": acceptance}, ensure_ascii=False, indent=2))
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
