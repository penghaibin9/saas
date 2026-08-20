import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const read=(p)=>fs.readFileSync(new URL(p,import.meta.url),'utf8')
const installer=read('../src/services/h5BrowserAuthInstaller.js')
const main=read('../src/main.js')
const request=read('../src/services/request.js')

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

test('native miniapp request implementation remains available and installer is H5 gated',()=>{
  assert.match(installer,/typeof window !== 'undefined'/)
  assert.match(installer,/typeof document !== 'undefined'/)
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
