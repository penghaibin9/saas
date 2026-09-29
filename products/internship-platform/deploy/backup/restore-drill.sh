#!/usr/bin/env bash
# Restore a backup set into an isolated MySQL drill DB and verify local file bytes.
set -euo pipefail

manifest="${1:?usage: restore-drill.sh <manifest.json> [drill_db]}"
drill_db="${2:-internship_restore_drill}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "$HERE/.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-$DEPLOY_DIR/docker-compose.production.yml}"
ENV_FILE="${ENV_FILE:-$DEPLOY_DIR/.env.production}"
EXPECTED_ALEMBIC_REVISION="${EXPECTED_ALEMBIC_REVISION:-ix0023}"
KEEP_DRILL_DB="${KEEP_DRILL_DB:-0}"
EVIDENCE_FILE="${EVIDENCE_FILE:-$DEPLOY_DIR/backups/restore-evidence-$(date -u +%Y%m%d_%H%M%S).json}"

[[ "$drill_db" =~ ^[A-Za-z0-9_]+(_drill|_restore_drill|_restore_test)$ ]] || {
  echo "drill DB name must end with _drill, _restore_drill or _restore_test" >&2
  exit 2
}
[ -f "$manifest" ] || { echo "manifest missing: $manifest" >&2; exit 2; }
[ -f "$ENV_FILE" ] || { echo "environment file missing: $ENV_FILE" >&2; exit 2; }

backup_dir="$(cd "$(dirname "$manifest")" && pwd)"
(
  cd "$backup_dir"
  sha256sum -c "$(basename "$manifest").sha256"
)

mapfile -t meta < <(python3 - "$manifest" <<'PY'
import json,sys
from pathlib import Path
m=json.load(open(sys.argv[1],encoding="utf-8"))
if m.get("schemaVersion") != 1 or m.get("product") != "internship-standalone":
    raise SystemExit("unsupported backup manifest")
def safe(value):
    if not isinstance(value,str) or Path(value).name != value:
        raise SystemExit(f"unsafe manifest filename: {value!r}")
    return value
print(m["backupSetId"])
print(safe(m["database"]["file"]))
print(m["database"]["sha256"])
print(safe(m["files"]["file"]))
print(m["files"]["sha256"])
print(m.get("sourceCommit") or "unknown")
PY
)

backup_set_id="${meta[0]}"
db_name="${meta[1]}"
db_sha="${meta[2]}"
files_name="${meta[3]}"
files_sha="${meta[4]}"
source_commit="${meta[5]}"
db_file="$backup_dir/$db_name"
files_file="$backup_dir/$files_name"

verify_file() {
  local file="$1" expected="$2"
  test -s "$file"
  local actual
  actual="$(sha256sum "$file" | awk '{print $1}')"
  [ "$actual" = "$expected" ] || { echo "sha256 mismatch: $file" >&2; exit 1; }
}
verify_file "$db_file" "$db_sha"
verify_file "$files_file" "$files_sha"
gzip -t "$db_file"
gzip -t "$files_file"

dc=(docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
"${dc[@]}" exec -T mysql sh -c 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" mysqladmin -uroot ping --silent'

cleanup_db() {
  if [ "$KEEP_DRILL_DB" != "1" ]; then
    "${dc[@]}" exec -T mysql sh -c "MYSQL_PWD=\"\$MYSQL_ROOT_PASSWORD\" mysql -uroot -e 'DROP DATABASE IF EXISTS $drill_db;'" >/dev/null 2>&1 || true
  fi
}
tmp="$(mktemp -d)"
cleanup_all() {
  rm -rf "$tmp"
  cleanup_db
}
trap cleanup_all EXIT

started="$(date +%s)"
"${dc[@]}" exec -T mysql sh -c "MYSQL_PWD=\"\$MYSQL_ROOT_PASSWORD\" mysql -uroot -e 'DROP DATABASE IF EXISTS $drill_db; CREATE DATABASE $drill_db CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;'"
gunzip -c "$db_file" | "${dc[@]}" exec -T mysql sh -c "MYSQL_PWD=\"\$MYSQL_ROOT_PASSWORD\" mysql -uroot $drill_db"

revision="$("${dc[@]}" exec -T mysql sh -c "MYSQL_PWD=\"\$MYSQL_ROOT_PASSWORD\" mysql -uroot -Nse 'SELECT version_num FROM $drill_db.alembic_version LIMIT 1'" | tr -d '\r')"
[ "$revision" = "$EXPECTED_ALEMBIC_REVISION" ] || {
  echo "Alembic mismatch: expected=$EXPECTED_ALEMBIC_REVISION actual=$revision" >&2
  exit 1
}

