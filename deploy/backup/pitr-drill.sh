#!/usr/bin/env bash
# Restore a disposable local MySQL database to an exact binary-log position.
#
# This drill proves the recovery mechanics only. It does not claim that production
# binary logs are archived off-host; production RPO remains governed separately.
set -euo pipefail

base_dump="${1:?usage: pitr-drill.sh <base_dump.sql.gz> <drill_db> <binlog_file> <start_position> <target_position>}"
drill_db="${2:?usage: pitr-drill.sh <base_dump.sql.gz> <drill_db> <binlog_file> <start_position> <target_position>}"
binlog_file="${3:?usage: pitr-drill.sh <base_dump.sql.gz> <drill_db> <binlog_file> <start_position> <target_position>}"
start_position="${4:?usage: pitr-drill.sh <base_dump.sql.gz> <drill_db> <binlog_file> <start_position> <target_position>}"
target_position="${5:?usage: pitr-drill.sh <base_dump.sql.gz> <drill_db> <binlog_file> <start_position> <target_position>}"

DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-root}"
: "${DB_PASSWORD:?DB_PASSWORD must be set}"
MAX_PITR_SECONDS="${MAX_PITR_SECONDS:-900}"
PITR_EVIDENCE_FILE="${PITR_EVIDENCE_FILE:-}"

case "$DB_HOST" in
  127.0.0.1|localhost|::1) ;;
  *) echo "PITR drill refuses non-local DB_HOST=$DB_HOST" >&2; exit 2 ;;
esac
case "${APP_ENV:-test}" in
  production|prod) echo "PITR drill refuses APP_ENV=${APP_ENV}" >&2; exit 2 ;;
esac
case "${DEPLOYMENT_MODE:-local}" in
  production) echo "PITR drill refuses DEPLOYMENT_MODE=production" >&2; exit 2 ;;
esac
if [[ ! "$drill_db" =~ ^[A-Za-z0-9_]+_pitr_drill$ ]]; then
  echo "PITR drill database must end with _pitr_drill" >&2
  exit 2
fi
if [[ ! "$binlog_file" =~ ^[A-Za-z0-9_.-]+$ ]]; then
  echo "unsafe binary-log filename: $binlog_file" >&2
  exit 2
fi
if [[ ! "$start_position" =~ ^[0-9]+$ || ! "$target_position" =~ ^[0-9]+$ ]]; then
  echo "binary-log positions must be positive integers" >&2
  exit 2
fi
if (( start_position < 4 || target_position <= start_position )); then
  echo "invalid PITR range: start=$start_position target=$target_position" >&2
  exit 2
fi
if [[ ! "$MAX_PITR_SECONDS" =~ ^[0-9]+$ || "$MAX_PITR_SECONDS" -lt 1 ]]; then
  echo "MAX_PITR_SECONDS must be a positive integer" >&2
  exit 2
fi

test -s "$base_dump"
test -f "${base_dump}.sha256"
(
  cd "$(dirname "$base_dump")"
  sha256sum -c "$(basename "${base_dump}.sha256")"
)
gzip -t "$base_dump"
base_dump_sha256="$(sha256sum "$base_dump" | awk '{print $1}')"

export MYSQL_PWD="$DB_PASSWORD"
MYSQL=(mysql --protocol=tcp -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER")
MYSQLBINLOG=(mysqlbinlog --read-from-remote-server --protocol=tcp -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER")

log_bin="$("${MYSQL[@]}" -Nse "SELECT @@GLOBAL.log_bin")"
binlog_format="$("${MYSQL[@]}" -Nse "SELECT @@GLOBAL.binlog_format")"
if [[ "$log_bin" != "1" ]]; then
  echo "PITR drill requires MySQL binary logging" >&2
  exit 1
fi
if [[ "$binlog_format" != "ROW" ]]; then
  echo "PITR drill requires ROW binlog format; actual=$binlog_format" >&2
  exit 1
fi
listed="$("${MYSQL[@]}" -Nse "SHOW BINARY LOGS" | awk '{print $1}' | grep -Fx "$binlog_file" || true)"
if [[ "$listed" != "$binlog_file" ]]; then
  echo "binary log not available on source: $binlog_file" >&2
  exit 1
fi

started_epoch="$(date +%s)"
"${MYSQL[@]}" -e "DROP DATABASE IF EXISTS \`${drill_db}\`; CREATE DATABASE \`${drill_db}\` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
gunzip -c "$base_dump" | "${MYSQL[@]}" "$drill_db"

# Replay only the committed interval ending at the requested recovery position.
# The source and restored DB intentionally have the same disposable name so row
# events retain their original table identity without unsafe text rewriting.
"${MYSQLBINLOG[@]}" \
  --start-position="$start_position" \
  --stop-position="$target_position" \
  "$binlog_file" | "${MYSQL[@]}"

pitr_seconds="$(( $(date +%s) - started_epoch ))"
if (( pitr_seconds > MAX_PITR_SECONDS )); then
  echo "PITR exceeded RTO threshold: restore=${pitr_seconds}s max=${MAX_PITR_SECONDS}s" >&2
  exit 1
fi

if [[ -n "$PITR_EVIDENCE_FILE" ]]; then
  mkdir -p "$(dirname "$PITR_EVIDENCE_FILE")"
  cat > "$PITR_EVIDENCE_FILE" <<EVIDENCE
drill_database=$drill_db
base_dump_sha256=$base_dump_sha256
binlog_file=$binlog_file
start_position=$start_position
target_position=$target_position
binlog_format=$binlog_format
pitr_seconds=$pitr_seconds
max_pitr_seconds=$MAX_PITR_SECONDS
production_binlog_archival_proven=false
drill_trigger_sha=${GITHUB_SHA:-unknown}
workflow_run_id=${GITHUB_RUN_ID:-manual}
completed_at_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)
EVIDENCE
  (
    cd "$(dirname "$PITR_EVIDENCE_FILE")"
    sha256sum "$(basename "$PITR_EVIDENCE_FILE")" > "$(basename "$PITR_EVIDENCE_FILE").sha256"
  )
fi

unset MYSQL_PWD
echo "PITR drill complete: db=${drill_db} binlog=${binlog_file} range=${start_position}-${target_position} seconds=${pitr_seconds}"
