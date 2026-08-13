from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_release_quiesces_scheduled_backup_before_application_writers():
    release = (ROOT / "scripts/deploy/install-systemd-release.sh").read_text(encoding="utf-8")
    service = (ROOT / "deploy/systemd/school-lifecycle-backup.service").read_text(encoding="utf-8")

    assert 'BACKUP_TIMER_UNIT="school-lifecycle-backup.timer"' in release
    assert 'BACKUP_SERVICE_UNIT="school-lifecycle-backup.service"' in release
    assert "quiesce_scheduled_backup()" in release
    assert 'systemctl stop "$BACKUP_TIMER_UNIT"' in release
    assert 'systemctl stop "$BACKUP_SERVICE_UNIT"' in release

    quiesce_call = release.index("\nquiesce_scheduled_backup\n")
    app_stop = release.index('systemctl stop "${ACTIVE_OLD_SERVICES[@]}"', quiesce_call)
    governed_backup = release.index('bash "$RELEASE_DIR/deploy/backup/backup-runner.sh"', app_stop)
    migrate = release.index("-m alembic upgrade head", governed_backup)
    assert quiesce_call < app_stop < governed_backup < migrate

    # Scheduling remains independent from backend health outside a release. A backend crash must
    # never silently disable disaster-recovery backups.
    assert "ExecCondition=" not in service
    assert "school-lifecycle-backend.service" not in service.split("[Service]", 1)[0]


def test_release_restores_only_the_timer_state_that_was_active_before_quiesce():
    release = (ROOT / "scripts/deploy/install-systemd-release.sh").read_text(encoding="utf-8")

    assert 'BACKUP_TIMER_WAS_ACTIVE=0' in release
    assert 'if systemctl is-active --quiet "$BACKUP_TIMER_UNIT"' in release
    assert 'BACKUP_TIMER_WAS_ACTIVE=1' in release
    assert "restore_scheduled_backup_timer()" in release
    assert 'if [ "$BACKUP_TIMER_WAS_ACTIVE" = "1" ]; then\n    systemctl start "$BACKUP_TIMER_UNIT"' in release

    # Failure recovery stops any backup trigger before DB restore and rearms the prior timer only
    # after previous application services have recovered. Critical restore failures intentionally
    # exit before rearming the timer so no corrupted/intermediate database is backed up.
    guard = release.split("release_failure_guard() {", 1)[1].split("\n}\ntrap release_failure_guard EXIT", 1)[0]
    assert 'systemctl stop "$BACKUP_TIMER_UNIT" "$BACKUP_SERVICE_UNIT"' in guard
    restore_db = guard.index('restore-backup-set.sh')
    restart_previous = guard.index('systemctl start "${ACTIVE_OLD_SERVICES[@]}"')
    restore_timer = guard.rindex("restore_scheduled_backup_timer")
    assert restore_db < restart_previous < restore_timer

    final_accept = release.index('accept-production-release.sh')
    final_timer_restore = release.rindex("restore_scheduled_backup_timer")
    disarm = release.rindex("trap - EXIT")
    assert final_accept < final_timer_restore < disarm


def test_release_keeps_direct_governed_backup_independent_from_timer_service():
    release = (ROOT / "scripts/deploy/install-systemd-release.sh").read_text(encoding="utf-8")
    runner = (ROOT / "deploy/backup/backup-runner.sh").read_text(encoding="utf-8")

    # Release invokes the governed runner directly after stopping the timer/service, so the
    # mandatory pre-migration backup cannot be skipped by scheduled-service state.
    assert 'bash "$RELEASE_DIR/deploy/backup/backup-runner.sh"' in release
    assert 'BACKUP_LOCK_FILE="${BACKUP_LOCK_FILE:-$BACKUP_DIR/.backup.lock}"' in runner
    assert "flock -n 9" in runner
