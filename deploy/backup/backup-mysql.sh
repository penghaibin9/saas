#!/usr/bin/env bash
# 高校学生全生命周期管理平台 · MySQL 自动备份脚本（Linux 服务器）
# 用法：chmod +x backup-mysql.sh && ./backup-mysql.sh
# 定时（每天 02:00）：crontab -e 加一行：
#   0 2 * * * /path/to/backup-mysql.sh >> /var/log/school-backup.log 2>&1
set -euo pipefail

# ── 配置（按实际改）──
DB_HOST="127.0.0.1"
DB_PORT="3306"
DB_USER="saas_user"
DB_NAME="saas_lifecycle"
# 密码从环境变量读，勿硬编码到脚本：export DB_PASSWORD=xxx
DB_PASSWORD="${DB_PASSWORD:?请先 export DB_PASSWORD}"
BACKUP_DIR="/var/backups/school-lifecycle"
KEEP_DAYS=14                     # 保留最近 14 天
UPLOAD_DIR="/var/www/school-lifecycle/uploads"   # 附件目录（可选一并备份）

mkdir -p "$BACKUP_DIR"
TS=$(date +%Y%m%d_%H%M%S)
SQL_FILE="$BACKUP_DIR/db_${DB_NAME}_${TS}.sql.gz"

echo "[$(date)] 开始备份数据库 $DB_NAME ..."
mysqldump -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASSWORD" \
  --single-transaction --quick --routines --triggers "$DB_NAME" | gzip > "$SQL_FILE"
echo "[$(date)] 数据库备份完成：$SQL_FILE ($(du -h "$SQL_FILE" | cut -f1))"

# 附件备份（存在才做）
if [ -d "$UPLOAD_DIR" ]; then
  tar -czf "$BACKUP_DIR/uploads_${TS}.tar.gz" -C "$(dirname "$UPLOAD_DIR")" "$(basename "$UPLOAD_DIR")"
  echo "[$(date)] 附件备份完成：uploads_${TS}.tar.gz"
fi

# 清理过期备份
find "$BACKUP_DIR" -name "db_*.sql.gz" -mtime +$KEEP_DAYS -delete
find "$BACKUP_DIR" -name "uploads_*.tar.gz" -mtime +$KEEP_DAYS -delete
echo "[$(date)] 已清理 $KEEP_DAYS 天前的旧备份。"

# ── 恢复演练（务必定期做一次，备份不验证=没有备份）──
# gunzip < db_xxx.sql.gz | mysql -u saas_user -p saas_lifecycle_restoretest
echo "[$(date)] 备份任务结束。建议每月做一次恢复演练验证可用性。"
