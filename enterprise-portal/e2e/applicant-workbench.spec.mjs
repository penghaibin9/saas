import { test, expect } from '@playwright/test'

const ok = (data) => ({ code: 0, message: 'ok', data })

async function installEnterpriseApi(page) {
  const state={legacyRequests:0,contextCampaignIds:[],memberRole:'HR',snapshotRequests:0}
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

    if (path.endsWith('/internship/enterprise-portal/auth/invite/inspect')) {
      let body={}
      try{body=request.postDataJSON()||{}}catch{}
      state.memberRole=String(body.token||'').includes('.mentor.')?'MENTOR':'HR'
      return route.fulfill({
        contentType:'application/json',
        body:JSON.stringify(ok({
          tenantId:'1',tenantCode:'CSZY',schoolName:'长沙职业技术学院',campaignId:'2027',campaignName:'2027届春季岗位实习双选季',
          companyId:'21',companyName:'中联重科股份有限公司',inviteeName:state.memberRole==='MENTOR'?'企业导师':'企业HR',phoneMasked:'138****5678',memberRole:state.memberRole,expiresAt:'2027-03-31T23:59:59',
        })),
      })
    }

    if (path.endsWith('/internship/enterprise-portal/auth/invite/accept')) {
      return route.fulfill({
        contentType:'application/json',
        body:JSON.stringify(ok({
          accessToken:'invite-access',refreshToken:'invite-refresh',tokenType:'Bearer',expiresIn:1800,
          user:{userId:'db-101',realName:state.memberRole==='MENTOR'?'企业导师':'企业HR',userType:'ENTERPRISE_MENTOR'},
          context:{tenantId:'1',tenantCode:'CSZY',schoolName:'长沙职业技术学院',memberId:'11',companyId:'21',memberRole:state.memberRole},
        })),
      })
    }

    if (path.endsWith('/internship/enterprise-portal/context')) {
      state.contextCampaignIds.push(url.searchParams.get('campaignId'))
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          tenantId: '1', tenantCode: 'CSZY', memberId: '11', memberRole: state.memberRole, companyId: '21',
          campaignId: '2027', batchId: '2027', grantId: '31', grantType: 'RECRUITMENT',
        })),
      })
    }

    if (path.endsWith('/internship/enterprise-portal/applications/501')) {
      state.snapshotRequests+=1
      if (url.searchParams.get('campaignId') !== '2027') {
        return route.fulfill({ status: 400, contentType:'application/json', body:JSON.stringify({code:400001,message:'campaignId required'}) })
      }
      return route.fulfill({
        contentType: 'application/json',
        body: JSON.stringify(ok({
          applicationId:'501', positionId:'81', positionTitle:'机械装配技术实习生',
          profileSnapshot:{profile:{headline:'智能制造方向实习生'},items:[]},
          schoolFactSnapshot:{realName:'张三',majorName:'机械制造及自动化',grade:'2025级'},
          snapshotHash:'sha256-browser-evidence',contactSharingPolicy:{mode:'NONE',sharePhone:false,shareEmail:false},
        })),
      })
    }

    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ code: 404001, message: 'test route missing' }) })
  }

  await page.route('**/api/v1/internship/enterprise-portal/**', handler)
  await page.route('**/api/v1/enterprise/internship/**', async route=>{
    state.legacyRequests+=1
    await route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({code:500001,message:'legacy route must never be called'})})
  })
  return state
}

async function acceptInvite(page,token){
  await page.goto(`invite/accept?tenantCode=CSZY&token=${encodeURIComponent(token)}`)
  await expect(page.getByText('2027届春季岗位实习双选季')).toBeVisible()
  await page.getByLabel('验证受邀手机号').fill('13800125678')
  await page.getByLabel('设置密码（至少 8 位）').fill('Evidence-Only-Password')
  await page.getByRole('button',{name:'接受邀请并进入企业协同中心'}).click()
  await expect(page.getByRole('heading',{name:'企业首页'})).toBeVisible()
}

