import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import test from 'node:test'

const runtimeUrl = new URL('../src/services/officialWechatRuntime.js', import.meta.url)
const indexUrl = new URL('../index.html', import.meta.url)
const nginxUrl = new URL('../../deploy/nginx/security-http.conf', import.meta.url)
const systemdEnvUrl = new URL('../../deploy/env/backend.systemd.env.example', import.meta.url)

const [runtimeSource, indexSource, nginxSource, systemdEnvSource] = await Promise.all([
  readFile(runtimeUrl, 'utf8'),
  readFile(indexUrl, 'utf8'),
  readFile(nginxUrl, 'utf8'),
  readFile(systemdEnvUrl, 'utf8')
])

test('official site keeps WeChat WebView and iOS SPA compatibility contracts', () => {
  assert.match(indexSource, /viewport-fit=cover/)
  assert.match(runtimeSource, /MicroMessenger/)
  assert.match(runtimeSource, /iPhone\|iPad\|iPod/)
  assert.match(runtimeSource, /WECHAT_ENTRY_URL/)
  assert.match(runtimeSource, /resolveWechatSignatureUrl/)
  assert.match(runtimeSource, /updateAppMessageShareData/)
  assert.match(runtimeSource, /updateTimelineShareData/)
})

test('production CSP allows only the pinned WeChat SDK origin needed by the micro-site', () => {
  assert.match(runtimeSource, /https:\/\/res\.wx\.qq\.com\/open\/js\/jweixin-1\.6\.0\.js/)
  const effectiveNginx = nginxSource
    .split('\n')
    .filter((line) => !line.trimStart().startsWith('#'))
    .join('\n')
  assert.match(effectiveNginx, /script-src[^;]*https:\/\/res\.wx\.qq\.com/)
  assert.doesNotMatch(effectiveNginx, /'unsafe-eval'/)
})

test('systemd production template exposes separate Official Account credentials', () => {
  assert.match(systemdEnvSource, /^WECHAT_OFFICIAL_JS_SDK_ENABLED=false$/m)
  assert.match(systemdEnvSource, /^WECHAT_OFFICIAL_APP_ID=$/m)
  assert.match(systemdEnvSource, /^WECHAT_OFFICIAL_APP_SECRET=$/m)
  assert.match(systemdEnvSource, /^WECHAT_OFFICIAL_ALLOWED_HOSTS=hnyueke\.com,www\.hnyueke\.com$/m)
  assert.match(systemdEnvSource, /与微信小程序 WX_APPID\/WX_SECRET 完全分离/)
})
