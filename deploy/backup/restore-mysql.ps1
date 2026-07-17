param(
  [Parameter(Mandatory = $true)][string]$File,
  [string]$DbHost = $(if ($env:DB_HOST) { $env:DB_HOST } else { "127.0.0.1" }),
  [int]$DbPort = $(if ($env:DB_PORT) { [int]$env:DB_PORT } else { 3306 }),
  [string]$DbName = $(if ($env:DB_NAME) { $env:DB_NAME } else { "saas_lifecycle" }),
  [string]$DbUser = $(if ($env:DB_USER) { $env:DB_USER } else { "saas_user" })
)
$ErrorActionPreference = "Stop"
if (-not $env:DB_PASSWORD) { throw "DB_PASSWORD must be set" }
$backup = (Resolve-Path -LiteralPath $File).Path
$hashFile = "${backup}.sha256"
if (Test-Path -LiteralPath $hashFile) {
  $expected = ((Get-Content -LiteralPath $hashFile -Raw).Trim() -split '\s+')[0]
  $actual = (Get-FileHash -Algorithm SHA256 -LiteralPath $backup).Hash
  if ($expected -ne $actual) { throw "Backup SHA256 verification failed" }
}

Write-Host "[restore] target=${DbName}@${DbHost}:$DbPort file=$backup"
$confirmation = Read-Host "[restore] type RESTORE-$DbName to continue"
if ($confirmation -ne "RESTORE-$DbName") { Write-Host "[restore] cancelled"; exit 1 }

$workDir = Join-Path ([System.IO.Path]::GetTempPath()) "school-restore-$([guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $workDir | Out-Null
$oldMysqlPwd = $env:MYSQL_PWD
try {
  $env:MYSQL_PWD = $env:DB_PASSWORD
  $timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
  $safetyCopy = Join-Path $workDir "${DbName}_pre_restore_${timestamp}.sql"
  & mysqldump -h $DbHost -P $DbPort -u $DbUser --single-transaction --quick `
    --routines --events --triggers "--result-file=$safetyCopy" $DbName
  if ($LASTEXITCODE -ne 0) { throw "pre-restore safety backup failed" }

  if ($backup.EndsWith(".zip", [StringComparison]::OrdinalIgnoreCase)) {
    Expand-Archive -LiteralPath $backup -DestinationPath $workDir -Force
    $sqlFile = Get-ChildItem -LiteralPath $workDir -Filter "*.sql" |
      Where-Object { $_.FullName -ne $safetyCopy } | Select-Object -First 1
    if (-not $sqlFile) { throw "No SQL file found in backup archive" }
    $sqlPath = $sqlFile.FullName
  } elseif ($backup.EndsWith(".sql", [StringComparison]::OrdinalIgnoreCase)) {
    $sqlPath = $backup
  } else {
    throw "Windows restore supports .sql.zip or .sql backups"
  }

  Get-Content -LiteralPath $sqlPath -Raw | & mysql -h $DbHost -P $DbPort -u $DbUser $DbName
  if ($LASTEXITCODE -ne 0) { throw "mysql restore failed" }
  & mysql -h $DbHost -P $DbPort -u $DbUser -Nse `
    "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='$DbName'"
  Write-Host "[restore] complete; pre-restore safety copy remains at $safetyCopy"
  $workDir = $null  # preserve safety copy for operator-controlled cleanup
} finally {
  $env:MYSQL_PWD = $oldMysqlPwd
  if ($workDir -and (Test-Path -LiteralPath $workDir)) {
    $resolvedWork = (Resolve-Path -LiteralPath $workDir).Path
    $resolvedTemp = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
    if ($resolvedWork.StartsWith($resolvedTemp, [StringComparison]::OrdinalIgnoreCase)) {
      Remove-Item -LiteralPath $resolvedWork -Recurse -Force
    }
  }
}
