import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const view = fs.readFileSync(path.join(root, 'src/views/academic/StudentGraduationAuditView.vue'), 'utf8')
const routes = fs.readFileSync(path.join(root, 'src/router/academicRoutes.js'), 'utf8')
const api = fs.readFileSync(path.join(root, 'src/services/portalApi.js'), 'utf8')

test('D-W5 student graduation route remains a dedicated academic truth surface', () => {
  assert.match(routes, /path:\s*['"]graduation['"]/)
  assert.match(routes, /StudentGraduationAuditView\.vue/)
  assert.match(api, /academicGraduationAudit\s*\(\)\s*\{[\s\S]*?\/portal\/academic\/graduation-audit/)
})

test('SYSTEM_ABNORMAL is explicit and can never inherit a green or generic formal label', () => {
  assert.match(view, /SYSTEM_ABNORMAL:\s*['"]正式预审存在阻断项['"]/)
  assert.match(view, /overallPassed\s*=\s*computed\(\(\)\s*=>\s*String\(progress\.value\.overall\s*\|\|\s*['"]['"]\)\.toUpperCase\(\)\s*===\s*['"]SYSTEM_PASSED['"]\)/)
  assert.doesNotMatch(view, /SYSTEM_ABNORMAL:\s*['"][^'"]*通过/)
})

test('non-PASS graduation items remain warning tone and UNKNOWN never becomes green', () => {
  assert.match(view, /itemResult\(item\)\s*===\s*['"]PASS['"]\s*\?\s*['"]success['"]\s*:\s*['"]warn['"]/)
  assert.match(view, /value\s*===\s*['"]PASS['"]\s*\?\s*['"]已通过['"]\s*:\s*value\s*===\s*['"]FAIL['"]\s*\?\s*['"]未达标['"]\s*:\s*['"]待核验['"]/)
  assert.match(view, /itemTone\(item\)[\s\S]*?itemResult\(item\)\s*===\s*['"]PASS['"]\s*\?\s*['"]is-pass['"]\s*:\s*['"]is-pending['"]/)
})
