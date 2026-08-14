import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const bar=fs.readFileSync(new URL('../src/components/CampaignContextBar.vue',import.meta.url),'utf8')
const home=fs.readFileSync(new URL('../src/views/EnterpriseHomeView.vue',import.meta.url),'utf8')
test('enterprise home answers campaign phase and time-to-deadline before metrics',()=>{for(const label of ['当前招聘季','当前阶段','当前阶段截止','距离截止'])assert.match(bar,new RegExp(label));assert.match(bar,/currentDeadlineAt/);assert.match(bar,/enterpriseDecisionDeadline/)})
test('enterprise home keeps task flow and the required eight operational metrics',()=>{for(const label of ['已发布岗位','待学校审核','报名学生','待处理申请','面试中','拟接收','当前实习学生','待评价'])assert.match(home,new RegExp(label));assert.match(home,/今天要做什么/)})
