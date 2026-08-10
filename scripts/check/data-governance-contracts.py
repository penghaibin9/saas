#!/usr/bin/env python3
from __future__ import annotations

import subprocess
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


def forbid(path: str, *needles: str) -> None:
    value = text(path)
    present = [needle for needle in needles if needle in value]
    if present:
        raise SystemExit(f"{path} contains forbidden governance contracts: {present}")


def reject_tracked_runtime_secrets() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    bad = []
    for item in tracked:
        name = Path(item).name
        if name == "rclone.conf" or name.endswith(".env"):
            bad.append(item)
    if bad:
        raise SystemExit(
            "runtime secret/config files must not be tracked: " + ", ".join(sorted(bad))
        )


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
    "--no-tablespaces",
    "--set-gtid-purged=OFF",
)
forbid(
    "deploy/backup/backup-mysql.sh",
    "--source-data",
    "--master-data",
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
    ".gitignore",
    "*.env",
    "rclone.conf",
)

# Active production/operations documents must point to the same governed recovery model.
production_docs = [
    "docs/07-部署运维交付与商业化/deploy/生产上线runbook.md",
    "docs/07-部署运维交付与商业化/deploy/学校试点部署Runbook.md",
    "docs/07-部署运维交付与商业化/deploy/10-2U4G非容器部署准备与执行手册.md",
    "docs/07-部署运维交付与商业化/ops/备份恢复演练手册.md",
    "docs/07-部署运维交付与商业化/ops/10校SaaS上线性能与容灾基线.md",
]
for doc in production_docs:
    require(doc, "deploy/README-data-governance.md")

require(
    "docs/07-部署运维交付与商业化/deploy/生产上线runbook.md",
    "RPO ≤ 6 小时",
    "school-lifecycle-backup-watchdog.timer",
)
forbid(
    "docs/07-部署运维交付与商业化/deploy/生产上线runbook.md",
    "crontab 每天 02:00",
)
require(
    "docs/07-部署运维交付与商业化/deploy/学校试点部署Runbook.md",
    "school-lifecycle-backup.service/.timer",
    "每 6 小时一个恢复点",
)
forbid(
    "docs/07-部署运维交付与商业化/deploy/学校试点部署Runbook.md",
    "backup-mysql.sh` + crontab 02:00",
)
require(
    "docs/07-部署运维交付与商业化/deploy/10-2U4G非容器部署准备与执行手册.md",
    "RPO ≤ 6 小时",
    "school-lifecycle-backup-watchdog.timer",
)
forbid(
    "docs/07-部署运维交付与商业化/deploy/10-2U4G非容器部署准备与执行手册.md",
    "每日 02:00 备份 MySQL 与 uploads",
)
require(
    "docs/07-部署运维交付与商业化/ops/备份恢复演练手册.md",
    "RPO ≤ 6 小时",
    "manifest",
    "restore-drill.sh",
)
forbid(
    "docs/07-部署运维交付与商业化/ops/备份恢复演练手册.md",
    "restore-mysql.sh",
)
require(
    "docs/07-部署运维交付与商业化/ops/10校SaaS上线性能与容灾基线.md",
    "RPO ≤ 6 小时",
    "不承诺 5 分钟 PITR",
    "school-lifecycle-backup-watchdog.timer",
)
forbid(
    "docs/07-部署运维交付与商业化/ops/10校SaaS上线性能与容灾基线.md",
    "RPO 不超过 5 分钟",
    "CHANGE REPLICATION SOURCE TO",
)

require(
    ".github/workflows/data-governance-contracts.yml",
    "**/*.env",
    "**/rclone.conf",
    "生产上线runbook.md",
    "10校SaaS上线性能与容灾基线.md",
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

reject_tracked_runtime_secrets()
print("data governance contracts: PASS")