test('A02 normal login fails closed when the school has not exposed a Campaign list facade', async ({ page }) => {
  const state=await installEnterpriseApi(page)
  await page.goto('login')
  await page.getByLabel('学校编码').fill('CSZY')
  await page.getByLabel('手机号或登录账号').fill('enterprise.hr')
  await page.getByLabel('密码').fill('Evidence-Only-Password')
  await page.getByRole('button',{name:'登录'}).click()

  await expect(page.getByRole('heading',{name:'选择招聘季'})).toBeVisible()
  await expect(page.getByText(/该企业协同能力尚未由学校端开放：招聘季列表/)).toBeVisible()
  await expect(page.getByText('当前没有可进入的招聘季')).toBeVisible()
  expect(state.legacyRequests).toBe(0)
})

test('A02 invite activation binds campaign to the inspected token and context stays read-only without capability', async ({ page }) => {
  const state=await installEnterpriseApi(page)
  const token='ei.2027.11.browser-evidence-secret-012345678901234567890123456789'
  await acceptInvite(page,token)

  await expect(page.getByText('招聘季 #2027')).toBeVisible()
  await expect(page.getByText(/该企业协同能力尚未由学校端开放：招聘工作台/)).toBeVisible()
  expect(state.contextCampaignIds).toEqual(['2027'])
  expect(state.legacyRequests).toBe(0)

  await page.getByRole('link',{name:'报名学生'}).click()
  await expect(page.getByRole('heading',{name:'报名学生'})).toBeVisible()
  await expect(page.getByText(/该企业协同能力尚未由学校端开放：报名学生列表/)).toBeVisible()
  expect(state.legacyRequests).toBe(0)
  await page.screenshot({ path: 'test-results/a02-fail-closed-facades.png', fullPage: true })
})

test('A02 canonical Snapshot stays readable only with an already validated HR campaign context', async ({ page }) => {
  const state=await installEnterpriseApi(page)
  const token='ei.2027.11.browser-evidence-secret-012345678901234567890123456789'
  await acceptInvite(page,token)

  await page.getByRole('link',{name:'报名学生'}).click()
  await page.evaluate(()=>{
    window.history.pushState({},'',`${window.location.pathname.replace(/\/applications.*$/,'')}/applications/501`)
    window.dispatchEvent(new PopStateEvent('popstate'))
  })
  await expect(page.getByText('投递快照')).toBeVisible()
  await expect(page.getByText('张三',{exact:true})).toBeVisible()
  await expect(page.getByText('身份证')).toHaveCount(0)
  await expect(page.getByRole('button',{name:'拟接收',exact:true})).toBeDisabled()
  expect(state.snapshotRequests).toBe(1)
  expect(state.contextCampaignIds).toEqual(['2027'])
  expect(state.legacyRequests).toBe(0)
})

test('A02 MENTOR cannot enter Applicant workbench or call canonical Applicant Snapshot', async ({ page }) => {
  const state=await installEnterpriseApi(page)
  const token='ei.2027.11.mentor.browser-evidence-secret-012345678901234567890123'
  await acceptInvite(page,token)

  await expect(page.getByRole('link',{name:'报名学生'})).toHaveCount(0)
  await expect(page.locator('.nav-disabled[aria-disabled="true"]').filter({hasText:'报名学生'})).toBeVisible()

  await page.evaluate(()=>{
    window.history.pushState({},'', '/enterprise/applications/501')
    window.dispatchEvent(new PopStateEvent('popstate'))
  })
  await expect(page.getByRole('heading',{name:'报名学生'})).toBeVisible()
  await expect(page.getByText('当前成员角色不能处理报名学生')).toBeVisible()
  await expect(page.getByText(/企业导师可参与后续实习协同/)).toBeVisible()
  expect(state.snapshotRequests).toBe(0)
  expect(state.legacyRequests).toBe(0)
})
