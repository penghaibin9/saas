# 备份文件检查（Windows）：存在性 + 新鲜度 + 数量。不写死密码/路径。
# 用法：powershell -File scripts/check/check-backup-files.ps1 -Dir C:\backups\school-lifecycle
param([string]$Dir = "C:\backups\school-lifecycle", [int]$MaxAgeHours = 26)
$fail = 0
Write-Host "== 备份检查：$Dir =="
if(-not (Test-Path $Dir)){ Write-Host "  [FAIL] 备份目录不存在"; exit 1 }
$latest = Get-ChildItem $Dir -Filter *.sql.gz -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if(-not $latest){ Write-Host "  [FAIL] 无 .sql.gz 备份文件"; exit 1 }
Write-Host "  最新备份：$($latest.FullName)"
$ageH = [int]((Get-Date) - $latest.LastWriteTime).TotalHours
if($ageH -le $MaxAgeHours){ Write-Host "  [PASS] 新鲜度 ${ageH}h ≤ ${MaxAgeHours}h" } else { Write-Host "  [FAIL] 最新备份已 ${ageH}h，超期（备份任务可能没跑）"; $fail++ }
$cnt = (Get-ChildItem $Dir -Filter *.sql.gz).Count
Write-Host "  备份文件数：$cnt"
if($cnt -ge 1){ Write-Host "  [PASS] 存在备份" } else { Write-Host "  [FAIL] 无备份"; $fail++ }
Write-Host "  [INFO] gzip 完整性建议用 Linux 端 'gzip -t' 或 7-Zip 校验"
Write-Host "== 结束：FAIL=$fail =="
if($fail -gt 0){ exit 1 }
exit 0
