import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const frontendRoot = path.resolve(here, '..')
const repoRoot = path.resolve(frontendRoot, '..')
const readFront = (p) => fs.readFileSync(path.join(frontendRoot, p), 'utf8')
const readRepo = (p) => fs.readFileSync(path.join(repoRoot, p), 'utf8')

const state = readFront('src/modules/system/utils/identityImportState.js')
const api = readFront('src/modules/system/api/dataExchange.api.js')
const dialog = readFront('src/modules/system/components/ImportDialog.vue')
const student = readFront('src/modules/system/views/SystemStudentImportView.vue')
const teacher = readFront('src/modules/system/views/SystemTeacherImportView.vue')
const workspace = readFront('src/modules/system/components/workspace/IdentityImportWorkspace.vue')
const controller = readFront('src/modules/system/utils/identityImportWorkspace.js')
const worker = readRepo('backend/app/workers/identity_import_worker.py')
const service = readRepo('deploy/systemd/school-lifecycle-identity-import.service')

test('P-01 processing states never masquerade as confirmable zero-error preview', () => {
  for (const status of ['SCANNING', 'WORKER_CLAIMED', 'PARSING']) assert.match(state, new RegExp(`['"]${status}['"]`))
  assert.match(state, /identityImportStatus\(job\) === 'VALIDATED'/)
  assert.match(state, /Number\(job\?\.invalidRows \?\? job\?\.invalid \?\? 0\) === 0/)
  assert.match(state, /Number\(job\?\.validRows \?\? job\?\.valid \?\? 0\) > 0/)
  assert.match(state, /const invalid = countsReady \?[^\n]+: null/)
  assert.match(dialog, /return canConfirmIdentityImport\(this\.preview\)/)
  assert.match(dialog, /此阶段不会把缺失计数当作 0/)
})

test('P-01 browser polling is pure-read and confirm re-reads current server state', () => {
  assert.match(api, /let current = await this\.getImport\(jobId, context\)/)
  assert.match(api, /while \(isIdentityImportProcessing\(current\)\)/)
  assert.match(api, /current = await this\.getImport\(jobId, context\)/)
  assert.match(api, /getImport\(jobId, context = \{\}\)[\s\S]*?request\(`\/data-exchange\/imports\/\$\{jobId\}`/)
  assert.match(student, /kind="students"/)
  assert.match(teacher, /kind="teachers"/)
  for (const view of [student, teacher]) {
    assert.match(view, /IdentityImportWorkspace/)
    assert.match(view, /canLeave\(to\)/)
  }
  assert.match(workspace, /createImportController/)
  assert.match(workspace, /api: dataExchangeApi/)
  assert.match(controller, /const current = await api\.getImport\(jobId\)/)
  assert.match(controller, /!canConfirmIdentityImport\(current\)/)
  assert.match(controller, /confirmImport\(jobId, current\.version\)/)
  assert.match(controller, /reviewFingerprint\(current\) !== approved/)
  assert.match(controller, /state\.uncertain = true/)
})

test('P-01 canonical worker exclusively claims durable identity jobs', () => {
  assert.match(worker, /python -m app\.workers\.identity_import_worker/)
  assert.match(worker, /\.with_for_update\(skip_locked=True\)/)
  assert.match(worker, /CLAIMED = "WORKER_CLAIMED"/)
  assert.match(worker, /process_next_identity_import/)
  assert.match(worker, /worker_claimed=True/)
})

test('P-01 production process manager starts and restarts the canonical identity worker', () => {
  assert.match(service, /^WorkingDirectory=\/opt\/school-lifecycle\/current\/backend$/m)
  assert.match(service, /^EnvironmentFile=\/etc\/school-lifecycle\/backend\.env$/m)
  assert.match(service, /^ExecStart=\/opt\/school-lifecycle\/current\/backend\/\.venv\/bin\/python -m app\.workers\.identity_import_worker$/m)
  assert.match(service, /^Restart=always$/m)
  assert.match(service, /^NoNewPrivileges=true$/m)
  assert.match(service, /^WantedBy=multi-user\.target$/m)
})
