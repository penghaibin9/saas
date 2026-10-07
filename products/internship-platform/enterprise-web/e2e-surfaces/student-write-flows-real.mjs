import fs from 'node:fs/promises'
import path from 'node:path'
import { pathToFileURL } from 'node:url'
import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE_PATH ? pathToFileURL(process.env.PLAYWRIGHT_MODULE_PATH).href : 'playwright')
const out = process.env.WRITE_EVIDENCE_DIR
assert(out)
const flow = JSON.parse(await fs.readFile(path.join(out,'flow.json'),'utf8'))
const studentOrigin = process.env.WRITE_STUDENT_ORIGIN || 'http://127.0.0.1:5279'
const staffOrigin = process.env.WRITE_STAFF_ORIGIN || 'http://127.0.0.1:5278'
for (const origin of [studentOrigin,staffOrigin]) assert.equal(new URL(origin).hostname,'127.0.0.1')
const browser = await chromium.launch({headless:true,channel:'msedge'})
const contexts = await Promise.all([1,2,3].map(() => browser.newContext({viewport:{width:1440,height:1050}})))
const [student,school,teacher] = await Promise.all(contexts.map(c => c.newPage()))
const network=[], errors=[], receipts=[]
for (const [i,page] of [student,school,teacher].entries()) {
  page.on('pageerror',e=>errors.push({surface:i,message:e.message}))
  page.on('response',async r=>{if(r.url().includes('/api/v1/')) network.push({surface:i,path:new URL(r.url()).pathname,status:r.status()})})
}
async function login(page,studentRole,user) {
  await page.goto((studentRole?studentOrigin:staffOrigin)+(studentRole?'/student/login':'/login'))
  await page.getByLabel('学校编码').fill(flow.tenantCode)
  await page.getByLabel(studentRole?'学号 / 登录账号':'账号',{exact:true}).fill(user)
  await page.getByLabel('密码',{exact:true}).fill('Bulk-Tests-Only-2026!')
  await page.getByRole('button',{name:'登录',exact:true}).click()
  await page.waitForURL(studentRole?/\/student\/internship/:/\/admin\/internship/)
}
async function tab(groupName,tabName) {
  const group=student.locator('details.sp-process-group').filter({hasText:groupName})
  if(await group.getAttribute('open')===null) await group.locator('summary').click()
  await group.getByRole('button',{name:tabName,exact:true}).click()
}
async function postByClick(page,needle,button) {
  const pending=page.waitForResponse(r=>r.request().method()==='POST' && new URL(r.url()).pathname===needle,{timeout:30000})
  await button.click()
  const response=await pending, body=await response.json()
  assert.equal(response.status(),200,JSON.stringify(body)); assert.equal(body.code,0,JSON.stringify(body))
  receipts.push({path:needle,data:body.data})
  return body.data
}
async function upload(page,fileInput,fileName) {
  const pending=page.waitForResponse(r=>r.request().method()==='POST' && new URL(r.url()).pathname==='/api/v1/files')
  await fileInput.setInputFiles(path.join(out,fileName))
  const response=await pending, data=await response.json()
  assert.equal(data.code,0,JSON.stringify(data));assert.equal(data.data.readyForBusiness,true)
}
async function insuranceReview(id,approve) {
  await school.goto(staffOrigin+'/admin/internship/insurance/'+id+'?batchId='+flow.batchId)
  await school.locator('.iv-detail').waitFor()
  await school.locator('.iv-materials').getByRole('button',{name:'预览',exact:true}).click()
  await school.locator('.iv-materials img').first().waitFor({state:'visible',timeout:15000})
  if(!approve) {
    await school.getByRole('button',{name:'退回补正',exact:true}).click()
    await school.getByLabel('修改意见',{exact:true}).fill('请补充清晰的实习保险凭证')
  } else await school.getByRole('button',{name:'核验通过',exact:true}).click()
  await postByClick(school,'/api/v1/internship/insurances/'+id+'/verify',school.getByRole('button',{name:approve?'确认通过':'确认退回',exact:true}))
  await school.screenshot({path:path.join(out,approve?'insurance-approved.png':'insurance-returned.png'),fullPage:true})
}
async function reportTab(kind) {
  await tab('在岗办理','周报/月报/总结')
  await student.locator('.report-tabs').getByRole('button',{name:kind,exact:true}).click()
  await student.locator('.report-editor').waitFor()
}
async function reportReview(id,kind,approve) {
  const weekly=kind==='周报', prefix=weekly?'/reports/':'/process-reports/'
  await teacher.goto(staffOrigin+'/admin/internship'+prefix+id+'?batchId='+flow.batchId)
  await teacher.locator('.mp-grid-2').waitFor()
  assert.equal(await teacher.locator('.mp-grid-2').evaluate(node => getComputedStyle(node).display),'grid','Shared module styling must load on direct navigation')
  await teacher.locator('input[value="'+(approve?'APPROVE':'RETURN')+'"]').check()
  await teacher.locator(weekly?'#weekly-review-comment':'textarea').first().fill(approve?'修改后符合岗位实习要求':'请完善岗位成果与工作过程说明')
  if(approve) { await teacher.locator(weekly?'#weekly-rating':'#process-rating').selectOption('4'); if(kind==='实习总结') await teacher.locator('#summary-score').fill('88') }
  await teacher.locator('.report-evidence').getByRole('button',{name:approve?'report-corrected.png':'report.png',exact:true}).click()
  await teacher.locator('.report-evidence').getByRole('button',{name:'预览',exact:true}).click()
  await teacher.locator('.report-evidence img').first().waitFor({state:'visible'})
  if(approve) {
    const choice=teacher.getByLabel('附件所属报告版本'), latest=await choice.inputValue()
    const options=await choice.locator('option').evaluateAll(items=>items.map(x=>x.value))
    assert.equal(options.length,2)
    await choice.selectOption(options.find(x=>x!==latest))
    await teacher.locator('.report-evidence').getByRole('button',{name:'report.png',exact:true}).click()
    await teacher.locator('.report-evidence').getByRole('button',{name:'预览',exact:true}).click()
    await teacher.locator('.report-evidence img').first().waitFor({state:'visible'})
    await choice.selectOption(latest)
    await teacher.locator('.report-evidence').getByRole('button',{name:'report-corrected.png',exact:true}).click()
    await teacher.locator('.report-evidence').getByRole('button',{name:'预览',exact:true}).click()
    await teacher.locator('.report-evidence img').first().waitFor({state:'visible'})
    receipts.push({action:'VERSIONED_ATTACHMENT_PREVIEW',reportId:id,versions:2})
  }
  await teacher.evaluate(() => window.scrollTo(0,0))
  await teacher.waitForTimeout(150)
  assert.equal(await teacher.evaluate(() => document.documentElement.scrollWidth > innerWidth + 2),false,'Report review overflows desktop width')
  await teacher.screenshot({path:path.join(out,(weekly?'weekly':kind==='实习总结'?'summary':'monthly')+(approve?'-review-v2.png':'-review-v1.png')),fullPage:true})
  await postByClick(teacher,'/api/v1/internship'+prefix+id+'/review',teacher.getByRole('button',{name:approve?'确认通过':'退回修改',exact:true}))
}
try {
  await login(student,true,'student');await login(school,false,'school_admin');await login(teacher,false,'intern_mentor')
  await tab('安排与入岗','实习保险')
  await student.getByLabel('保单号',{exact:true}).fill('BROWSER-POLICY-'+flow.batchId)
  await student.getByLabel('承保机构',{exact:true}).fill('合成验收保险机构')
  await student.getByLabel('险种',{exact:true}).fill('实习责任保险')
  await student.getByLabel('生效日期',{exact:true}).fill('2026-09-01')
  await student.getByLabel('到期日期',{exact:true}).fill('2026-12-31')
  await upload(student,student.locator('input[type=file]'),'insurance.png')
  const policy=await postByClick(student,'/api/v1/portal/internship/insurance',student.getByRole('button',{name:'提交保险',exact:true}))
  await insuranceReview(policy.id,false)
  await student.reload();await tab('安排与入岗','实习保险')
  await student.getByText('核验意见：请补充清晰的实习保险凭证',{exact:true}).waitFor()
  await upload(student,student.locator('input[type=file]'),'insurance.png')
  await postByClick(student,'/api/v1/portal/internship/insurance',student.getByRole('button',{name:'补正并重新提交',exact:true}))
  await insuranceReview(policy.id,true)
  await student.reload();await tab('安排与入岗','实习保险')
  await student.getByText('保单已核验，当前无需更新。实习安排变化时请先联系学校核实。',{exact:true}).waitFor()
  await student.screenshot({path:path.join(out,'student-insurance-complete.png'),fullPage:true})
  for (const kind of ['周报','月报','实习总结']) {
    await reportTab(kind)
    const editor=student.locator('.report-editor'), weekly=kind==='周报'
    if(weekly) {await editor.getByPlaceholder('第几周').fill('1');await editor.getByPlaceholder('具体说明完成了什么任务、产出了什么结果').fill('完成岗位任务并记录工作成果。'.repeat(5));await editor.getByPlaceholder('记录技能、经验和需要改进的地方').fill('学习岗位技能并总结安全操作。'.repeat(4))}
    else {if(kind==='月报') await editor.locator('input[type=month]').fill('2026-10');await editor.locator('textarea').fill('真实岗位实习成果、操作过程、安全要求与学习总结。'.repeat(25))}
    await upload(student,editor.locator('input[type=file]'),'report.png')
    const route='/api/v1/portal/internship/context/'+(weekly?'weekly-reports':'reports')
    const created=await postByClick(student,route,editor.getByRole('button',{name:'提交'+kind,exact:true}))
    await reportReview(created.id,kind,false)
    await student.reload();await reportTab(kind)
    await student.getByRole('button',{name:'按意见修改',exact:true}).click()
    const field=weekly?editor.getByPlaceholder('具体说明完成了什么任务、产出了什么结果'):editor.locator('textarea')
    await field.fill((await field.inputValue())+'已根据指导意见补充了量化成果与过程记录。')
    await editor.getByRole('button',{name:'移除 · report.png',exact:true}).click()
    await upload(student,editor.locator('input[type=file]'),'report-corrected.png')
    const updated=await postByClick(student,route,editor.getByRole('button',{name:'重新提交'+kind,exact:true}))
    assert.equal(updated.id,created.id)
    await reportReview(updated.id,kind,true)
    await student.reload();await reportTab(kind)
    await student.locator('.report-item').getByText('已通过',{exact:true}).waitFor()
    await student.screenshot({path:path.join(out,(weekly?'weekly':kind==='实习总结'?'summary':'monthly')+'-student-complete.png'),fullPage:true})
  }
  assert.equal(errors.length,0,JSON.stringify(errors))
  const bad=network.filter(x=>x.status>=400 && x.path!=='/api/v1/auth/browser-refresh')
  assert.equal(bad.length,0,JSON.stringify(bad))
  await fs.writeFile(path.join(out,'browser-result.json'),JSON.stringify({status:'PASS',receipts,network,errors},null,2))
  console.log('BROWSER_WRITE_CHAIN_PASS')
} catch(error) {
  for(const [i,page] of [student,school,teacher].entries()) await page.screenshot({path:path.join(out,'failure-'+i+'.png'),fullPage:true}).catch(()=>{})
  await fs.writeFile(path.join(out,'browser-result.json'),JSON.stringify({status:'FAIL',message:error.message,receipts,network,errors,studentText:await student.locator('body').innerText(),schoolText:await school.locator('body').innerText(),teacherText:await teacher.locator('body').innerText()},null,2))
  throw error
} finally {await browser.close()}
