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
    "BACKUP_REQUIRE_ENCRYPTION",
    "BACKUP_AGE_RECIPIENT",
    "schemaVersion\": 2",
    "MIN_LOCAL_BACKUP_SETS",
    "retention_pruned_backup_set",
    "manifest_",
    "sha256sum",
)
require(
    "deploy/backup/backup-runner.sh",
    "BACKUP_REQUIRE_OFFSITE",
    "BACKUP_REQUIRE_IMMUTABLE_REMOTE",
    "BACKUP_IMMUTABLE_REMOTE_CONFIRMED",
    "BACKUP_REQUIRE_ENCRYPTION",
    "BACKUP_AGE_RECIPIENT",
    "RCLONE_CONFIG",
    " cat ",
    "manifest is copied last",
    "flock",
)
require(
    "deploy/backup/restore-drill.sh",
    "restore drill refuses non-local",
    "BACKUP_AGE_IDENTITY_FILE",
    "ALLOW_LEGACY_UNENCRYPTED_RESTORE",
    "manifest checksum sidecar",
    "MAX_BACKUP_AGE_SECONDS",
    "MAX_RESTORE_SECONDS",
    "manifest_sha256",
    "upload_entry_count",
)
require(
    "deploy/systemd/school-lifecycle-backup.service",
    "REQUIRE_UPLOAD_BACKUP=1",
    "BACKUP_REQUIRE_OFFSITE=true",
    "BACKUP_REQUIRE_IMMUTABLE_REMOTE=true",
    "BACKUP_REQUIRE_ENCRYPTION=true",
    "ProtectHome=true",
    "RCLONE_CONFIG=/etc/school-lifecycle/rclone.conf",
)
require(
    "deploy/systemd/school-lifecycle-backup.timer",
    "OnCalendar=*-*-* 01,07,13,19:15:00",
    "Persistent=true",
    "AccuracySec=1s",
)
require(
    "deploy/env/backup.env.example",
    "MIN_LOCAL_BACKUP_SETS=8",
    "BACKUP_REQUIRE_ENCRYPTION=true",
    "BACKUP_AGE_RECIPIENT=",
    "MAX_BACKUP_AGE_SECONDS=21600",
    "MAX_RESTORE_SECONDS=7200",
    "BACKUP_IMMUTABLE_REMOTE_CONFIRMED=false",
)
require(
    ".github/workflows/data-governance-contracts.yml",
    "age-keygen",
    "BACKUP_REQUIRE_ENCRYPTION: 'true'",
    "BACKUP_AGE_IDENTITY_FILE",
    "Prove encryption fails closed",
    "sha256sum -c",
)
require(
    ".github/workflows/backup-restore-drill.yml",
    "age-keygen",
    "BACKUP_REQUIRE_ENCRYPTION: 'true'",
    "BACKUP_AGE_IDENTITY_FILE",
    "Verify only encrypted data artifacts were committed offsite",
)
require(
    ".github/dependabot.yml",
    "package-ecosystem: pip",
    "package-ecosystem: npm",
    "package-ecosystem: github-actions",
    "timezone: Asia/Singapore",
)

print("data governance contracts: PASS")
