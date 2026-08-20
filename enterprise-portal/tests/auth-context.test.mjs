import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const read=(p)=>fs.readFileSync(new URL(p,import.meta.url),'utf8')
const intro=read('../README.md'),login=read('../src/views/EnterpriseLoginView.vue'),invite=read('../src/views/InviteAcceptView.vue'),api=read('../src/services/authApi.js')

test('branch introduction freezes A02-0 through A02-10 order',()=>{const steps=['A02-0','A02-1','A02-2','A02-3','A02-4','A02-5','A02-6','A02-7','A02-8','A02-9','A02-10'];let at=-1;for(const step of steps){const next=intro.indexOf(step,at+1);assert.ok(next>at,`${step} must follow frozen order`);at=next}})
test('login requires tenantCode context and does not offer self registration',()=>{assert.match(login,/学校编码/);assert.match(login,/不提供开放式企业自注册/)})
test('invite token and tenantCode lock school company and campaign context through A01 adapter',()=>{assert.match(invite,/同一 tenantCode \+ 邀请 token 在服务端校验/);assert.match(invite,/不会再次提交 campaignId 或 companyId/);assert.match(api,/auth\/invite\/inspect/);assert.match(api,/auth\/browser-invite\/accept/);assert.match(api,/validatedInvite/)})
