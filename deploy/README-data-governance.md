# Production data governance baseline

This is the simple production baseline for backup and recovery. The goal is that normal operation is automatic and the operator only needs a small number of deployment settings.

## What the system does automatically

A valid backup is one complete set containing:

- MySQL dump;
- uploads archive;
- SHA-256 checksums;
- one JSON manifest that binds the exact database and uploads files together.

The manifest is the commit marker. A restore always follows the manifest, so the database and attachments cannot silently come from different backup times.

Production backup also:

- fails if required uploads are missing;
- rejects unsafe upload entries such as symlinks and special files;
- fails if no offsite target is configured;
- verifies every offsite object by independent SHA-256 readback;
- copies the manifest last so incomplete remote uploads are not treated as valid recovery points;
- prevents two backup jobs running at the same time;
- cleans incomplete files after a failed backup attempt;
- retains complete backup sets together instead of deleting individual files independently;
- is force-failed by systemd after 5 hours if a network/storage call hangs, so one stuck run cannot block future recovery points forever.

## Automatic stale-backup watchdog

A backup system can fail silently when its timer stops running. `backup-watchdog.sh` independently checks the newest committed backup and fails if:

- no completed manifest exists;
- the newest backup is older than the configured RPO window;
- local database/upload objects or their checksums are missing or invalid;
- the offsite manifest commit marker is missing or differs from the local committed manifest.

`school-lifecycle-backup-watchdog.timer` runs this check hourly. The watchdog itself has a 10-minute systemd timeout so an unavailable storage provider cannot leave the health check hanging forever. It reuses the same optional failure webhook as the backup job, so there is no second alert configuration to maintain.

## Recovery objectives

Baseline:

- RPO <= 6 hours;
- RTO <= 2 hours.

The backup timer runs four times per day: 01:15, 07:15, 13:15 and 19:15. The watchdog checks backup freshness hourly.

Local retention keeps at least 8 complete sets by default, which gives at least 48 hours of local recovery points at the default cadence.

## Offsite protection

Use one production offsite bucket through rclone. Before setting `BACKUP_IMMUTABLE_REMOTE_CONFIRMED=true`, enable and verify provider-side versioning plus immutable/WORM retention for that bucket.

Do not implement ordinary deletion of the immutable remote from the backup host. Historical remote versions should be managed by the cloud provider's retention/lifecycle controls.

For a first production deployment, keep this operationally simple: use the cloud provider's storage-side encryption setting for the backup bucket rather than introducing a separate application-managed backup key system.

## Recovery evidence

`restore-drill.sh` can only restore into a disposable local drill database. It refuses production or remote DB targets.

It verifies:

- manifest checksum;
- database/upload checksums;
- backup freshness;
- upload archive member safety before extraction;
- restore duration;
- tables, indexes and foreign keys;
- Alembic version;
- tenant-count evidence.

The generated evidence records the manifest hash, recovery host/operator, source commit/workflow run when available, and completion time. The evidence file also receives its own SHA-256 checksum.

GitHub Actions has two layers:

- `Data governance contracts`: small PR-scoped proof independent of the backend pytest technical-debt cleanup;
- `Backup restore drill`: scheduled/manual full-stack recovery proof using the real migration chain, restored database, backend readiness and tenant login.

## One recovery secret you must not lose

The database contains fields encrypted by the application's production field-encryption key. A database backup can restore successfully while those fields remain unreadable if the original production key history is lost.

Keep one protected recovery copy of the production backend environment/secrets outside the application server and outside Git. At minimum this must preserve `FIELD_ENCRYPTION_KEY`, any configured `FIELD_ENCRYPTION_PREVIOUS_KEYS`, and `SENSITIVE_SEARCH_HMAC_KEY` when used. A password manager or encrypted secret vault is sufficient; do not put these values in the backup repository or GitHub.

This is a one-time disaster-recovery precaution, not a new day-to-day key-management system.

## What you need to do when deploying

Only these production steps need manual setup:

1. Fill `/etc/school-lifecycle/backup.env` with the real upload path and offsite rclone target, and keep one protected recovery copy of the production backend secrets outside the server/Git.
2. Configure `/etc/school-lifecycle/rclone.conf` for the backup bucket.
3. In the cloud storage console, enable versioning/immutable retention and storage-side encryption, then set `BACKUP_IMMUTABLE_REMOTE_CONFIRMED=true`.
4. Install the backup and watchdog systemd service/timer files. Run one manual backup and one manual watchdog check first; after both pass, enable both timers.
5. Run one isolated restore drill to confirm the database, uploads and recovery evidence are usable.

Everything else should be automated by the scripts and CI rather than requiring day-to-day manual operation.
