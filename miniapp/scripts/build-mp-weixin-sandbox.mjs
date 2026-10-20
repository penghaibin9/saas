import { spawnSync } from 'node:child_process'
import { existsSync, readFileSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'
import { runInNewContext } from 'node:vm'
import { optimizeWeixin } from './optimize-mp-weixin.mjs'

const root = fileURLToPath(new URL('../', import.meta.url))
const defaultApiBaseUrl = 'http://127.0.0.1:8000'

function sandboxApiBaseUrl(value = defaultApiBaseUrl) {
  const match = /^http:\/\/127\.0\.0\.1:([1-9]\d{0,4})\/?$/.exec(String(value))
  if (!match || Number(match[1]) > 65535) {
    throw new Error('微信沙箱接口地址必须为 http://127.0.0.1:端口，端口范围为 1 至 65535，不能包含路径或外部域名。')
  }
  return `http://127.0.0.1:${match[1]}`
}

export function sandboxBuildEnv(inherited = process.env) {
  // 只接受显式本机目标；未指定时保持既有端口。仅供本机开发者工具，不用于真机或发布。
  const apiBaseUrl = sandboxApiBaseUrl(inherited.VITE_API_BASE_URL || defaultApiBaseUrl)
  return { ...inherited, VITE_API_BASE_URL: apiBaseUrl, VITE_USE_MOCK: 'false' }
}

export function verifySandboxOutput(source, expectedApiBaseUrl = defaultApiBaseUrl) {
  const apiBaseUrl = sandboxApiBaseUrl(expectedApiBaseUrl)
  const output = { exports: {} }
  runInNewContext(source, output, { timeout: 1000 })
  const env = output.exports.ENV
  if (env?.apiBaseUrl !== apiBaseUrl || env.useMock !== false || env.allowMockFallback !== false) {
    throw new Error(`微信沙箱构建校验失败：接口必须与本次目标 ${apiBaseUrl} 一致，且禁止模拟数据及回退。`)
  }
}

export function configureSandboxProject(outputDir) {
  const path = resolve(outputDir, 'project.private.config.json')
  const config = existsSync(path) ? JSON.parse(readFileSync(path, 'utf8')) : {}
  // 仅本机沙箱产物允许访问 HTTP 回环地址；发布脚本仍强制开启域名校验。
  config.setting = { ...config.setting, urlCheck: false }
  writeFileSync(path, JSON.stringify(config, null, 2) + '\n')
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const buildEnv = sandboxBuildEnv()
  const result = spawnSync(process.execPath, [
    resolve(root, 'node_modules/@dcloudio/vite-plugin-uni/bin/uni.js'), 'build', '-p', 'mp-weixin'
  ], { cwd: root, env: buildEnv, stdio: 'inherit' })
  if (result.error) throw result.error
  if (result.status !== 0) process.exit(result.status || 1)
  verifySandboxOutput(readFileSync(resolve(root, 'dist/build/mp-weixin/config/env.js'), 'utf8'), buildEnv.VITE_API_BASE_URL)
  optimizeWeixin(resolve(root, 'dist/build/mp-weixin'))
  configureSandboxProject(resolve(root, 'dist/build/mp-weixin'))
  console.log(`微信沙箱构建已校验：本机接口 ${buildEnv.VITE_API_BASE_URL}，真实数据模式。请重新打开开发者工具项目以加载新包。`)
}
