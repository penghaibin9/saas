import { test, expect } from '@playwright/test'

const ok=(data)=>({code:0,message:'ok',data})

async function installApi(page){
  const state={recruitmentContext:0,collaborationContext:0,dashboard:0,positions:0,applications:0,students:0,evaluations:0}
  await page.route('**/api/v1/internship/enterprise-portal/**',async route=>{
    const request=route.request();const url=new URL(request.url());const path=url.pathname
    if(path.endsWith('/auth/invite/inspect'))return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({tenantId:'1',tenantCode:'CSZY',schoolName:'长沙职业技术学院',campaignId:'2026',campaignName:'2026届岗位实习双选季',companyId:'21',companyName:'中联重科股份有限公司',inviteeName:'企业HR',phoneMasked:'138****5678',memberRole:'HR',expiresAt:'2027-03-31T23:59:59'}))})
    if(path.endsWith('/auth/invite/accept'))return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({accessToken:'collab-access',refreshToken:'collab-refresh',tokenType:'Bearer',expiresIn:1800,user:{userId:'db-101',realName:'企业HR',userType:'ENTERPRISE_MENTOR'},context:{tenantId:'1',tenantCode:'CSZY',schoolName:'长沙职业技术学院',memberId:'11',companyId:'21',memberRole:'HR'}}))})
    if(path.endsWith('/campaigns'))return route.fulfill({contentType:'application/json',body:JSON.stringify(ok([{id:'2026',campaignId:'2026',campaignName:'2026届岗位实习双选季',status:'CLOSED',batchId:'66',participationStatus:'ACCEPTED'}]))})
    if(path.endsWith('/context')){state.recruitmentContext+=1;return route.fulfill({status:403,contentType:'application/json',body:JSON.stringify({code:403001,message:'招聘授权已过期'})})}
    if(path.endsWith('/collaboration-context')){state.collaborationContext+=1;expect(url.searchParams.get('batchId')).toBe('66');return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({tenantId:'1',tenantCode:'CSZY',memberId:'11',memberRole:'HR',companyId:'21',campaignId:'2026',batchId:'66',grantId:'88',grantType:'INTERNSHIP_COLLAB',capabilities:{recruitmentWrite:false,internshipCollab:true}}))})}
    if(path.endsWith('/company')&&request.method()==='GET')return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({id:'21',name:'中联重科股份有限公司',version:3,qualificationStatus:'PASSED',coopStatus:'ACTIVE',blacklist:false}))})
    if(path.endsWith('/dashboard')){state.dashboard+=1;return route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({code:500001,message:'must not reach dashboard'})})}
    if(path.endsWith('/positions')){state.positions+=1;return route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({code:500001,message:'must not reach positions'})})}
    if(path.endsWith('/applications')){state.applications+=1;return route.fulfill({status:500,contentType:'application/json',body:JSON.stringify({code:500001,message:'must not reach applications'})})}
    if(path.endsWith('/internship-students')){state.students+=1;expect(url.searchParams.get('batchId')).toBe('66');return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({items:[{id:'900',internshipId:'900',name:'张三',positionName:'机械装配技术实习生',mentorName:'李导师',status:'ONBOARD',statusLabel:'在岗',startDate:'2026-07-01',endDate:'2026-12-31',evaluationTaskId:'900',evaluationStatus:'PENDING'},{id:'901',internshipId:'901',name:'李四',positionName:'智能制造产线运维实习生',mentorName:'王导师',status:'ONBOARD',statusLabel:'在岗',startDate:'2026-07-08',endDate:'2026-12-31',evaluationTaskId:'901',evaluationStatus:'COMPLETED'}],total:2,page:1,pageSize:50,hasNext:false}))})}
    if(path.endsWith('/evaluation-tasks')){state.evaluations+=1;expect(url.searchParams.get('batchId')).toBe('66');return route.fulfill({contentType:'application/json',body:JSON.stringify(ok({items:[{id:'900',taskId:'900',internshipId:'900',studentName:'张三',positionName:'机械装配技术实习生',mentorName:'李导师',status:'PENDING',statusLabel:'待评价',deadline:'2026-12-31'},{id:'901',taskId:'901',internshipId:'901',studentName:'李四',positionName:'智能制造产线运维实习生',mentorName:'王导师',status:'COMPLETED',statusLabel:'已完成',deadline:'2026-12-31'}],total:2,page:1,pageSize:50,hasNext:false}))})}
    return route.fulfill({status:404,contentType:'application/json',body:JSON.stringify({code:404001,message:`unhandled ${path}`})})
  })
  return state
}

async function acceptInvite(page){
  const token='ei.2026.11.collaboration-only-evidence-01234567890123456789012345'
  await page.goto(`invite/accept?tenantCode=CSZY&token=${encodeURIComponent(token)}`)
  await expect(page.getByText('2026届岗位实习双选季')).toBeVisible()
  await page.getByLabel('验证受邀手机号').fill('13800125678')
  await page.getByLabel('设置密码（至少 8 位）').fill('Evidence-Only-Password')
  await page.getByRole('button',{name:'接受邀请并进入企业协同中心'}).click()
}

async function navigateSpa(page,path){
  await page.evaluate(async target=>{const app=document.querySelector('#app')?.__vue_app__;const router=app?.config?.globalProperties?.$router;if(!router)throw new Error('Vue Router unavailable');await router.push(target)},path)
}

test('expired recruitment falls back to active internship collaboration without any recruitment network calls',async({page})=>{
  const state=await installApi(page)
  await acceptInvite(page)
  await expect(page.getByRole('heading',{name:'企业首页'})).toBeVisible()
  expect(state.recruitmentContext).toBe(1)
  expect(state.collaborationContext).toBe(1)
  expect(state.dashboard).toBe(0)
  expect(state.positions).toBe(0)
  expect(state.applications).toBe(0)

  await navigateSpa(page,'/positions')
  await expect(page.getByText(/招聘访问已结束/)).toBeVisible()
  expect(state.positions).toBe(0)

  await navigateSpa(page,'/applications')
  await expect(page.getByText(/当前成员角色不能处理报名学生|招聘访问已结束|不能处理报名学生/)).toBeVisible()
  expect(state.applications).toBe(0)

  await navigateSpa(page,'/students')
  await expect(page.getByRole('heading',{name:'实习学生'})).toBeVisible()
  await expect(page.getByText('张三')).toBeVisible()
  await page.screenshot({path:'test-results/a02-internship-students.png',fullPage:true})

  await navigateSpa(page,'/evaluations')
  await expect(page.getByRole('heading',{name:'评价任务'})).toBeVisible()
  await expect(page.getByText('张三 · 机械装配技术实习生')).toBeVisible()
  await page.screenshot({path:'test-results/a02-evaluation-tasks.png',fullPage:true})

  expect(state.students).toBe(1)
  expect(state.evaluations).toBe(1)
  expect(state.dashboard).toBe(0)
  expect(state.positions).toBe(0)
  expect(state.applications).toBe(0)
})
