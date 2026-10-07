import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const access = fs.readFileSync(new URL('../src/security/platformAccessGate.js', import.meta.url), 'utf8')
const provisioning = fs.readFileSync(new URL('../src/modules/platform/views/control/PlatformProvisioningView.vue', import.meta.url), 'utf8')

test('PLATFORM_DELIVERY canonical provisioning.manage reaches historical route keys', () => {
  assert.match(access, /normalized\.has\('provisioning\.manage'\)/)
  assert.match(access, /patterns\.add\('platform\.provision\.run\.view'\)/)
  assert.match(access, /patterns\.add\('platform\.onboarding\.view'\)/)
  assert.match(access, /duties\.has\('provisioning\.manage'\).*\/admin\/platform\/provisioning/s)
})

test('PLATFORM_OPERATIONS incident.manage reaches historical incident.view route key', () => {
  assert.match(access, /normalized\.has\('incident\.manage'\)/)
  assert.match(access, /patterns\.add\('platform\.incident\.view'\)/)
})

test('provisioning page keeps root-only destructive actions out of delegated delivery UI', () => {
  assert.match(provisioning, /const ROOT_ROLES = new Set\(\['PLATFORM_OWNER', 'PLATFORM_SUPER_ADMIN'\]\)/)
  assert.match(provisioning, /v-if="isRoot && row\.status === 'FAILED'"[^>]*@click\.stop="compensateStep\(row\)"/)
  assert.match(provisioning, /v-if="isRoot && \(row\.status === 'FAILED' \|\| row\.status === 'COMPENSATED'\)"[^>]*@click\.stop="flagManual\(row\)"/)
  assert.match(provisioning, /v-if="isRoot && !\['SUCCEEDED', 'CANCELLED', 'RUNNING'\]\.includes\(selected\.status\)"[^>]*@click="cancelJob"/)
  assert.match(provisioning, /if \(!this\.isRoot\) return toast\.error\('仅平台负责人\/超级管理员可执行补偿'\)/)
})

test('delegated delivery keeps normal create retry and resume actions visible', () => {
  assert.match(provisioning, /@click="submitCreate">提交开通/)
  assert.match(provisioning, /@click\.stop="retryStep\(row\)">重试/)
  assert.match(provisioning, /@click="resumeJob">续跑/)
})
