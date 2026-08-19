import { fileURLToPath } from 'node:url'
import { dirname, resolve, sep } from 'node:path'
import { defineConfig } from 'vite'
import uni from '@dcloudio/vite-plugin-uni'

const here = dirname(fileURLToPath(import.meta.url))
const MOCK_ROOT = resolve(here, 'src', 'mock') + sep

/**
 * V3 S1.5：生产构建不得把 mock 数据体打进小程序包。
 *
 * config/env.js 已把生产构建的 useMock 与 allowMockFallback 双双硬编码为 false，
 * 因此 realFirst()/realFirstStrict() 在生产里永远不会执行 mockFn —— 整棵 src/mock
 * 数据体在生产是可证明的死代码，却仍会被 uni-app 按源码路径原样发进主包。
 *
 * uni-app 的 mp 构建自己解析模块说明符（resolveId 收不到 '@/mock'），所以这里用
 * transform 钩子：保留每个 mock 模块的导出名与模块形状，只把数据体换成冻结空数组。
 * 空数组同时支持 M.x.y（undefined）与 M.x.filter(...)，即使生产里有已不可达的分支被
 * 误调用也不会抛形状错误，同时保证“生产包里读不到任何 mock 业务数据”。
 *
 * 开发构建（VITE_USE_MOCK=true 的纯 mock 本地模式）不受影响。
 */
function stripMockPayloadInProduction() {
  let active = false
  return {
    name: 'miniapp-v3-strip-mock-payload-in-production',
    enforce: 'pre',
    config(_config, env) {
      active = env.command === 'build' && env.mode !== 'development'
    },
    transform(code, id) {
      if (!active) return null
      const file = id.split('?')[0]
      if (!file.startsWith(MOCK_ROOT)) return null

      const named = new Set()
      for (const match of code.matchAll(/^export\s+const\s+([A-Za-z0-9_$]+)/gm)) named.add(match[1])
      for (const match of code.matchAll(/^export\s*\{([^}]*)\}/gm)) {
        for (const clause of match[1].split(',')) {
          const parts = clause.trim().split(/\s+as\s+/)
          const name = (parts[1] || parts[0] || '').trim()
          if (name && name !== 'default') named.add(name)
        }
      }
      const hasDefault = /^export\s+default\b/m.test(code)
      if (!named.size && !hasDefault) return null

      const lines = ['/* miniapp V3 S1.5：生产构建已剥离 mock 数据体，仅保留同名空导出 */']
      for (const name of named) lines.push(`export const ${name} = Object.freeze([])`)
      if (hasDefault) lines.push('export default Object.freeze([])')
      return { code: lines.join('\n') + '\n', map: null }
    }
  }
}

// uni-app + Vue3 独立工程配置。仅服务小程序端，不影响 PC frontend。
export default defineConfig({
  plugins: [stripMockPayloadInProduction(), uni()]
})
