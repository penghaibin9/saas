import { test, expect } from '@playwright/test'

const ok = (data) => ({ code: 0, message: 'ok', data })

async function installEnterpriseApi(page, { released = false } = {}) {
  const handler = async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname

    if (path.endsWith('/internship/enterprise-portal/auth/login')) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          accessToken: 'browser-evidence-access', refreshToken: 'browser-evidence-refresh', tokenType: 'Bearer', expiresIn: 1800,
          context: { tenantId: '1', tenantCode: 'CSZY', memberId: '11', memberRole: 'HR', companyId: '21' },
        })),
      })
    }

    if (path.endsWith('/internship/enterprise-portal/context')) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          tenantId: '1', tenantCode: 'CSZY', memberId: '11', memberRole: 'HR', companyId: '21',
          campaignId: '2027-spring', batchId: '2027', grantId: '31', grantType: 'RECRUITMENT',
          capabilities: { recruitmentWrite: true },
        })),
      })
    }

    if (path.endsWith('/enterprise/internship/applications')) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          counts: { ALL: 2, PENDING: 1, INTERESTED: 0, INTERVIEW: 1, ACCEPT_INTENT: 0, REJECTED: 0 },
          items: [
            { applicationId: '501', name: '张三', major: '机械制造及自动化', grade: '2025级', positionName: '机械装配技术实习生', volunteerNo: 1, skillTags: ['CAD', '数控', '装配'], matchPercent: 95, appliedAt: '03-06 10:21' },
            { applicationId: '502', name: '李四', major: '机电一体化', grade: '2025级', positionName: '自动化维护实习生', volunteerNo: 2, skillTags: ['PLC'], matchPercent: 88, appliedAt: '03-06 11:15' },
          ],
        })),
      })
    }

    if (path.endsWith('/enterprise/internship/applications/501/material')) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          skillTags: ['CAD', '数控', '装配'],
          projects: [{ id: 'p1', title: '数控加工综合实训', description: '完成工艺编制与加工验证', verificationStatus: 'VERIFIED' }],
          practices: [{ id: 'x1', title: '智能制造产线实训', description: '完成装配与设备点检', verificationStatus: 'NOT_REQUIRED' }],
          certificates: [{ id: 'c1', title: '数控车工技能证书', verificationStatus: 'VERIFIED' }],
          portfolio: [],
        })),
      })
    }

    if (path.endsWith('/enterprise/internship/applications/501')) {
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          id: '501', name: '张三', major: '机械制造及自动化', grade: '2025级', positionName: '机械装配技术实习生',
          volunteerNo: 1, appliedAt: '03-06 10:21', matchPercent: 95, studentVerified: true,
          applicationStatement: '具备机械装配实训经验，希望从事智能制造方向。',
          volunteerGroupStatus: released ? 'NEEDS_REVISION' : 'SUBMITTED',
          releaseReason: released ? 'TEACHER_CONFIRM_TIMEOUT' : '', acceptIntentReleased: released,
          decisionStatus: released ? 'ACCEPT_INTENT' : 'INTERVIEW',
          contactPolicy: { allowed: false, maskedValue: '138****5678' },
          decisionHistory: [{ id: 'd1', status: 'INTERVIEW', effectStatus: 'ACTIVE', at: '03-08 14:00' }],
        })),
      })
    }

    if (path.endsWith('/enterprise/internship/campaigns')) {
      return route.fulfill({ contentType:'application/json', body:JSON.stringify(ok({items:[{id:'2027-spring',campaignName:'2027届春季岗位实习双选季',status:'OPEN'}]})) })
    }
    if (path.endsWith('/enterprise/internship/company')) {
      return route.fulfill({ contentType:'application/json', body:JSON.stringify(ok({name:'中联重科股份有限公司'})) })
    }
    if (path.endsWith('/enterprise/internship/dashboard')) {
      return route.fulfill({ contentType:'application/json', body:JSON.stringify(ok({metrics:{},tasks:[]})) })
    }

    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ code: 404001, message: 'test route missing' }) })
  }

  await page.route('**/api/v1/internship/enterprise-portal/**', handler)
  await page.route('**/api/v1/enterprise/internship/**', handler)
}

async function loginAndEnterCampaign(page){
  await page.goto('login')
  await page.getByLabel('学校编码').fill('CSZY')
  await page.getByLabel('手机号或登录账号').fill('enterprise.hr')
  await page.getByLabel('密码').fill('Evidence-Only-Password')
  await page.getByRole('button',{name:'登录'}).click()
  await expect(page.getByRole('heading',{name:'选择招聘季'})).toBeVisible()
  await page.getByRole('button',{name:/2027届春季岗位实习双选季/}).click()
  await expect(page.getByRole('link',{name:'报名学生'})).toBeVisible()
  await page.getByRole('link',{name:'报名学生'}).click()
}

test('A02-6 authenticated BOSS-style applicant workbench keeps snapshot privacy boundary', async ({ page }) => {
  await installEnterpriseApi(page)
  await loginAndEnterCampaign(page)

  await expect(page.getByRole('heading', { name: '报名学生' })).toBeVisible()
  await expect(page.getByText('张三', { exact: true }).first()).toBeVisible()
  await expect(page.getByText('岗位申请说明')).toBeVisible()
  await expect(page.getByText('学校已核验').first()).toBeVisible()
  await expect(page.getByText('138****5678')).toBeVisible()
  await expect(page.getByRole('button', { name: '联系方式未授权' })).toBeDisabled()
  await expect(page.getByText('身份证')).toHaveCount(0)
  await expect(page.getByText('其他志愿')).toHaveCount(0)
  await page.screenshot({ path: 'test-results/a02-applicant-workbench.png', fullPage: true })
})

test('A02-7 authenticated released ACCEPT_INTENT never stays visually effective', async ({ page }) => {
  await installEnterpriseApi(page, { released: true })
  await loginAndEnterCampaign(page)
  await expect(page.getByText('学校未在确认期限内完成最终确认，本次拟接收已释放，申请状态可能发生变化。历史 Decision 仍保留在处理记录。')).toBeVisible()
  await expect(page.getByText('已录用')).toHaveCount(0)
})
