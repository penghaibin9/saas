import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const read=(p)=>fs.readFileSync(new URL(p,import.meta.url),'utf8')
const installer=read('../src/services/h5BrowserAuthInstaller.js')
const main=read('../src/main.js')
const request=read('../src/services/request.js')
const env=read('../src/config/env.js')
const vite=read('../vite.config.js')

test('H5 browser auth installer loads before App and request consumers',()=>{
  const installerAt=main.indexOf("import './services/h5BrowserAuthInstaller'")
  const appAt=main.indexOf("import App from './App.vue'")
  assert.ok(installerAt>=0)
  assert.ok(appAt>installerAt)
})

test('H5 bearer credentials are removed from browser-readable persistent storage',()=>{
  assert.match(installer,/const TOKEN_KEY = 'gx_token_v1'/)
  assert.match(installer,/const REFRESH_KEY = 'gx_refresh_v1'/)
  assert.match(installer,/originalRemove\?\.\(TOKEN_KEY\)/)
  assert.match(installer,/originalRemove\?\.\(REFRESH_KEY\)/)
  assert.match(installer,/window\.localStorage\.removeItem\(TOKEN_KEY\)/)
  assert.match(installer,/window\.localStorage\.removeItem\(REFRESH_KEY\)/)
  assert.match(installer,/if \(key === TOKEN_KEY\) return accessToken/)
  assert.match(installer,/if \(key === REFRESH_KEY\) return channel\(\) \? REFRESH_SENTINEL : ''/)
  assert.doesNotMatch(installer,/originalSet\(TOKEN_KEY/)
  assert.doesNotMatch(installer,/originalSet\(REFRESH_KEY/)
})

test('H5 rewrites login refresh switch-role and logout to existing browser session transport',()=>{
  for(const path of ['browser-login','browser-refresh','browser-switch-role','browser-logout']){
    assert.match(installer,new RegExp(path))
  }
  assert.match(installer,/X-Browser-Session-Id/)
  assert.match(installer,/withCredentials = true/)
  assert.match(installer,/clientType === 'STUDENT_MINI'/)
  assert.match(installer,/clientType: 'STUDENT_PC'/)
})

test('student H5 password CAPTCHA uses the same browser clientType as final login without touching WX_BIND',()=>{
  assert.ok(installer.includes("const isCaptcha = /\\/api\\/v1\\/auth\\/captcha"))
  assert.ok(installer.includes("scene === 'PASSWORD_LOGIN' && clientType === 'STUDENT_MINI'"))
  assert.ok(installer.includes("next.data = { ...(next.data || {}), clientType: 'STUDENT_PC' }"))
  assert.ok(installer.includes('WX_BIND stays'))
})

test('native miniapp request implementation remains available and installer is H5 gated',()=>{
  assert.match(installer,/import \{ uni as h5Uni \} from '@dcloudio\/uni-h5'/)
  assert.match(installer,/typeof window !== 'undefined'/)
  assert.match(installer,/typeof document !== 'undefined'/)
  assert.match(installer,/typeof h5Uni !== 'undefined'/)
  assert.match(installer,/const runtimeUni = h5Uni/)
  assert.match(installer,/if \(isH5\)/)
  assert.match(request,/realRequest\('\/auth\/refresh'/)
  assert.match(request,/setRefreshToken/)
})

test('H5 refresh sentinel is non-secret and only preserves the existing single-flight branch',()=>{
  assert.match(installer,/REFRESH_SENTINEL = '__HTTPONLY_BROWSER_REFRESH__'/)
  assert.match(installer,/if \(isRefresh\) next\.data = \{\}/)
  assert.match(request,/if \(!snapshot\.refreshToken\)/)
  assert.match(request,/if \(_refreshing && _refreshing\.generation === expectedGeneration\)/)
})

test('shared request layer accepts valid JSON text from H5 but keeps malformed responses fail-closed',()=>{
  assert.match(request,/function normalizeJsonResponseBody\(value\)/)
  assert.match(request,/return JSON\.parse\(text\)/)
  assert.match(request,/const body = normalizeJsonResponseBody\(res\.data\)/)
  assert.match(request,/code: 'BAD_RESPONSE'/)
})

test('local H5 uses a same-origin API proxy while native miniapp keeps its explicit origin',()=>{
  assert.match(env,/BUILD_DEV && typeof window !== 'undefined'/)
  assert.doesNotMatch(env,/(?<![\w.])env\.DEV\b/)
  assert.match(env,/localhost\|127\\\.0\\\.0\\\.1/)
  assert.match(vite,/['"]\/api['"]\s*:/)
  assert.match(vite,/VITE_DEV_API_PROXY_TARGET/)
  assert.match(vite,/http:\/\/127\.0\.0\.1:8000/)
})
