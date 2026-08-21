import { test, expect } from '@playwright/test'

const ok = (data) => ({ code: 0, message: 'ok', data })

async function installEnterpriseApi(page,{recruitmentWrite=true}={}) {
  const state={legacyRequests:0,contextCampaignIds:[],memberRole:'HR',listRequests:[],snapshotRequests:0,pdfRequests:0,contactRequests:0,campaignRequests:0,companyRequests:0,dashboardRequests:0,positionRequests:0,refreshRequests:0}
  const handler = async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const path = url.pathname

    if (path.endsWith('/internship/enterprise-portal/auth/browser-login')) {
      return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({accessToken:'browser-evidence-access',tokenType:'Bearer',expiresIn:1800,context:{tenantId:'1',tenantCode:'CSZY',memberId:'11',memberRole:'HR',companyId:'21'}}))})
    }
    if (path.endsWith('/internship/enterprise-portal/auth/browser-refresh')) {
      state.refreshRequests+=1
      return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({accessToken:`browser-evidence-refresh-${state.refreshRequests}`,tokenType:'Bearer',expiresIn:1800}))})
    }
    if (path.endsWith('/internship/enterprise-portal/auth/browser-logout')) {
      return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({invalidated:true}))})
    }
    if (path.endsWith('/internship/enterprise-portal/auth/invite/inspect')) {
      let body={};try{body=request.postDataJSON()||{}}catch{}
      state.memberRole=String(body.token||'').includes('.mentor.')?'MENTOR':'HR'
      return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({tenantId:'1',tenantCode:'CSZY',schoolName:'长沙职业技术学院',campaignId:'2027',campaignName:'2027届春季岗位实习双选季',companyId:'21',companyName:'中联重科股份有限公司',inviteeName:state.memberRole==='MENTOR'?'企业导师':'企业HR',phoneMasked:'138****5678',memberRole:state.memberRole,expiresAt:'2027-03-31T23:59:59'}))})
    }
    if (path.endsWith('/internship/enterprise-portal/auth/browser-invite/accept')) {
      return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({accessToken:'invite-access',tokenType:'Bearer',expiresIn:1800,user:{userId:'db-101',realName:state.memberRole==='MENTOR'?'企业导师':'企业HR',userType:'ENTERPRISE_MENTOR'},context:{tenantId:'1',tenantCode:'CSZY',schoolName:'长沙职业技术学院',memberId:'11',companyId:'21',memberRole:state.memberRole}}))})
    }
    if (path.endsWith('/internship/enterprise-portal/campaigns') && request.method()==='GET') {
      state.campaignRequests+=1
      return route.fulfill({contentType:'application/json',body:JSON.stringify(ok([
        {id:'2027',campaignId:'2027',campaignName:'2027届春季岗位实习双选季',status:'OPEN',batchId:'2027',participationStatus:'ACCEPTED'},
        {id:'2026',campaignId:'2026',campaignName:'2026届岗位实习双选季',status:'CLOSED',batchId:'2026',participationStatus:'ACCEPTED'},
      ]))})
    }
    if (path.endsWith('/internship/enterprise-portal/context')) {
      const requestedCampaignId=url.searchParams.get('campaignId')
      state.contextCampaignIds.push(requestedCampaignId)
      if(requestedCampaignId!=='2027')return route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({code:403001,message:'fixture rejects unauthorized recruitment campaign'})})
      return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({tenantId:'1',tenantCode:'CSZY',memberId:'11',memberRole:state.memberRole,companyId:'21',campaignId:requestedCampaignId,campaignName:'2027届春季岗位实习双选季',campaignStatus:'OPEN',batchId:'2027',grantId:'31',grantType:'RECRUITMENT',capabilities:{recruitmentWrite:recruitmentWrite&&state.memberRole==='HR',internshipCollab:false}}))})
    }
    if (path.endsWith('/internship/enterprise-portal/company') && request.method()==='GET') {
      state.companyRequests+=1
      return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({id:'21',name:'中联重科股份有限公司',shortName:'中联重科',shortIntro:'面向全球的高端装备制造企业，长期参与职业院校智能制造人才培养。',website:'https://example.invalid',mainBusiness:'工程机械、智能制造与工业互联网',establishedYear:1992,address:'湖南省长沙市岳麓区',qualificationStatus:'PASSED',coopStatus:'ACTIVE',accessValidUntil:'2027-12-31',blacklist:false,schoolReview:'资质审核通过，允许参与当前招聘季',version:3}))})
    }
    if (path.endsWith('/internship/enterprise-portal/dashboard') && request.method()==='GET') {
      state.dashboardRequests+=1
      return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({metrics:{published:4,pending:1,applicants:36,todoApplicants:8,interview:6,acceptIntent:3,interns:12,evaluations:4},tasks:[{key:'candidate',title:'处理 8 份待处理申请',description:'优先处理第一志愿且材料完整的候选学生',href:'/applications',actionLabel:'去处理'},{key:'position',title:'补充 1 个待审核岗位材料',description:'学校审核前可撤回修改岗位内容',href:'/positions',actionLabel:'看岗位'}]}))})
    }
    if (path.endsWith('/internship/enterprise-portal/positions') && request.method()==='GET') {
      state.positionRequests+=1
      return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({items:[
        {id:'81',title:'机械装配技术实习生',workLocation:'长沙 · 高新区',headcount:12,majorRequirement:'机械制造及自动化 / 机电一体化',salaryRange:'3.5k-5k/月',status:'PUBLISHED',riskFlag:false,applicantCount:24,acceptIntentCount:3,placementCount:2,version:4},
        {id:'82',title:'智能制造产线运维实习生',workLocation:'长沙 · 望城区',headcount:8,majorRequirement:'智能制造 / 电气自动化',salaryRange:'4k-5.5k/月',status:'PENDING',riskFlag:false,applicantCount:12,acceptIntentCount:0,placementCount:0,version:2}
      ],total:2,page:1,pageSize:20}))})
    }
    if (path.endsWith('/internship/enterprise-portal/applications') && request.method()==='GET') {
      state.listRequests.push(Object.fromEntries(url.searchParams.entries()))
      return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({items:[{applicationId:'501',volunteerNo:1,positionId:'81',positionTitle:'机械装配技术实习生',student:{studentId:'9001',realName:'张三',studentNo:'20250001',collegeName:'智能制造学院',majorName:'机械制造及自动化',grade:'2025级',className:'机制2501'},submissionVersion:2,materialSnapshotId:'991',submittedAt:'2026-08-15T09:30:00',decisionStatus:'PENDING',effectStatus:null,decisionVersion:0}],total:1,page:Number(url.searchParams.get('page')||1),pageSize:Number(url.searchParams.get('pageSize')||50)}))})
    }
    if (path.endsWith('/internship/enterprise-portal/applications/501') && request.method()==='GET') {
      state.snapshotRequests+=1
      if (url.searchParams.get('campaignId') !== '2027') return route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({code:400001,message:'campaignId required'})})
      return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({applicationId:'501',positionId:'81',positionTitle:'机械装配技术实习生',profileSnapshot:{profile:{headline:'智能制造方向实习生'},items:[]},schoolFactSnapshot:{realName:'张三',majorName:'机械制造及自动化',grade:'2025级'},snapshotHash:'sha256-browser-evidence',contactSharingPolicy:{mode:'IMMEDIATE',sharePhone:true,shareEmail:false}}))})
    }
    if (path.endsWith('/internship/enterprise-portal/applications/501/resume-pdf') && request.method()==='GET') {
      state.pdfRequests+=1
      if(url.searchParams.get('campaignId')!=='2027')return route.fulfill({status:400,contentType:'application/json',body:JSON.stringify({code:400001,message:'campaignId required'})})
      return route.fulfill({status:200,headers:{'content-type':'application/pdf','content-disposition':'inline; filename="internship-application-snapshot-991-v2.pdf"','x-internship-snapshot-hash':'sha256-browser-evidence'},body:'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\n%%EOF'})
    }
    if (path.endsWith('/internship/enterprise-portal/applications/501/contact-view') && request.method()==='POST') {
      state.contactRequests+=1
      return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({applicationId:'501',contactMode:'IMMEDIATE',phone:'13800138000'}))})
    }
    return route.fulfill({ status: 404, contentType: 'application/json', body: JSON.stringify({ code: 404001, message: 'test route missing' }) })
  }

  await page.route('**/api/v1/internship/enterprise-portal/**', handler)
  await page.route('**/api/v1/enterprise/internship/**', async route=>{state.legacyRequests+=1;await route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({code:500001,message:'legacy route must never be called'})})})
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

