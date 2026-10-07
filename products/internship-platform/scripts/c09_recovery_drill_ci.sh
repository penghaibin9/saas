#!/usr/bin/env bash
# C09 real recovery drill for CI only.
# Spins up the production-like MySQL/Redis/backend stack, writes one real local
# file object, creates one backup set, restores it into an isolated database,
# and requires the restore evidence to verify the file bytes by SHA-256.
set -euo pipefail

if [ "${C09_RECOVERY_DRILL_ACK:-}" != "YES" ]; then
  echo "C09_RECOVERY_DRILL_ACK=YES is required" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY="$ROOT/deploy"
ENV_FILE="$DEPLOY/.env.production"
COMPOSE_FILE="$DEPLOY/docker-compose.production.yml"
BACKUP_DIR="$DEPLOY/backups"

cleanup() {
  (
    cd "$DEPLOY"
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down -v --remove-orphans
  ) >/dev/null 2>&1 || true
  rm -f "$ENV_FILE"
}
trap cleanup EXIT

mkdir -p "$BACKUP_DIR"
cat > "$ENV_FILE" <<EOF
COMPOSE_PROJECT_NAME=yueke-internship-recovery-ci
DB_NAME=internship_standalone
DB_USER=internship_app
DB_PASSWORD=${C09_DB_PASSWORD:-ci_recovery_app}
MYSQL_ROOT_PASSWORD=${C09_MYSQL_ROOT_PASSWORD:-ci_recovery_root}
MYSQL_MAX_CONNECTIONS=200
MYSQL_INNODB_BUFFER_POOL_SIZE=512M
REDIS_PASSWORD=${C09_REDIS_PASSWORD:-ci_recovery_redis}
REDIS_MAXMEMORY=128mb
JWT_SECRET=${C09_JWT_SECRET:-ci-recovery-jwt-secret-not-for-production-20260929}
FIELD_ENCRYPTION_KEY=${C09_FIELD_ENCRYPTION_KEY:-MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA=}
SENSITIVE_SEARCH_HMAC_KEY=${C09_HMAC_KEY:-ci-recovery-hmac-not-for-production}
WEB_CONCURRENCY=1
EXPECTED_ALEMBIC_REVISION=ix0023
FILE_STORAGE_DIR=/data/files
EOF

cd "$DEPLOY"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build mysql redis migrate backend

for attempt in $(seq 1 60); do
  if docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend     python -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:8000/health/ready',timeout=3)); assert d['status']=='READY'"     >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" = "60" ]; then
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" logs backend migrate mysql redis
    exit 1
  fi
  sleep 2
done

printf 'Yueke internship standalone C09 recovery evidence\n' > /tmp/c09-recovery-evidence.txt
file_sha="$(sha256sum /tmp/c09-recovery-evidence.txt | awk '{print $1}')"
file_size="$(stat -c '%s' /tmp/c09-recovery-evidence.txt)"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend   sh -c 'mkdir -p /data/files/gate && cat > /data/files/gate/c09-recovery-evidence.txt'   < /tmp/c09-recovery-evidence.txt

insert_sql="INSERT INTO t_file_object (
  file_key,file_name,ext,mime_type,size_bytes,sha256,visibility,security_level,status,
  storage_backend,storage_zone,legal_hold,upload_source,scan_required,scan_status,
  scan_attempts,tenant_id,updated_at,is_deleted,version,created_at
) VALUES (
  'gate/c09-recovery-evidence.txt','c09-recovery-evidence.txt','txt','text/plain',
  $file_size,'$file_sha','PRIVATE','NORMAL','AVAILABLE','local','ACTIVE',0,'SYSTEM',
  0,'NOT_REQUIRED',0,777,NOW(),0,0,NOW()
);"

docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T mysql   sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$MYSQL_DATABASE"'   <<< "$insert_sql"

row_count="$(printf '%s\n' "SELECT COUNT(*) FROM t_file_object WHERE file_key='gate/c09-recovery-evidence.txt';" | docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysql -uroot "$MYSQL_DATABASE" --batch --skip-column-names' | tr -d '\r')"
[ "$row_count" = "1" ] || { echo "recovery evidence FileObject seed failed" >&2; exit 1; }

rm -f "$BACKUP_DIR"/manifest_*.json "$BACKUP_DIR"/manifest_*.json.sha256       "$BACKUP_DIR"/mysql_*.sql.gz "$BACKUP_DIR"/mysql_*.sql.gz.sha256       "$BACKUP_DIR"/files_*.tar.gz "$BACKUP_DIR"/files_*.tar.gz.sha256       "$BACKUP_DIR"/restore-evidence-ci.json "$BACKUP_DIR"/restore-evidence-ci.json.sha256

SOURCE_COMMIT="${GITHUB_SHA:-local-ci}" KEEP_DAYS=30 bash ./backup/backup.sh
manifest="$(ls -1t "$BACKUP_DIR"/manifest_*.json | head -1)"
[ -s "$manifest" ] || { echo "backup manifest missing" >&2; exit 1; }
[ -s "$manifest.sha256" ] || { echo "backup manifest checksum missing" >&2; exit 1; }

EXPECTED_ALEMBIC_REVISION=ix0023 EVIDENCE_FILE="$BACKUP_DIR/restore-evidence-ci.json" bash ./backup/restore-drill.sh "$manifest" internship_restore_drill

python3 - "$BACKUP_DIR/restore-evidence-ci.json" "$file_sha" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
expected_file_sha = sys.argv[2]
data = json.loads(path.read_text(encoding="utf-8"))

assert data["verdict"] == "PASS", data
assert data["alembicRevision"] == "ix0023", data
assert int(data["tableCount"]) >= 90, data
assert int(data["localFileObjectsVerified"]) >= 1, data
assert int(data["hashedFileObjectsVerified"]) >= 1, data
assert int(data["externalStorageObjects"]) == 0, data

manifest = sorted(path.parent.glob("manifest_*.json"))[-1]
backup = json.loads(manifest.read_text(encoding="utf-8"))
assert backup["product"] == "internship-standalone", backup
assert backup["database"]["sha256"], backup
assert backup["files"]["sha256"], backup

print(json.dumps({
    "gate": "C09-RECOVERY",
    "verdict": data["verdict"],
    "revision": data["alembicRevision"],
    "tableCount": data["tableCount"],
    "localFilesVerified": data["localFileObjectsVerified"],
    "hashedFilesVerified": data["hashedFileObjectsVerified"],
    "backupSetId": data["backupSetId"],
    "seedFileSha256": expected_file_sha,
    "restoreSeconds": data["restoreSeconds"],
}, ensure_ascii=False))
PY

(
  cd "$BACKUP_DIR"
  sha256sum -c restore-evidence-ci.json.sha256
)

echo "[c09-recovery] PASS"
