import fs from 'node:fs/promises'
import path from 'node:path'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const saAdmin = {
  tenant: 'sandbox-school',
  username: 'e2e_sa_admin',
  password: 'E2eTest@2026'
}

async function jsonBody(response) {
  try { return await response.json() } catch { return {} }
}

function apiUrl(suffix) {
  return `${config.apiBaseUrl}${suffix}`
}

function field(dialog, label) {
  return dialog.locator('.app-form-item').filter({ hasText: label }).first()
}

test.describe.serial('Student Affairs V3 Browser First · SA-005 grant configuration', () => {
  test.describe.configure({ retries: 0 })

  test('staff creates grant project and one-day batch through real UI, then reads server truth', async ({ page }) => {
    test.setTimeout(180_000)

    const prefix = `E2E-SA005-CONFIG-${Date.now()}-${process.pid}`
    const projectName = `${prefix}-助学金`
    const schoolYear = '2026-2027'
    const api500 = []
    const consoleErrors = []

    page.on('response', (response) => {
      if (response.url().includes('/api/') && response.status() >= 500) {
        api500.push(`${response.status()} ${response.request().method()} ${response.url()}`)
      }
    })
    page.on('console', (message) => {
      if (message.type() !== 'error') return
      const text = message.text()
      if (/favicon|source map|Vue Devtools/i.test(text)) return
      consoleErrors.push(text)
    })

    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login(saAdmin)
    await page.goto(`${config.staffBaseUrl}/admin/student-affairs/funding`)
    await expect(page.getByRole('heading', { name: '奖助管理工作台', exact: true })).toBeVisible()

    let projectId = ''
    await test.step('create grant project from Staff PC button and modal', async () => {
      await page.getByRole('button', { name: '建项目', exact: true }).click()
      const dialog = page.getByRole('dialog', { name: '新建资助项目' })
      await expect(dialog).toBeVisible()

      await field(dialog, '项目类型').locator('select').selectOption('GRANT')
      await field(dialog, '项目名称').locator('input').fill(projectName)
      await field(dialog, '金额（元）').locator('input').fill('2500')
      await field(dialog, '名额').locator('input').fill('1')

      const createdPromise = page.waitForResponse((response) => {
        try {
          const url = new URL(response.url())
          return url.pathname.endsWith('/api/v1/student-affairs/funding/projects')
            && response.request().method() === 'POST'
        } catch { return false }
      })
      await dialog.getByRole('button', { name: '创建', exact: true }).click()
      const created = await createdPromise
      expect(created.ok(), `project create HTTP ${created.status()}`).toBeTruthy()
      const env = await jsonBody(created)
      expect(env.code).toBe(0)
      projectId = String(env.data?.projectId || '')
      expect(projectId).toBeTruthy()
      await expect(dialog).toBeHidden()
    })

    let batchId = ''
    await test.step('create published one-day grant batch from Staff PC button and modal', async () => {
      const createBatch = page.getByRole('button', { name: '建批次', exact: true })
      await expect(createBatch).toBeEnabled({ timeout: 15_000 })
      await createBatch.click()
      const dialog = page.getByRole('dialog', { name: '新建资助批次' })
      await expect(dialog).toBeVisible()

      await field(dialog, '学年').locator('input').fill(schoolYear)
      await field(dialog, '公示天数').locator('input').fill('1')
      await field(dialog, '名额').locator('input').fill('1')
      const publish = dialog.locator('input[type="checkbox"]').first()
      await expect(publish).toBeChecked()

      const createdPromise = page.waitForResponse((response) => {
        try {
          const url = new URL(response.url())
          return url.pathname.endsWith('/api/v1/student-affairs/funding/batches')
            && response.request().method() === 'POST'
        } catch { return false }
      })
      await dialog.getByRole('button', { name: '保存', exact: true }).click()
      const created = await createdPromise
      expect(created.ok(), `batch create HTTP ${created.status()}`).toBeTruthy()
      const env = await jsonBody(created)
      expect(env.code).toBe(0)
      batchId = String(env.data?.batchId || '')
      expect(batchId).toBeTruthy()
      await expect(dialog).toBeHidden()
      await expect(page.getByRole('button', { name: '受理申请', exact: true })).toBeEnabled({ timeout: 15_000 })
    })

    await test.step('read GRANT project and batch server truth after UI writes', async () => {
      const headers = { Authorization: `Bearer ${login.lastAccessToken}` }
      const projects = await page.request.get(apiUrl('/student-affairs/funding/projects?page=1&pageSize=100'), { headers })
      expect(projects.ok(), `projects read HTTP ${projects.status()}`).toBeTruthy()
      const projectsEnv = await jsonBody(projects)
      expect(projectsEnv.code).toBe(0)
      const project = (projectsEnv.data?.items || []).find((item) => String(item.projectId) === projectId)
      expect(project, 'created grant project must be readable from server truth').toBeTruthy()
      expect(project.projectType).toBe('GRANT')
      expect(project.projectName).toBe(projectName)
      expect(String(project.amount)).toBe('2500.00')

      const batches = await page.request.get(apiUrl(`/student-affairs/funding/batches?projectId=${encodeURIComponent(projectId)}&page=1&pageSize=100`), { headers })
      expect(batches.ok(), `batches read HTTP ${batches.status()}`).toBeTruthy()
      const batchesEnv = await jsonBody(batches)
      expect(batchesEnv.code).toBe(0)
      const batch = (batchesEnv.data?.items || []).find((item) => String(item.batchId) === batchId)
      expect(batch, 'created grant batch must be readable from server truth').toBeTruthy()
      expect(batch.status).toBe('OPEN')
      expect(Number(batch.publicityDays)).toBe(1)
      expect(batch.schoolYear).toBe(schoolYear)
    })

    expect(api500, 'no API 5xx during Staff PC grant project/batch creation').toEqual([])
    expect(consoleErrors, 'no unexpected browser console errors during Staff PC grant project/batch creation').toEqual([])

    await fs.writeFile(
      path.resolve('student-affairs-grant-config-v3-evidence.json'),
      JSON.stringify({
        exactHead: process.env.E2E_TARGET_SHA || '',
        projectId,
        batchId,
        projectName,
        schoolYear,
        publicityDays: 1,
        surface: 'STAFF_PC',
        result: 'REAL_PASS'
      }, null, 2),
      'utf8'
    )
  })
})