async function navigateSpa(page,path){
  await page.evaluate(async target=>{const app=document.querySelector('#app')?.__vue_app__;const router=app?.config?.globalProperties?.$router;if(!router)throw new Error('Vue Router unavailable in mounted enterprise portal');await router.push(target)},path)
}

test('A02 normal login reads the frozen Campaign list and survives F5 through browser refresh', async ({ page }) => {
  const state=await installEnterpriseApi(page)
  await page.goto('login')
  await page.getByLabel('学校编码').fill('CSZY')
  await page.getByLabel('手机号或登录账号').fill('enterprise.hr')
  await page.getByLabel('密码').fill('Evidence-Only-Password')
  await page.getByRole('button',{name:'登录'}).click()
  await expect(page.getByRole('heading',{name:'选择招聘季'})).toBeVisible()
  await expect(page.getByText('2027届春季岗位实习双选季')).toBeVisible()
  await expect(page.getByText('2026届岗位实习双选季')).toBeVisible()
  await page.getByRole('button').filter({hasText:'2027届春季岗位实习双选季'}).click()
  await expect(page.getByRole('heading',{name:'企业首页'})).toBeVisible()
  expect(state.campaignRequests).toBeGreaterThanOrEqual(1)
  expect(state.contextCampaignIds).toEqual(['2027'])
  expect(state.legacyRequests).toBe(0)

  await page.reload()
  await expect(page.getByRole('heading',{name:'企业首页'})).toBeVisible()
  expect(state.refreshRequests).toBe(1)
  expect(state.legacyRequests).toBe(0)
})

