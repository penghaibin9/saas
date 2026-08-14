import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const read=(p)=>fs.readFileSync(new URL(p,import.meta.url),'utf8')
const store=read('../src/stores/enterpriseContext.js'),home=read('../src/views/EnterpriseHomeView.vue'),positions=read('../src/views/PositionListView.vue'),form=read('../src/views/PositionFormView.vue'),decisions=read('../src/components/applicant/DecisionActions.vue')
test('closed and archived campaigns fail closed for recruitment writes',()=>{assert.match(store,/CLOSED','ARCHIVED/);assert.match(store,/contextReady/);assert.match(form,/recruitmentWritable/);assert.match(decisions,/recruitmentWritable|campaignWritable/);assert.match(positions,/历史只读/)})
test('campaign close preserves history and internship collaboration',()=>{assert.match(home,/历史招聘季/);assert.match(home,/INTERNSHIP_COLLAB/);assert.match(home,/正式 InternshipRecord/)})
