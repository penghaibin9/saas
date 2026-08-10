# Production data governance baseline

This document defines the minimum production backup and recovery contract for the school lifecycle SaaS. It does not replace school-specific retention or compliance requirements.

## 1. One backup is one committed set

A valid backup is not a database dump by itself. `backup-mysql.sh` creates one set containing:

- compressed MySQL dump;
- compressed uploads archive when uploads are required;
- SHA-256 sidecars for both payloads;
- a JSON manifest binding the exact database and uploads files, sizes and hashes.

The manifest is the commit marker. A restore must select a manifest and restore the exact objects named by it. Orphan files without a completed manifest are not a valid recovery point.

## 2. Production fails closed

`school-lifecycle-backup.service` pins all of the following:

- `REQUIRE_UPLOAD_BACKUP=1`;
- `BACKUP_REQUIRE_OFFSITE=true`;
- `BACKUP_REQUIRE_IMMUTABLE_REMOTE=true`;
- `RCLONE_CONFIG=/etc/school-lifecycle/rclone.conf`.

Therefore a missing uploads directory, missing remote, unreadable rclone config, failed transfer, failed remote readback, or unconfirmed immutable storage makes the backup job fail.

## 3. Offsite integrity and anti-ransomware controls

`backup-runner.sh` uploads payloads and checksum sidecars first, independently reads every remote object back through `rclone cat`, recomputes SHA-256, and copies the manifest last.

Before setting `BACKUP_IMMUTABLE_REMOTE_CONFIRMED=true`, verify in the cloud-provider control plane that the production backup bucket has versioning and an immutable/WORM retention mechanism enabled for the required retention period. Keep the evidence outside Git. The confirmation flag is an operational attestation, not a mechanism that configures the provider.

## 4. Recovery objectives

The baseline is:

- RPO <= 6 hours (`21600` seconds);
- RTO <= 2 hours (`7200` seconds).

The systemd timer runs at 01:15, 07:15, 13:15 and 19:15 with no random delay. A school contract may impose stricter objectives, never looser objectives without an explicit governance decision.

## 5. Recovery evidence

`restore-drill.sh` refuses production or remote database targets. It validates the manifest, SHA-256 sidecars, backup freshness, uploads archive, schema/table/index/foreign-key thresholds and the configured Alembic version before producing recovery evidence.

GitHub Actions contains two layers:

- `Data governance contracts`: PR-scoped, synthetic MySQL runtime proof that does not depend on the historical backend pytest debt;
- `Backup restore drill`: scheduled/manual full-stack proof using the current migration chain, restored database, backend readiness and real tenant login.

A scheduled full drill failure is a release-operations incident even when ordinary feature PR checks remain green.

## 6. Production installation checklist

1. Copy `deploy/env/backup.env.example` to `/etc/school-lifecycle/backup.env` and set mode `0640`.
2. Create `/etc/school-lifecycle/rclone.conf` outside Git and grant read access only to the backup service account.
3. Configure the offsite bucket and immutable/versioned retention, then set `BACKUP_IMMUTABLE_REMOTE_CONFIRMED=true` only after verification.
4. Install `school-lifecycle-backup.service` and `.timer`, run `systemctl daemon-reload`, enable the timer, and trigger one manual service run.
5. Confirm the remote contains a complete manifest-committed set and that the service journal reports independent SHA-256 readback success.
6. Run an isolated restore drill and archive the RPO/RTO evidence with the operational change record.
