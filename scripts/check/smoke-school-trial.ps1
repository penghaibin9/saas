# 学校试点 · 部署后冒烟检查（Windows / 演示机；需服务已启动）
# 用法：powershell -File scripts/check/smoke-school-trial.ps1 -BaseUrl http://localhost:8000
# 不写死真实 IP/密钥。
param([string]$BaseUrl = "http://localhost:8000")
$fail = 0
function Pass($m){ Write-Host "  [PASS] $m" }
function Fail($m){ Write-Host "  [FAIL] $m"; $script:fail++ }
function Biz($url){ try { (Invoke-RestMethod -Uri $url -Method Get -TimeoutSec 8).code } catch { -1 } }
function Http($url){ try { (Invoke-WebRequest -Uri $url -Method Get -TimeoutSec 8 -UseBasicParsing).StatusCode } catch { if($_.Exception.Response){ [int]$_.Exception.Response.StatusCode } else { -1 } } }

Write-Host "== 冒烟检查：$BaseUrl =="
if((Http "$BaseUrl/health") -eq 200){ Pass "/health 200" } else { Fail "/health 不可达" }
if((Biz "$BaseUrl/health/ready") -eq 0){ Pass "/health/ready 就绪" } else { Fail "/health/ready 异常" }
$m = Biz "$BaseUrl/api/v1/mobile/me/overview"; if($m -eq 401001){ Pass "未登录 mobile → 401" } else { Fail "未登录 mobile 未拦截(code=$m)" }
$s = Biz "$BaseUrl/api/v1/stats/overview"; if($s -eq 401001 -or $s -eq 403001){ Pass "stats 需鉴权(code=$s)" } else { Fail "stats 未鉴权(code=$s)" }
$d = Http "$BaseUrl/docs"; if($d -eq 404){ Pass "/docs 已关闭(生产)" } else { Write-Host "  [INFO] /docs=$d（非生产可开）" }
if($BaseUrl -match "localhost|127.0.0.1"){ Write-Host "  [INFO] 本地地址，生产请换真实域名" } else { Pass "BASE 非 localhost" }
Write-Host "== 冒烟结束：FAIL=$fail =="
if($fail -gt 0){ exit 1 }
exit 0
