import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/views/EvaluationTaskListView.vue',import.meta.url),'utf8')
const api=fs.readFileSync(new URL('../src/services/enterpriseInternshipApi.js',import.meta.url),'utf8')
test('enterprise evaluation reuses facade and cannot forge canonical audit fields',()=>{assert.match(page,/ENTERPRISE_ONLINE/);assert.match(api,/evaluation-tasks\/\$\{id\}\/submit/);for(const forbidden of [/sourceType\s*:/,/actorMemberId\s*:/,/recordedAt\s*:/,/enterpriseContactId\s*:/])assert.doesNotMatch(page,forbidden)})
test('evaluation preserves existing canonical five score dimensions',()=>{for(const field of ['attendanceScore','skillScore','attitudeScore','collaborationScore','safetyScore'])assert.match(page,new RegExp(field))})
