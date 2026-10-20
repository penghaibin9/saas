import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const root = fileURLToPath(new URL('../', import.meta.url))

export function defaultWeixinBuildArgs(env = process.env) {
  // CI 继续验证生产编译；本机日常构建必须保留沙箱接口。
  return env.CI && env.CI !== 'false'
    ? [resolve(root, 'node_modules/@dcloudio/vite-plugin-uni/bin/uni.js'), 'build', '-p', 'mp-weixin']
    : [resolve(root, 'scripts/build-mp-weixin-sandbox.mjs')]
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const result = spawnSync(process.execPath, defaultWeixinBuildArgs(), { cwd: root, stdio: 'inherit' })
  if (result.error) throw result.error
  process.exit(result.status || (result.signal ? 1 : 0))
}
