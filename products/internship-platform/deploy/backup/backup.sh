#!/usr/bin/env bash
# Consistent standalone recovery set: MySQL dump + file bytes + SHA-256 manifest.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$HERE/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.production.yml}"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env.production}"
BACKUP_DIR="${BACKUP_DIR:-$DEPLOY_DIR/backups}"
KEEP_DAYS="${KEEP_DAYS:-30}"
SOURCE_COMMIT="${SOURCE_COMMIT:-unknown}"

[ -f "$COMPOSE_FILE" ] || { echo "compose file missing: $COMPOSE_FILE" >&2; exit 2; }
[ -f "$ENV_FILE" ] || { echo "environment file missing: $ENV_FILE" >&2; exit 2; }
[[ "$KEEP_DAYS" =~ ^[0-9]+$ ]] && [ "$KEEP_DAYS" -ge 1 ] || { echo "KEEP_DAYS must be positive" >&2; exit 2; }

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR" 2>/dev/null || true

stamp="$(date -u +%Y%m%d_%H%M%S)"
db_file="$BACKUP_DIR/mysql_${stamp}.sql.gz"
files_file="$BACKUP_DIR/files_${stamp}.tar.gz"
manifest="$BACKUP_DIR/manifest_${stamp}.json"
tmp_db="${db_file}.partial"
tmp_files="${files_file}.partial"
tmp_manifest="${manifest}.partial"

cleanup() { rm -f "$tmp_db" "$tmp_files" "$tmp_manifest"; }
trap cleanup EXIT

dc=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

echo "[backup] checking services"
"${dc[@]}" exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqladmin -uroot ping --silent'
"${dc[@]}" exec -T backend python - <<'PY'
import json, urllib.request
payload=json.load(urllib.request.urlopen("http://127.0.0.1:8000/health/ready", timeout=5))
assert payload["status"] == "READY", payload
print(json.dumps(payload, ensure_ascii=False))
PY

echo "[backup] dumping MySQL"
"${dc[@]}" exec -T mysql sh -c '
  MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqldump -uroot     --single-transaction --quick --routines --events --triggers     --hex-blob --default-character-set=utf8mb4     --no-tablespaces --set-gtid-purged=OFF "$MYSQL_DATABASE"
' | gzip -9 > "$tmp_db"
test -s "$tmp_db"
gzip -t "$tmp_db"
mv "$tmp_db" "$db_file"

echo "[backup] archiving file bytes"
"${dc[@]}" exec -T backend python - <<'PY' > "$tmp_files"
import sys, tarfile
from pathlib import Path
root=Path("/data/files")
if not root.is_dir():
    raise SystemExit("FILE_STORAGE_DIR missing: /data/files")
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|gz") as archive:
    archive.add(root, arcname="files", recursive=True)
PY
test -s "$tmp_files"
gzip -t "$tmp_files"
mv "$tmp_files" "$files_file"

db_sha="$(sha256sum "$db_file" | awk '{print $1}')"
files_sha="$(sha256sum "$files_file" | awk '{print $1}')"
db_size="$(stat -c '%s' "$db_file")"
files_size="$(stat -c '%s' "$files_file")"

DB_FILE="$(basename "$db_file")" DB_SHA="$db_sha" DB_SIZE="$db_size" FILES_FILE="$(basename "$files_file")" FILES_SHA="$files_sha" FILES_SIZE="$files_size" STAMP="$stamp" SOURCE_COMMIT="$SOURCE_COMMIT" python3 - "$tmp_manifest" <<'PY'
import json, os, sys
from datetime import datetime, timezone
payload={
  "schemaVersion":1,
  "product":"internship-standalone",
  "backupSetId":os.environ["STAMP"],
  "createdAtUtc":datetime.now(timezone.utc).isoformat(),
  "sourceCommit":os.environ["SOURCE_COMMIT"],
  "database":{
    "file":os.environ["DB_FILE"],
    "sha256":os.environ["DB_SHA"],
    "sizeBytes":int(os.environ["DB_SIZE"]),
  },
  "files":{
    "file":os.environ["FILES_FILE"],
    "sha256":os.environ["FILES_SHA"],
    "sizeBytes":int(os.environ["FILES_SIZE"]),
  },
}
with open(sys.argv[1],"w",encoding="utf-8") as h:
    json.dump(payload,h,ensure_ascii=False,indent=2,sort_keys=True)
    h.write("\n")
PY
mv "$tmp_manifest" "$manifest"

(
  cd "$BACKUP_DIR"
  sha256sum "$(basename "$db_file")" > "$(basename "$db_file").sha256"
  sha256sum "$(basename "$files_file")" > "$(basename "$files_file").sha256"
  sha256sum "$(basename "$manifest")" > "$(basename "$manifest").sha256"
)

find "$BACKUP_DIR" -type f -mtime "+$KEEP_DAYS" \(   -name 'mysql_*.sql.gz' -o -name 'mysql_*.sql.gz.sha256' -o   -name 'files_*.tar.gz' -o -name 'files_*.tar.gz.sha256' -o   -name 'manifest_*.json' -o -name 'manifest_*.json.sha256' \) -delete

trap - EXIT
echo "[backup] complete: $manifest"
