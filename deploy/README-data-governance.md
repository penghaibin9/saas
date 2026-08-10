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
- fails if no offsite target is configured;
- verifies every offsite object by independent SHA-256 readback;
- copies the manifest last so incomplete remote uploads are not treated as valid recovery points;
- prevents two backup jobs running at the same time;
- retains complete backup sets together instead of deleting individual files independently.

## Recovery objectives

Baseline:

- RPO <= 6 hours;
- RTO <= 2 hours.

The systemd timer runs four times per day: 01:15, 07:15, 13:15 and 19:15.

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
- uploads archive contents;
- restore duration;
- tables, indexes and foreign keys;
- Alembic version;
- tenant-count evidence.

The generated evidence records the manifest hash, recovery host/operator, source commit/workflow run when available, and completion time. The evidence file also receives its own SHA-256 checksum.

GitHub Actions has two layers:

- `Data governance contracts`: small PR-scoped proof independent of the backend pytest technical-debt cleanup;
- `Backup restore drill`: scheduled/manual full-stack recovery proof using the real migration chain, restored database, backend readiness and tenant login.

## What you need to do when deploying

Only these production steps need manual setup:

1. Fill `/etc/school-lifecycle/backup.env` with the real upload path and offsite rclone target.
2. Configure `/etc/school-lifecycle/rclone.conf` for the backup bucket.
3. In the cloud storage console, enable versioning/immutable retention and storage-side encryption, then set `BACKUP_IMMUTABLE_REMOTE_CONFIRMED=true`.
4. Install and enable `school-lifecycle-backup.service` and `.timer`.
5. Trigger one manual backup and one isolated restore drill to confirm everything works.

Everything else should be automated by the scripts and CI rather than requiring day-to-day manual operation.
