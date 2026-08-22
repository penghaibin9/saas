import path from 'node:path'
import { pathToFileURL } from 'node:url'

let settings = null

export function initialize(data) {
  settings = data
}

export async function resolve(specifier, context, nextResolve) {
  if (!settings) return nextResolve(specifier, context)
  if (specifier === '@/services/http/client') {
    return { shortCircuit: true, url: settings.mockClientUrl }
  }
  if (specifier.startsWith('@/')) {
    let absolute = path.join(settings.frontendRoot, 'src', specifier.slice(2))
    if (!path.extname(absolute)) absolute += '.js'
    return { shortCircuit: true, url: pathToFileURL(absolute).href }
  }
  try {
    return await nextResolve(specifier, context)
  } catch (err) {
    if (err && err.code === 'ERR_MODULE_NOT_FOUND' && !path.extname(specifier)) {
      return nextResolve(`${specifier}.js`, context)
    }
    throw err
  }
}
