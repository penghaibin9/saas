import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = process.cwd()
const read = (relativePath) => readFileSync(path.join(root, relativePath), 'utf8')

test('H5 dialog transform starts with an identifier so a preceding string cannot be called as a function', () => {
  const config = read('vite.config.js')
  const installer = read('src/services/h5InAppDialogInstaller.js')

  assert.match(config, /globalThis\.__schoolInAppModalInvoker\(uni\.showModal\)\(/)
  assert.match(config, /globalThis\.__schoolInAppActionSheetInvoker\(uni\.showActionSheet\)\(/)
  assert.doesNotMatch(config, /\(globalThis\.__schoolInAppModal \|\| uni\.showModal\)\(/)
  assert.match(installer, /typeof globalThis === 'undefined' \? null : globalThis/)
  assert.match(installer, /runtime\.__schoolInAppModalInvoker\s*=\s*\(fallback\)\s*=>\s*runtime\.__schoolInAppModal \|\| fallback/)
  assert.match(installer, /runtime\.__schoolInAppActionSheetInvoker\s*=\s*\(fallback\)\s*=>\s*runtime\.__schoolInAppActionSheet \|\| fallback/)
  assert.match(installer, /if \(typeof window === 'undefined' \|\| typeof document === 'undefined' \|\| window\[INSTALL_FLAG\]\) return/)
})
