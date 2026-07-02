#!/usr/bin/env bash
# 数据库每日备份 + 30 天轮转。crontab：0 2 * * * /path/to/deploy/backup.sh
set -euo pipefail
cd "$(dirname "$0")"
source ../.env 2>/dev/null || true
DIR=./backup
mkdir -p "$DIR"
F="$DIR/${DB_NAME:-internship_management}_$(date +%F_%H%M).sql.gz"
if command -v docker &>/dev/null && docker compose -f docker-compose.yml ps db &>/dev/null; then
  docker compose -f docker-compose.yml exec -T db mysqldump -uroot -p"${DB_PASSWORD}" --single-transaction --routines "${DB_NAME:-internship_management}" | gzip > "$F"
else
  mysqldump -h"${DB_HOST:-localhost}" -u"${DB_USER:-root}" -p"${DB_PASSWORD}" --single-transaction --routines "${DB_NAME:-internship_management}" | gzip > "$F"
fi
find "$DIR" -name '*.sql.gz' -mtime +30 -delete
echo "备份完成: $F ($(du -h "$F" | cut -f1))"
