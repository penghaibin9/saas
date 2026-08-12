from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_scheduled_backup_is_suppressed_during_release_quiesce():
    service = (ROOT / "deploy/systemd/school-lifecycle-backup.service").read_text(encoding="utf-8")
    release = (ROOT / "scripts/deploy/install-systemd-release.sh").read_text(encoding="utf-8")
    runner = (ROOT / "deploy/backup/backup-runner.sh").read_text(encoding="utf-8")

    # Timer-triggered service must not start once the release pipeline has stopped the backend.
    assert "After=network-online.target mysql.service school-lifecycle-backend.service" in service
    assert "ExecCondition=/usr/bin/systemctl is-active --quiet school-lifecycle-backend.service" in service

    stop_pos = release.index('systemctl stop "${ACTIVE_OLD_SERVICES[@]}"')
    backup_pos = release.index('bash "$RELEASE_DIR/deploy/backup/backup-runner.sh"')
    manifest_pos = release.index('ROLLBACK_MANIFEST="$(find "$GOVERNED_BACKUP_DIR"')
    migrate_pos = release.index("-m alembic upgrade head")
    assert stop_pos < backup_pos < manifest_pos < migrate_pos

    # If a scheduled backup was already running before quiesce, the release-owned backup cannot
    # overlap it: the existing runner lock makes the release fail before any migration starts.
    assert 'LOCK_FILE="$BACKUP_DIR/.backup.lock"' in runner
    assert "flock -n 9" in runner


def test_release_backup_timer_contract_preserves_direct_emergency_runner():
    service = (ROOT / "deploy/systemd/school-lifecycle-backup.service").read_text(encoding="utf-8")
    release = (ROOT / "scripts/deploy/install-systemd-release.sh").read_text(encoding="utf-8")

    # The condition is attached only to the scheduled systemd service. The release keeps invoking
    # backup-runner.sh directly after quiesce, so the mandatory governed pre-migration backup is not
    # accidentally skipped merely because backend.service is intentionally stopped.
    assert "ExecCondition=" in service
    assert 'bash "$RELEASE_DIR/deploy/backup/backup-runner.sh"' in release
