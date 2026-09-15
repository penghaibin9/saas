import { spawnSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { runInNewContext } from 'node:vm'

const root = fileURLToPath(new URL('../', import.meta.url))
const apiBaseUrl = 'http://127.0.0.1:8000'

export function sandboxBuildEnv(inherited = process.env) {
  // 显式覆盖发布环境和父进程配置；仅供本机开发者工具，不用于真机或发布。
  return { ...inherited, VITE_API_BASE_URL: apiBaseUrl, VITE_USE_MOCK: 'false' }
}

export function verifySandboxOutput(source) {
  const output = { exports: {} }
  runInNewContext(source, output, { timeout: 1000 })
  const env = output.exports.ENV
  if (env?.apiBaseUrl !== apiBaseUrl || env.useMock !== false || env.allowMockFallback !== false) {
    throw new Error('微信沙箱构建校验失败：接口必须为本机 8000，且禁止模拟数据及回退。')
  }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = spawnSync(process.execPath, [
    resolve(root, 'node_modules/@dcloudio/vite-plugin-uni/bin/uni.js'), 'build', '-p', 'mp-weixin'
  ], { cwd: root, env: sandboxBuildEnv(), stdio: 'inherit' })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status || 1)
  verifySandboxOutput(readFileSync(resolve(root, 'dist/build/mp-weixin/config/env.js'), 'utf8'))
  console.log('微信沙箱构建已校验：本机接口 8000，真实数据模式。请重新打开开发者工具项目以加载新包。')
}
