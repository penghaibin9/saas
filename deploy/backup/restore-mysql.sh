#!/usr/bin/env bash
# MySQL 恢复脚本（与 backup-mysql.sh 配套）。
# 用法：./restore-mysql.sh /backups/saas_lifecycle_20260705_020000.sql.gz
# 环境变量：DB_HOST DB_PORT DB_NAME DB_USER DB_PASSWORD（与后端 .env 一致）
set -euo pipefail

FILE="${1:?用法: restore-mysql.sh <备份文件.sql.gz>}"
DB_HOST="${DB_HOST:-127.0.0.1}"
DB_PORT="${DB_PORT:-3306}"
DB_NAME="${DB_NAME:-saas_lifecycle}"
DB_USER="${DB_USER:-saas_user}"
: "${DB_PASSWORD:?必须通过环境变量提供 DB_PASSWORD}"

echo "[restore] 目标库 ${DB_NAME}@${DB_HOST}:${DB_PORT}，备份文件 ${FILE}"
read -r -p "[restore] 将覆盖现有数据，确认继续？(yes/no) " ok
[ "$ok" = "yes" ] || { echo "[restore] 已取消"; exit 1; }

# 恢复前先做一次安全备份
TS=$(date +%Y%m%d_%H%M%S)
SAFE="/tmp/${DB_NAME}_pre_restore_${TS}.sql.gz"
mysqldump -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASSWORD" \
  --single-transaction --routines "$DB_NAME" | gzip > "$SAFE"
echo "[restore] 恢复前快照已存 $SAFE"

gunzip -c "$FILE" | mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASSWORD" "$DB_NAME"
echo "[restore] 恢复完成。请重启后端并验证 /health 与登录。"
