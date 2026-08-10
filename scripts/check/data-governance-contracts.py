#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def text(path: str) -> str:
    value = (ROOT / path).read_text(encoding="utf-8")
    if not value.strip():
        raise SystemExit(f"empty governance file: {path}")
    return value


def require(path: str, *needles: str) -> None:
    value = text(path)
    missing = [needle for needle in needles if needle not in value]
    if missing:
        raise SystemExit(f"{path} missing governance contracts: {missing}")


require(
    "deploy/backup/backup-mysql.sh",
    "REQUIRE_UPLOAD_BACKUP",
    "MIN_LOCAL_BACKUP_SETS",
    "cleanup_incomplete",
    "committed=1",
    "unsafe upload entry is not allowed",
    "retention_pruned_backup_set",
    "manifest_",
    "schemaVersion",
    "sha256sum",
)
require(
    "deploy/backup/backup-runner.sh",
    "BACKUP_REQUIRE_OFFSITE",
    "BACKUP_REQUIRE_IMMUTABLE_REMOTE",
    "BACKUP_IMMUTABLE_REMOTE_CONFIRMED",
    "RCLONE_CONFIG",
    " cat ",
    "manifest is copied last",
    "flock",
)
require(
    "deploy/backup/backup-watchdog.sh",
    "MAX_BACKUP_AGE_SECONDS",
    "no_completed_backup_manifest",
    "backup_stale_age_",
    "remote_manifest_hash_mismatch",
    "backup_watchdog=PASS",
)
require(
    "deploy/backup/restore-drill.sh",
    "restore drill refuses non-local",
    "manifest checksum sidecar",
    "unsafe upload archive member path",
    "unsafe upload archive member type",
    "--no-same-owner",
    "manifest_sha256",
    "MAX_BACKUP_AGE_SECONDS",
    "MAX_RESTORE_SECONDS",
    "upload_entry_count",
)
require(
    "deploy/systemd/school-lifecycle-backup.service",
    "REQUIRE_UPLOAD_BACKUP=1",
    "BACKUP_REQUIRE_OFFSITE=true",
    "BACKUP_REQUIRE_IMMUTABLE_REMOTE=true",
    "ProtectHome=true",
    "RCLONE_CONFIG=/etc/school-lifecycle/rclone.conf",
    "TimeoutStartSec=5h",
)
require(
    "deploy/systemd/school-lifecycle-backup.timer",
    "OnCalendar=*-*-* 01,07,13,19:15:00",
    "Persistent=true",
    "AccuracySec=1s",
)
require(
    "deploy/systemd/school-lifecycle-backup-watchdog.service",
    "backup-watchdog.sh",
    "BACKUP_REQUIRE_OFFSITE=true",
    "ProtectHome=true",
    "ReadOnlyPaths=/var/lib/school-lifecycle-backup",
    "TimeoutStartSec=10min",
)
require(
    "deploy/systemd/school-lifecycle-backup-watchdog.timer",
    "OnCalendar=hourly",
    "Persistent=true",
    "school-lifecycle-backup-watchdog.service",
)
require(
    "deploy/env/backup.env.example",
    "MIN_LOCAL_BACKUP_SETS=8",
    "MAX_BACKUP_AGE_SECONDS=21600",
    "MAX_RESTORE_SECONDS=7200",
    "BACKUP_IMMUTABLE_REMOTE_CONFIRMED=false",
)
require(
    "deploy/README-data-governance.md",
    "FIELD_ENCRYPTION_KEY",
    "FIELD_ENCRYPTION_PREVIOUS_KEYS",
    "outside the application server",
    "systemd after 5 hours",
    "10-minute systemd timeout",
)
require(
    ".github/workflows/data-governance-contracts.yml",
    "Prove uploads fail closed",
    "failed backup left orphan files",
    "Prove unsafe upload entries are rejected",
    "Prove local-only backup is rejected",
    "Verify backup watchdog sees healthy committed set",
    "Prove watchdog detects missing remote commit marker",
    "manifest_sha256",
    "sha256sum -c",
)
require(
    ".github/workflows/backup-restore-drill.yml",
    "Stage restore only from offsite objects",
    "Verify recovery evidence integrity",
    "manifest_sha256",
)
require(
    ".github/dependabot.yml",
    "package-ecosystem: pip",
    "package-ecosystem: npm",
    "package-ecosystem: github-actions",
    "timezone: Asia/Singapore",
)

print("data governance contracts: PASS")