table_count="$("${dc[@]}" exec -T mysql sh -c "MYSQL_PWD=\"\$MYSQL_ROOT_PASSWORD\" mysql -uroot -Nse \"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$drill_db'\"" | tr -d '\r')"
[ "${table_count:-0}" -ge 90 ] || { echo "suspicious restored table count: $table_count" >&2; exit 1; }

python3 - "$files_file" "$tmp" <<'PY'
import sys,tarfile
from pathlib import Path,PurePosixPath
archive=Path(sys.argv[1]); out=Path(sys.argv[2]).resolve()
with tarfile.open(archive,"r:gz") as tf:
    for member in tf.getmembers():
        p=PurePosixPath(member.name)
        if p.is_absolute() or ".." in p.parts or not (member.isfile() or member.isdir()):
            raise SystemExit(f"unsafe archive member: {member.name!r}")
    tf.extractall(out, filter="data")
PY

file_rows="$tmp/fileobjects.tsv"
"${dc[@]}" exec -T mysql sh -c "MYSQL_PWD=\"\$MYSQL_ROOT_PASSWORD\" mysql -uroot --batch --raw --skip-column-names -e \"SELECT id,file_key,COALESCE(size_bytes,''),COALESCE(sha256,''),LOWER(COALESCE(NULLIF(storage_backend,''),'local')) FROM $drill_db.t_file_object WHERE is_deleted=0 ORDER BY id\"" > "$file_rows"

read -r local_files hashed_files external_files < <(python3 - "$tmp/files" "$file_rows" <<'PY'
import hashlib,re,sys
from pathlib import Path,PurePosixPath
root=Path(sys.argv[1]).resolve()
local=hashed=external=0
for raw in Path(sys.argv[2]).read_text(encoding="utf-8").splitlines():
    parts=raw.split("\t")
    if len(parts) != 5:
        raise SystemExit(f"invalid t_file_object row: {raw!r}")
    file_id,key,size,sha,backend=parts
    if backend != "local":
        external += 1
        continue
    rel=PurePosixPath(key)
    if not key or rel.is_absolute() or ".." in rel.parts:
        raise SystemExit(f"unsafe file_key id={file_id}: {key!r}")
    target=root.joinpath(*rel.parts).resolve()
    if target == root or root not in target.parents:
        raise SystemExit(f"file key escaped restore root id={file_id}")
    if not target.is_file():
        raise SystemExit(f"file bytes missing id={file_id}: {key}")
    if size and target.stat().st_size != int(size):
        raise SystemExit(f"size mismatch id={file_id}")
    if sha:
        if not re.fullmatch(r"[0-9a-fA-F]{64}",sha):
            raise SystemExit(f"invalid sha256 id={file_id}")
        digest=hashlib.sha256()
        with target.open("rb") as handle:
            for chunk in iter(lambda:handle.read(1024*1024),b""):
                digest.update(chunk)
        if digest.hexdigest().lower() != sha.lower():
            raise SystemExit(f"sha256 mismatch id={file_id}")
        hashed += 1
    local += 1
print(local,hashed,external)
PY
)

elapsed="$(( $(date +%s) - started ))"
mkdir -p "$(dirname "$EVIDENCE_FILE")"
BACKUP_SET_ID="$backup_set_id" SOURCE_COMMIT="$source_commit" REVISION="$revision" TABLE_COUNT="$table_count" LOCAL_FILES="$local_files" HASHED_FILES="$hashed_files" EXTERNAL_FILES="$external_files" ELAPSED="$elapsed" DRILL_DB="$drill_db" python3 - "$EVIDENCE_FILE" <<'PY'
import json,os,sys
from datetime import datetime,timezone
payload={
 "schemaVersion":1,
 "gate":"C09-RESTORE",
 "verdict":"PASS",
 "backupSetId":os.environ["BACKUP_SET_ID"],
 "sourceCommit":os.environ["SOURCE_COMMIT"],
 "alembicRevision":os.environ["REVISION"],
 "tableCount":int(os.environ["TABLE_COUNT"]),
 "localFileObjectsVerified":int(os.environ["LOCAL_FILES"]),
 "hashedFileObjectsVerified":int(os.environ["HASHED_FILES"]),
 "externalStorageObjects":int(os.environ["EXTERNAL_FILES"]),
 "restoreSeconds":int(os.environ["ELAPSED"]),
 "drillDatabase":os.environ["DRILL_DB"],
 "completedAtUtc":datetime.now(timezone.utc).isoformat(),
 "note":"External/COS objects still require provider-level copy and checksum evidence."
}
with open(sys.argv[1],"w",encoding="utf-8") as handle:
    json.dump(payload,handle,ensure_ascii=False,indent=2)
    handle.write("\n")
PY
sha256sum "$EVIDENCE_FILE" > "${EVIDENCE_FILE}.sha256"
echo "[restore-drill] PASS evidence=$EVIDENCE_FILE"
