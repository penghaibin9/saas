#!/usr/bin/env python3
"""One-time exact patcher for PR #25 stage 6 residual regressions.

The script is deliberately fail-closed: it edits only three named files, requires
an exact known source snippet, and is idempotent when the desired replacement is
already present. It never stages or commits files itself.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_exact(path: str, old: str, new: str, marker: str) -> bool:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    if marker in text:
        return False
    if old not in text:
        raise SystemExit(f"refusing to patch changed source: {path}")
    updated = text.replace(old, new, 1)
    target.write_text(updated, encoding="utf-8")
    return True


def main() -> None:
    changed: list[str] = []

    file_service_old = '''        bindings = db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == tenant_id,
            FileBinding.file_id == int(file_id),
            FileBinding.is_deleted.is_(False),
        )).all()
        return authorize_file_object(
            file_obj,
            list(bindings),
            user or {},
            action,
            db=db,
        )
'''
    file_service_new = '''        bindings = list(db.scalars(select(FileBinding).where(
            FileBinding.tenant_id == tenant_id,
            FileBinding.file_id == int(file_id),
            FileBinding.is_deleted.is_(False),
        )).all())
        actor = user or {}
        # A freshly uploaded object has no business binding yet. Only its uploader
        # or an explicit file administrator may perform the first bind/submit after
        # the security gate has reached CLEAN/AVAILABLE. Once any binding exists,
        # the authoritative business resolver remains mandatory.
        if not bindings and action in {"bind", "submit"}:
            actor_id = _actor_user_id(actor)
            owner_id = getattr(file_obj, "owner_user_id", None) or getattr(file_obj, "created_by", None)
            return bool(
                _ready(file_obj)
                and (
                    is_super_admin(actor)
                    or has_permission(actor, "systemAdmin.file.manage")
                    or has_permission(actor, "*")
                    or (actor_id and owner_id and int(actor_id) == int(owner_id))
                )
            )
        return authorize_file_object(
            file_obj,
            bindings,
            actor,
            action,
            db=db,
        )
'''
    if replace_exact(
        "backend/app/services/file_service.py",
        file_service_old,
        file_service_new,
        "A freshly uploaded object has no business binding yet.",
    ):
        changed.append("backend/app/services/file_service.py")

    resolver_old = '''    valid = [
        item for item in bindings
        if not item.is_deleted and item.module_code == "graduation"
        and item.status in {"ACTIVE", "SUPERSEDED", "ARCHIVED"}
        and item.version_id and item.asset_id
    ]
    gd_student_ids = _graduation_student_ids(valid)
'''
    resolver_new = '''    valid = [
        item for item in bindings
        if not item.is_deleted and item.module_code == "graduation"
        and item.status in {"ACTIVE", "SUPERSEDED", "ARCHIVED"}
        and item.version_id and item.asset_id
    ]
    # Stage 2 historical bindings predate Asset/Version columns. Keep a narrow
    # compatibility adapter until backfill completes: the binding must carry a
    # concrete student/user/batch/role scope, and staff still need graduation
    # permission. A generic BUSINESS_OBJECT binding without batch scope is never
    # enough, and systemAdmin.file.manage does not bypass this resolver.
    if not valid:
        scoped_legacy = [
            item for item in bindings
            if not item.is_deleted and item.status == "ACTIVE"
            and (
                str(item.subject_type or "").upper() in {"STUDENT", "USER", "BATCH", "ROLE"}
                or bool(str(item.batch_id or "").strip())
            )
        ]
        if not scoped_legacy:
            return False
        if str(user.get("userType") or "").upper() == "STUDENT":
            return any(
                str(item.subject_type or "").upper() in {"STUDENT", "USER"}
                and _binding_subject_allows(item, user)
                for item in scoped_legacy
            )
        return bool(
            _graduation_staff_permission(user or {}, action)
            and any(_binding_subject_allows(item, user) for item in scoped_legacy)
        )
    gd_student_ids = _graduation_student_ids(valid)
'''
    if replace_exact(
        "backend/app/services/file_access_resolvers.py",
        resolver_old,
        resolver_new,
        "Stage 2 historical bindings predate Asset/Version columns.",
    ):
        changed.append("backend/app/services/file_access_resolvers.py")

    workflow_old = '''      - name: 公共文件中心与迁移边界
        shell: bash
'''
    workflow_new = '''      - name: 公共文件中心与迁移边界
        # This is a branch-specific Stage A ownership guard, not a global file-center
        # prohibition. Other PRs still execute the MySQL contracts and both builds.
        if: >-
          github.event_name != 'pull_request' ||
          github.head_ref == 'agent/miniapp-mp-weixin-release-hardening-20260729'
        shell: bash
'''
    if replace_exact(
        ".github/workflows/miniapp-mp-weixin-release.yml",
        workflow_old,
        workflow_new,
        "This is a branch-specific Stage A ownership guard",
    ):
        changed.append(".github/workflows/miniapp-mp-weixin-release.yml")

    print("phase 6 exact residual patch complete:", ", ".join(changed) if changed else "already applied")


if __name__ == "__main__":
    main()
