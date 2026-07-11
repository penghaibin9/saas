# 学校试点上线前 · 静态预检（Windows / 演示机）
# 用法：powershell -File scripts/check/preflight-school-trial.ps1 -EnvFile backend/.env
# 不写死真实 IP/密码/密钥；只读 .env 与仓库文件。
param([string]$EnvFile = "backend/.env")
$fail = 0; $warn = 0
function Pass($m){ Write-Host "  [PASS] $m" }
function Warn($m){ Write-Host "  [WARN] $m"; $script:warn++ }
function Fail($m){ Write-Host "  [FAIL] $m"; $script:fail++ }
function GetV($k){ if(Test-Path $EnvFile){ (Select-String -Path $EnvFile -Pattern "^$k=" | Select-Object -Last 1) -replace "^.*?=", "" } }

Write-Host "== 预检开始：$EnvFile =="
if(-not (Test-Path $EnvFile)){
  Fail "未找到 $EnvFile（生产必须提供 .env）"
} else {
  if((GetV "APP_ENV") -eq "production"){ Pass "APP_ENV=production" } else { Warn "APP_ENV 非 production" }
  $dbg = GetV "DEBUG"; if($dbg -eq "false" -or [string]::IsNullOrEmpty($dbg)){ Pass "DEBUG 关闭" } else { Fail "DEBUG 应为 false" }
  $js = "" + (GetV "JWT_SECRET") + (GetV "JWT_SECRET_KEY")
  if($js -match "change-me|dev-secret"){ Fail "JWT_SECRET 仍是默认弱密钥" }
  elseif($js.Length -ge 32){ Pass "JWT_SECRET 长度充足" } else { Warn "JWT_SECRET 建议≥32位" }
  $cors = GetV "CORS_ORIGINS"; if([string]::IsNullOrWhiteSpace($cors) -or $cors -eq "*"){ Fail "CORS_ORIGINS 不能为空或 *" } else { Pass "CORS 已收敛" }
  if((GetV "MOCK_LOGIN_ENABLED") -eq "true"){ Fail "MOCK_LOGIN_ENABLED=true（正式前必须关闭）" } else { Pass "mock-login 未开启" }
  if((GetV "SMS_ENABLED") -eq "true"){ if((GetV "SMS_ACCESS_KEY_ID")){ Pass "SMS 已配置" } else { Warn "SMS_ENABLED=true 但未配密钥" } } else { Pass "SMS 默认关闭（占位）" }
}
if(Test-Path "deploy/nginx"){ if(Get-ChildItem "deploy/nginx" -Filter *.conf* -ErrorAction SilentlyContinue){ Pass "存在 nginx 配置模板" } else { Warn "未见 nginx 配置" } }
Write-Host "== 预检结束：FAIL=$fail WARN=$warn =="
if($fail -gt 0){ Write-Host "存在 FAIL 项，禁止上线"; exit 1 }
exit 0
