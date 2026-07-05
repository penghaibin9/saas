# MySQL 恢复脚本（Windows；与 backup-mysql.ps1 配套）。
# 用法：.\restore-mysql.ps1 -File C:\backups\saas_lifecycle_20260705.sql.gz
# 需要 mysql 客户端在 PATH；密码经环境变量 DB_PASSWORD 注入，不落脚本。
param(
  [Parameter(Mandatory = $true)][string]$File,
  [string]$DbHost = $(if ($env:DB_HOST) { $env:DB_HOST } else { "127.0.0.1" }),
  [int]$DbPort = $(if ($env:DB_PORT) { [int]$env:DB_PORT } else { 3306 }),
  [string]$DbName = $(if ($env:DB_NAME) { $env:DB_NAME } else { "saas_lifecycle" }),
  [string]$DbUser = $(if ($env:DB_USER) { $env:DB_USER } else { "saas_user" })
)
if (-not $env:DB_PASSWORD) { Write-Error "必须设置环境变量 DB_PASSWORD"; exit 1 }
if (-not (Test-Path $File)) { Write-Error "备份文件不存在：$File"; exit 1 }

Write-Host "[restore] 目标库 $DbName@${DbHost}:$DbPort，备份文件 $File"
$ok = Read-Host "[restore] 将覆盖现有数据，确认继续？(yes/no)"
if ($ok -ne "yes") { Write-Host "[restore] 已取消"; exit 1 }

# 恢复前快照
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$safe = Join-Path $env:TEMP "${DbName}_pre_restore_$ts.sql"
mysqldump -h $DbHost -P $DbPort -u $DbUser -p"$env:DB_PASSWORD" --single-transaction --routines $DbName | Out-File -Encoding utf8 $safe
Write-Host "[restore] 恢复前快照已存 $safe"

if ($File.EndsWith(".gz")) {
  # 需要 7z 或先手动解压
  $sql = $File -replace "\.gz$", ""
  if (-not (Test-Path $sql)) { & 7z x $File "-o$(Split-Path $File)" | Out-Null }
  Get-Content $sql -Raw | mysql -h $DbHost -P $DbPort -u $DbUser -p"$env:DB_PASSWORD" $DbName
} else {
  Get-Content $File -Raw | mysql -h $DbHost -P $DbPort -u $DbUser -p"$env:DB_PASSWORD" $DbName
}
Write-Host "[restore] 恢复完成。请重启后端并验证 /health 与登录。"
