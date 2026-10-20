import assert from 'node:assert/strict'
import fs from 'node:fs'
import test from 'node:test'
import { deferred, optionsInstance } from './platform-workspace-test-support.mjs'

const catalog = fs.readFileSync(new URL('../src/modules/platform/platformManagementCatalog.js', import.meta.url), 'utf8')
const routes = fs.readFileSync(new URL('../src/modules/platform/platform.routes.js', import.meta.url), 'utf8')
const templateApi = fs.readFileSync(new URL('../src/modules/platform/api/productIam.api.js', import.meta.url), 'utf8')
const templateView = '../src/modules/platform/views/control/PlatformProductIamView.vue'

const draft = () => ({ templateCode: 'college_admin', id: '99', version: 0, permissionDigest: 'digest', reason: '学院权限收口', permissionCodes: [], impact: { sourceDigest: 'source', navigationDigest: 'navigation' } })
const publishedRow = (status = 'DRAFT') => ({ id: '99', version: 0, permissionDigest: 'digest', publishStatus: status })
const makeTemplatePage = (api, security = { stepUpMfa: async () => ({ accessToken: 'step-up-token', expiresIn: 600 }) }) => {
  const result = optionsInstance(templateView, { templateDraft: draft(), templateMfaCode: '123456' }, {
    productIamApi: api, platformSecurityOpsApi: security,
    platformEnumLabel: value => value, platformStatusLabel: value => value
  })
  result.state.load = async () => {}
  return result
}

const retired = [
  'tenant-lifecycle',
  'tenant-transitions',
  'tenant-contacts',
  'products',
  'init-templates',
  'role-templates',
  'releases',
  'support-tickets',
  'support-sessions',
  'tenant-health'
]

test('P1-09 roadmap and production platform catalogs are separated', () => {
  assert.match(catalog, /PLATFORM_MANAGEMENT_ROADMAP_CATALOG/)
  assert.match(catalog, /group\.items\.filter\(\(item\) => item\.view !== 'capability'\)/)
  assert.match(catalog, /PLATFORM_CAPABILITY_ONLY_KEYS/)
})

test('P1-09 production platform routes no longer render PlatformCapabilityView', () => {
  assert.doesNotMatch(routes, /PlatformCapabilityView\.vue/)
  for (const path of retired) {
    const escaped = path.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
    const block = new RegExp(`path: '${escaped}'[\\s\\S]{0,360}?redirect: '/admin/platform/`)
    assert.match(routes, block, `${path} must remain compatibility redirect only`)
  }
})

test('role template publish uses a request-scoped step-up token without auth refresh retry', async () => {
  assert.match(templateApi, /publishTemplate: \(code, id, body, mfaAccessToken\)/)
  assert.match(templateApi, /auth: false, noAuthRetry: true/)
  assert.match(templateApi, /Authorization: `Bearer \$\{mfaAccessToken\}`/)
  let publishes = 0
  const { state } = makeTemplatePage({ publishTemplate: async (code, id, body, token) => {
    publishes += 1
    assert.equal(code, 'college_admin')
    assert.equal(id, '99')
    assert.equal(body.expectedVersion, 0)
    assert.equal(token, 'step-up-token')
    return { code: 0 }
  } })
  await state.publishTemplateDraft()
  assert.equal(publishes, 1)
  assert.equal(state.templateMfaCode, '')
  assert.equal(state.templateDraft, null)
  assert.equal(state.saving, '')
  assert.equal('mfaToken' in state, false)
})

test('switching template during dynamic-code verification cancels the pending publish', async () => {
  const pending = deferred()
  let publishes = 0
  const { state } = makeTemplatePage({ publishTemplate: async () => { publishes += 1; return { code: 0 } } }, { stepUpMfa: () => pending.promise })
  const operation = state.publishTemplateDraft()
  state.selectTemplate({ templateCode: 'teacher' })
  pending.resolve({ accessToken: 'step-up-token', expiresIn: 600 })
  await operation
  assert.equal(publishes, 0)
  assert.equal(state.templateMfaCode, '')
  assert.equal(state.templateDraft, null)
})

test('a sent publish and its uncertain receipt keep the same draft open for readback', async () => {
  const started = deferred()
  const receipt = deferred()
  const { state } = makeTemplatePage({
    publishTemplate: () => { started.resolve(); return receipt.promise },
    templateVersions: async () => ({ code: 0, data: { items: [publishedRow()] } }),
    templateImpact: async () => ({ code: 0, data: { sourceDigest: 'source', navigationDigest: 'navigation' } })
  })
  const original = state.templateDraft
  const operation = state.publishTemplateDraft()
  await started.promise
  assert.equal(state.publishCheckRequired, true)
  state.selectTemplate({ templateCode: 'teacher' })
  state.startTemplateDraft({ templateCode: 'teacher' })
  state.closeSelectedTemplate()
  state.closeTemplateDraft()
  assert.equal(state.templateDraft, original)
  assert.equal(state.templatePublishEpoch, 1)
  receipt.resolve({ code: 503002, message: '请求超时', httpStatus: 0 })
  await operation
  assert.equal(state.publishCheckRequired, true)
  state.closeTemplateDraft()
  assert.equal(state.templateDraft, original)
  assert.equal(state.templateMfaCode, '')
})

test('uncertain publish receipt requires version and impact readback before a new command', async () => {
  let publishes = 0
  let impacts = 0
  const api = {
    publishTemplate: async () => { publishes += 1; return { code: 503002, message: '请求超时', httpStatus: 0 } },
    templateVersions: async () => ({ code: 0, data: { items: [publishedRow()] } }),
    templateImpact: async () => { impacts += 1; return { code: 0, data: { sourceDigest: 'source', navigationDigest: 'navigation' } } }
  }
  const { state } = makeTemplatePage(api)
  await state.publishTemplateDraft()
  assert.equal(impacts, 1)
  assert.equal(state.publishCheckRequired, true)
  state.templateMfaCode = '654321'
  await state.publishTemplateDraft()
  assert.equal(publishes, 1)
  await state.checkTemplatePublishResult()
  assert.equal(impacts, 2)
  assert.equal(state.publishCheckRequired, false)
  assert.equal(state.templateMfaCode, '')
})

test('explicit publish rejection permits a fresh code only after draft and impact readback', async () => {
  let publishes = 0
  const { state } = makeTemplatePage({
    publishTemplate: async () => { publishes += 1; return { code: 409001, httpStatus: 409, message: '版本冲突' } },
    templateVersions: async () => ({ code: 0, data: { items: [publishedRow()] } }),
    templateImpact: async () => ({ code: 0, data: { sourceDigest: 'source', navigationDigest: 'navigation' } })
  })
  await state.publishTemplateDraft()
  assert.equal(publishes, 1)
  assert.equal(state.publishCheckRequired, false)
  assert.equal(state.templateMfaCode, '')
})
