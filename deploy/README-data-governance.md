# Production data governance baseline

This document defines the minimum production backup and recovery contract for the school lifecycle SaaS. It does not replace school-specific retention, privacy, or regulatory requirements.

## 1. One backup is one committed set

A valid backup is not a database dump by itself. `backup-mysql.sh` creates one set containing:

- an age-encrypted compressed MySQL dump;
- an age-encrypted compressed uploads archive when uploads are required;
- SHA-256 sidecars for every payload and for the manifest;
- a JSON manifest binding the exact database and uploads files, sizes, hashes, creation time and encryption format.

The manifest is the commit marker. A restore must select a manifest and restore the exact objects named by it. Orphan files without a completed manifest are not a valid recovery point.

Local retention is also set-aware: complete sets are pruned together, never file-by-file, and at least `MIN_LOCAL_BACKUP_SETS` complete sets are retained even when `KEEP_DAYS` would otherwise prune more aggressively.

## 2. Backup encryption and key separation

Production pins `BACKUP_REQUIRE_ENCRYPTION=true`.

Generate a dedicated recovery identity offline with `age-keygen`. Put only the public `age1...` recipient in `/etc/school-lifecycle/backup.env`. The private age identity must not be present on the production backup service host and must never be committed to Git, written into CI logs, embedded in rclone configuration, or copied into the offsite backup bucket.

The private recovery identity belongs in a separately controlled recovery vault. An isolated restore operator provides it through `BACKUP_AGE_IDENTITY_FILE` only for the duration of the drill or incident.

This separation means compromise of the backup host or offsite bucket does not by itself provide the decryption key.

## 3. Production fails closed

`school-lifecycle-backup.service` pins all of the following:

- `REQUIRE_UPLOAD_BACKUP=1`;
- `BACKUP_REQUIRE_OFFSITE=true`;
- `BACKUP_REQUIRE_IMMUTABLE_REMOTE=true`;
- `BACKUP_REQUIRE_ENCRYPTION=true`;
- `RCLONE_CONFIG=/etc/school-lifecycle/rclone.conf`.

Therefore a missing uploads directory, missing age recipient, missing `age` binary, missing remote, unreadable rclone config, failed transfer, failed remote readback, or unconfirmed immutable storage makes the backup job fail.

## 4. Offsite integrity and anti-ransomware controls

`backup-runner.sh` uploads encrypted payloads and checksum sidecars first, independently reads every remote object back through `rclone cat`, recomputes SHA-256, uploads the manifest checksum, and copies the manifest last.

Before setting `BACKUP_IMMUTABLE_REMOTE_CONFIRMED=true`, verify in the cloud-provider control plane that the production backup bucket has versioning and an immutable/WORM retention mechanism enabled for the required retention period. Keep provider-side evidence outside Git. The confirmation flag is an operational attestation, not a mechanism that configures the provider.

Do not implement ordinary rclone deletion of the immutable production remote. Remote retention and expiry must be enforced by the cloud provider's versioning/Object-Lock/lifecycle controls so a compromised backup host cannot erase historical recovery points.

## 5. Recovery objectives

The baseline is:

- RPO <= 6 hours (`21600` seconds);
- RTO <= 2 hours (`7200` seconds).

The systemd timer runs at 01:15, 07:15, 13:15 and 19:15 with no random delay. A school contract may impose stricter objectives, never looser objectives without an explicit governance decision.

## 6. Recovery evidence

`restore-drill.sh` refuses production or remote database targets. It validates:

- the manifest SHA-256 sidecar before parsing it;
- every encrypted payload and its SHA-256;
- successful age decryption with the isolated recovery identity;
- backup freshness against RPO;
- uploads archive contents;
- database restore duration against RTO;
- schema/table/index/foreign-key thresholds;
- the configured Alembic version and tenant-count evidence.

The evidence record includes the backup-set ID, manifest hash, encryption format, recovery host/operator, source commit/workflow run when available, and completion time. A SHA-256 sidecar is generated for the evidence record so later corruption or accidental editing is detectable.

GitHub Actions contains two layers:

- `Data governance contracts`: PR-scoped synthetic MySQL runtime proof independent of historical backend pytest debt;
- `Backup restore drill`: scheduled/manual full-stack proof using the current migration chain, encrypted offsite objects, restored database, backend readiness and real tenant login.

A scheduled full drill failure is a release-operations incident even when ordinary feature PR checks remain green.

## 7. Production installation checklist

1. Install `age`, `rclone`, the MySQL client and required runtime utilities on the backup host.
2. Generate a dedicated age recovery identity offline. Store the private identity in a recovery vault and copy only its public `age1...` recipient into `/etc/school-lifecycle/backup.env`.
3. Copy `deploy/env/backup.env.example` to `/etc/school-lifecycle/backup.env`, set the recipient and operational values, and set mode `0640`.
4. Create `/etc/school-lifecycle/rclone.conf` outside Git and grant read access only to the backup service account.
5. Configure the offsite bucket and immutable/versioned retention, then set `BACKUP_IMMUTABLE_REMOTE_CONFIRMED=true` only after verification.
6. Install `school-lifecycle-backup.service` and `.timer`, run `systemctl daemon-reload`, enable the timer, and trigger one manual service run.
7. Confirm the remote contains only encrypted database/upload payloads for the new set, all checksum sidecars, and the manifest committed last.
8. In an isolated recovery environment, provide the private age identity through `BACKUP_AGE_IDENTITY_FILE`, run a restore drill, verify the evidence sidecar, and archive the RPO/RTO evidence with the operational change record.
