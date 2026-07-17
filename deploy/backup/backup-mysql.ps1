param(
  [string]$DbHost = $(if ($env:DB_HOST) { $env:DB_HOST } else { "127.0.0.1" }),
  [int]$DbPort = $(if ($env:DB_PORT) { [int]$env:DB_PORT } else { 3306 }),
  [string]$DbName = $(if ($env:DB_NAME) { $env:DB_NAME } else { "saas_lifecycle" }),
  [string]$DbUser = $(if ($env:DB_USER) { $env:DB_USER } else { "saas_user" }),
  [string]$BackupDir = $(if ($env:BACKUP_DIR) { $env:BACKUP_DIR } else { Join-Path $PSScriptRoot "data" }),
  [int]$KeepDays = $(if ($env:KEEP_DAYS) { [int]$env:KEEP_DAYS } else { 14 })
)
$ErrorActionPreference = "Stop"
if (-not $env:DB_PASSWORD) { throw "DB_PASSWORD must be set" }
New-Item -ItemType Directory -Force -Path $BackupDir | Out-Null
$resolvedDir = (Resolve-Path -LiteralPath $BackupDir).Path
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$sql = Join-Path $resolvedDir "db_${DbName}_${timestamp}.sql"
$zip = "${sql}.zip"

$oldMysqlPwd = $env:MYSQL_PWD
try {
  $env:MYSQL_PWD = $env:DB_PASSWORD
  & mysqldump -h $DbHost -P $DbPort -u $DbUser --single-transaction --quick `
    --routines --events --triggers --hex-blob --default-character-set=utf8mb4 `
    --source-data=2 "--result-file=$sql" $DbName
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $sql) -or (Get-Item $sql).Length -eq 0) {
    throw "mysqldump failed or produced an empty file"
  }
  Compress-Archive -LiteralPath $sql -DestinationPath $zip -Force
  Remove-Item -LiteralPath $sql
  (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash + "  " + (Split-Path $zip -Leaf) |
    Set-Content -Encoding ascii -LiteralPath "${zip}.sha256"
} finally {
  $env:MYSQL_PWD = $oldMysqlPwd
}

$cutoff = (Get-Date).AddDays(-$KeepDays)
Get-ChildItem -LiteralPath $resolvedDir -File |
  Where-Object { $_.Name -like "db_*.sql.zip*" -and $_.LastWriteTime -lt $cutoff } |
  Remove-Item -Force
Write-Output "Backup complete: $zip"
