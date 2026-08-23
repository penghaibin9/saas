import fs from 'node:fs'
import path from 'node:path'
import { test, expect } from '../lib/observability.mjs'
import { config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

const FIXTURE = JSON.parse(fs.readFileSync(path.resolve(process.cwd(), 'runtime-fixtures/control-plane-school-iam.json'), 'utf8'))
const captureDir = path.resolve(process.cwd(), 'test-results/official-site-marketing-captures')
const surfaces = [
  { path: '/admin/system/roles?tab=permissions', file: 'platform-role-permissions.png', text: /角色|权限/ },
  { path: '/admin/system/scopes', file: 'platform-data-scopes.png', text: /数据范围/ },
  { path: '/admin/system/config?tab=brand', file: 'platform-school-brand.png', text: /品牌|学校信息/ },
  { path: '/admin/system/logs?tab=operation', file: 'platform-operation-audit.png', text: /审计|日志/ },
  { path: '/admin/system/implementation/overview', file: 'implementation-overview.png', text: /实施/ },
  { path: '/admin/system/implementation/acceptance', file: 'implementation-acceptance.png', text: /上线|验收/ },
  { path: '/admin/orientation/progress', file: 'orientation-progress.png', text: /报到进度/ },
  { path: '/admin/data-center', file: 'leadership-cockpit.png', text: /驾驶舱|生命周期/ }
]

async function waitForStableSurface(page, surface) {
  await expect(page).not.toHaveURL(/\/login(?:\?|$)/)
  await expect(page.locator('body')).toContainText(surface.text)
  await page.waitForLoadState('networkidle', { timeout: 20_000 })
  await expect(page.locator('body')).not.toContainText('正在加载系统管理中心…')
}

test.describe.serial('Official site marketing captures · real isolated school admin', () => {
  test('capture platform, implementation, orientation and leadership evidence from the real system', async ({ page }) => {
    const login = new StaffLoginPage(page, config.staffBaseUrl)
    await login.login({ tenant: FIXTURE.iamTenantCode, username: FIXTURE.iamAdminLogin, password: '123456' })
    fs.mkdirSync(captureDir, { recursive: true })
    await page.setViewportSize({ width: 1440, height: 1000 })
    for (const surface of surfaces) {
      await page.goto(`${config.staffBaseUrl}${surface.path}`)
      await waitForStableSurface(page, surface)
      await page.screenshot({ path: path.join(captureDir, surface.file), fullPage: true })
    }
    expect(fs.readdirSync(captureDir).filter((name) => name.endsWith('.png'))).toHaveLength(surfaces.length)
  })
})
