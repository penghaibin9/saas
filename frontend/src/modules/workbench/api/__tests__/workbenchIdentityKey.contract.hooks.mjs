import path from 'node:path'
import { pathToFileURL } from 'node:url'

let settings = null

export function initialize(data) {
  settings = data
}

export async function resolve(specifier, context, nextResolve) {
  if (!settings) return nextResolve(specifier, context)
  if (specifier === '@/services/http') {
    return { shortCircuit: true, url: settings.mockHttpUrl }
  }
  if (specifier === '@/services/http/client') {
    return { shortCircuit: true, url: settings.mockClientUrl }
  }
  if (specifier.startsWith('@/')) {
    let absolute = path.join(settings.frontendRoot, 'src', specifier.slice(2))
    if (!path.extname(absolute)) absolute += '.js'
    return { shortCircuit: true, url: pathToFileURL(absolute).href }
  }
  // 源码里的相对导入沿用 Vite 惯例省略 .js 后缀（如 '../config/todoTypedRouteBridge'），
  // 裸 Node ESM 解析要求显式后缀，这里补一次兜底重试，不改动被测源码。
  try {
    return await nextResolve(specifier, context)
  } catch (err) {
    if (err && err.code === 'ERR_MODULE_NOT_FOUND' && !path.extname(specifier)) {
      return nextResolve(`${specifier}.js`, context)
    }
    throw err
  }
}