test('A02 commercial browser evidence covers home company positions and applicant workbench', async ({ page }) => {
  const state=await installEnterpriseApi(page)
  const token='ei.2027.11.browser-evidence-secret-012345678901234567890123456789'
  await acceptInvite(page,token)
  await expect(page.getByRole('banner').getByText('2027届春季岗位实习双选季',{exact:true})).toBeVisible()
  await page.screenshot({ path: 'test-results/a02-enterprise-home.png', fullPage: true })

  await navigateSpa(page,'/company')
  await expect(page.getByRole('heading',{name:'企业资料',exact:true})).toBeVisible()
  await page.screenshot({ path: 'test-results/a02-company-profile.png', fullPage: true })

  await navigateSpa(page,'/positions')
  await expect(page.getByRole('heading',{name:'我的岗位',exact:true})).toBeVisible()
  await expect(page.getByText('机械装配技术实习生')).toBeVisible()
  await page.screenshot({ path: 'test-results/a02-position-list.png', fullPage: true })

  await navigateSpa(page,'/applications')
  await expect(page.getByRole('heading',{name:'报名学生',exact:true})).toBeVisible()
  await expect(page.locator('button.candidate').filter({hasText:'张三'})).toBeVisible()
  await expect(page.getByText('20250001')).toHaveCount(0)
  expect(state.listRequests).toEqual([{campaignId:'2027',page:'1',pageSize:'50'}])
  expect(state.positionRequests).toBeGreaterThanOrEqual(1)
  expect(state.legacyRequests).toBe(0)
  await page.screenshot({ path: 'test-results/a02-canonical-applicant-list.png', fullPage: true })
})

test('A02 canonical list to Snapshot to contact-view never leaks identifiers before server-authorized reveal', async ({ page }) => {
  const state=await installEnterpriseApi(page)
  const token='ei.2027.11.browser-evidence-secret-012345678901234567890123456789'
  await acceptInvite(page,token)
  await page.getByRole('link',{name:'报名学生'}).click()
  await page.locator('button.candidate').filter({hasText:'张三'}).click()
  await expect(page.getByRole('heading',{name:'本次投递材料',exact:true})).toBeVisible()
  await expect(page.getByRole('heading',{name:'张三',exact:true})).toBeVisible()
  await expect(page.getByText('20250001')).toHaveCount(0)
  await expect(page.getByText('13800138000')).toHaveCount(0)
  await page.getByRole('button',{name:'查看联系方式'}).click()
  await expect(page.getByText('13800138000')).toBeVisible()
  await expect(page.locator('footer').getByRole('button',{name:'拟接收',exact:true})).toBeEnabled()
  expect(state.listRequests.length).toBe(1)
  expect(state.snapshotRequests).toBe(1)
  expect(state.contactRequests).toBe(1)
  expect(state.contextCampaignIds).toEqual(['2027'])
  expect(state.legacyRequests).toBe(0)
})

test('A02 applicant Snapshot and frozen PDF stay readable when recruitment writes are unavailable', async ({ page }) => {
  const state=await installEnterpriseApi(page,{recruitmentWrite:false})
  const token='ei.2027.11.browser-evidence-secret-012345678901234567890123456789'
  await acceptInvite(page,token)
  await page.getByRole('link',{name:'报名学生'}).click()
  await page.locator('button.candidate').filter({hasText:'张三'}).click()
  await expect(page.getByText(/当前招聘季未开放企业处理权限/)).toBeVisible()
  await expect(page.locator('footer').getByRole('button',{name:'拟接收',exact:true})).toBeDisabled()
  await page.getByRole('button',{name:'查看本次冻结档案 PDF'}).click()
  await expect.poll(()=>state.pdfRequests).toBe(1)
  expect(state.listRequests).toHaveLength(1)
  expect(state.snapshotRequests).toBe(1)
  expect(state.contextCampaignIds).toEqual(['2027'])
  expect(state.legacyRequests).toBe(0)
})

test('A02 MENTOR cannot enter Applicant workbench or issue list or Snapshot requests', async ({ page }) => {
  const state=await installEnterpriseApi(page)
  const token='ei.2027.11.mentor.browser-evidence-secret-012345678901234567890123'
  await acceptInvite(page,token)
  await expect(page.getByRole('link',{name:'报名学生'})).toHaveCount(0)
  await expect(page.locator('.nav-disabled[aria-disabled="true"]').filter({hasText:'报名学生'})).toBeVisible()
  await navigateSpa(page,'/applications/501')
  await expect(page.getByRole('heading',{name:'报名学生',exact:true})).toBeVisible()
  await expect(page.getByText('当前成员角色不能处理报名学生')).toBeVisible()
  await expect(page.getByText(/企业导师可参与后续实习协同/)).toBeVisible()
  expect(state.listRequests).toHaveLength(0)
  expect(state.snapshotRequests).toBe(0)
  expect(state.contactRequests).toBe(0)
  expect(state.legacyRequests).toBe(0)
})
