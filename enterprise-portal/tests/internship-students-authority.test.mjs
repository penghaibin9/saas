import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/views/InternshipStudentListView.vue',import.meta.url),'utf8')
test('internship students page is InternshipRecord-only and never promotes accept intent',()=>{assert.match(page,/正式落岗的 InternshipRecord/);assert.doesNotMatch(page,/ACCEPT_INTENT/);assert.match(page,/MENTOR/);assert.match(page,/member\/contact scope/)})
