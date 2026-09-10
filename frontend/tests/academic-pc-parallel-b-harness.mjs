import { readFileSync } from 'node:fs'
import vm from 'node:vm'

// Execute the page's actual Options API methods, with only its I/O imports replaced.
export function page(name, dependencies = {}, props = {}) {
  const source = readFileSync(new URL(`../src/modules/academicAffairs/views/${name}.vue`, import.meta.url), 'utf8')
  const script = source.match(/<script>([\s\S]*?)<\/script>/)[1]
    .replace(/import\s+([\s\S]*?)\s+from\s+['"][^'"]+['"]/g, (_, binding) => {
      const value = binding.trim().replace(/\s+as\s+/g, ': ')
      return `const ${value} = dependencies${value.startsWith('{') ? '' : '.' + value}`
    }).replace('export default', 'component =')
  const sandbox = { dependencies: { currentUserFromToken: () => ({ userId: 'teacher-a' }), toast: { success() {}, error() {} }, ...dependencies } }
  vm.runInNewContext(script, sandbox)
  const definition = sandbox.component
  const state = { $route: { query: {}, params: {} }, $router: { replace: async () => {}, push: async () => {} }, ...props }
  Object.assign(state, definition.data.call(state), definition.methods)
  for (const [key, getter] of Object.entries(definition.computed || {})) Object.defineProperty(state, key, { get: () => getter.call(state) })
  return { state, definition }
}

export function deferred() {
  let resolve, reject
  const promise = new Promise((done, fail) => { resolve = done; reject = fail })
  return { promise, resolve, reject }
}
