const requiredTrue = (name) => {
  if (process.env[name] !== 'true') {
    throw new Error(`${name}=true is required. Browser E2E can create and mutate test data.`)
  }
}

const account = (prefix, fallback) => ({
  tenant: process.env[`${prefix}_TENANT`] || fallback.tenant,
  username: process.env[`${prefix}_USERNAME`] || fallback.username,
  password: process.env[`${prefix}_PASSWORD`] || fallback.password
})

export const config = {
  staffBaseUrl: process.env.E2E_STAFF_BASE_URL || 'http://127.0.0.1:5173',
  studentBaseUrl: process.env.E2E_STUDENT_BASE_URL || 'http://127.0.0.1:5199/portal',
  apiBaseUrl: process.env.E2E_API_BASE_URL || 'http://127.0.0.1:8000/api/v1',
  sandboxAdmin: account('E2E_SANDBOX_ADMIN', {
    tenant: 'sandbox-school', username: 'admin2', password: '123456'
  }),
  demoAdmin: account('E2E_DEMO_ADMIN', {
    tenant: 'demo-school', username: 'admin', password: '123456'
  }),
  multiRole: account('E2E_MULTI_ROLE', {
    tenant: 'sandbox-school', username: 'e2e_academic_admin', password: 'E2eTest@2026'
  }),
  student: account('E2E_STUDENT', {
    tenant: 'sandbox-school', username: 'E2E20260001', password: 'E2eTest@2026'
  }),
  outsideStudent: account('E2E_OUTSIDE_STUDENT', {
    tenant: 'sandbox-school', username: 'E2E20260002', password: 'E2eTest@2026'
  }),
  studentC: account('E2E_STUDENT_C', {
    tenant: 'sandbox-school', username: 'E2E20260003', password: 'E2eTest@2026'
  }),
  mentor: account('E2E_MENTOR', {
    tenant: 'sandbox-school', username: 'e2e_advisor_a', password: 'E2eTest@2026'
  })
}

function assertLocalUrl(name, value) {
  const url = new URL(value)
  const local = ['127.0.0.1', 'localhost', '::1'].includes(url.hostname)
  if (!local && process.env.E2E_ALLOW_REMOTE !== 'true') {
    throw new Error(`${name} must point to localhost unless E2E_ALLOW_REMOTE=true: ${value}`)
  }
}

export function assertSafeEnvironment() {
  requiredTrue('E2E_ALLOW_DESTRUCTIVE_TESTS')

  const appEnv = String(process.env.APP_ENV || '').toLowerCase()
  const deploy = String(process.env.DEPLOYMENT_MODE || '').toLowerCase()
  if (['prod', 'production'].includes(appEnv) || ['prod', 'production'].includes(deploy)) {
    throw new Error('Refusing to run browser E2E against a production environment.')
  }

  const dbUrl = process.env.DATABASE_URL || ''
  if (!dbUrl) throw new Error('DATABASE_URL is required for safety verification.')
  const lowered = dbUrl.toLowerCase()
  if (!/(e2e|test)/.test(lowered)) {
    throw new Error('DATABASE_URL must contain "e2e" or "test".')
  }
  if (/(prod|production|staging)/.test(lowered)) {
    throw new Error('DATABASE_URL looks like a production/staging database.')
  }
  if (!/(127\.0\.0\.1|localhost)/.test(lowered) && process.env.E2E_ALLOW_REMOTE_DB !== 'true') {
    throw new Error('DATABASE_URL must be local unless E2E_ALLOW_REMOTE_DB=true.')
  }

  assertLocalUrl('E2E_STAFF_BASE_URL', config.staffBaseUrl)
  assertLocalUrl('E2E_STUDENT_BASE_URL', config.studentBaseUrl)
  assertLocalUrl('E2E_API_BASE_URL', config.apiBaseUrl)
}
