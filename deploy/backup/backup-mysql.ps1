# 高校学生全生命周期管理平台 · MySQL 自动备份（Windows 服务器）
# 用法：先 setx DB_PASSWORD "你的密码"（或在任务计划里设环境变量），再用任务计划每天调用本脚本。
$ErrorActionPreference = "Stop"
$DB_HOST = "127.0.0.1"; $DB_PORT = "3306"; $DB_USER = "saas_user"; $DB_NAME = "saas_lifecycle"
$DB_PASSWORD = $env:DB_PASSWORD
if (-not $DB_PASSWORD) { Write-Error "请先设置环境变量 DB_PASSWORD"; exit 1 }
$BACKUP_DIR = "D:\backups\school-lifecycle"; $KEEP_DAYS = 14
New-Item -ItemType Directory -Force -Path $BACKUP_DIR | Out-Null
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$sql = Join-Path $BACKUP_DIR "db_${DB_NAME}_$ts.sql"
& mysqldump -h $DB_HOST -P $DB_PORT -u $DB_USER "-p$DB_PASSWORD" --single-transaction --quick --routines --triggers $DB_NAME > $sql
Compress-Archive -Path $sql -DestinationPath "$sql.zip" -Force; Remove-Item $sql
Write-Output "备份完成：$sql.zip"
Get-ChildItem $BACKUP_DIR -Filter "db_*.zip" | Where-Object { $_.LastWriteTime -lt (Get-Date).AddDays(-$KEEP_DAYS) } | Remove-Item
Write-Output "已清理 $KEEP_DAYS 天前旧备份。建议每月做一次恢复演练。"
