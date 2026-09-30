import test from 'node:test'
import assert from 'node:assert/strict'
import { dormLoginReturn } from '../src/utils/dormLoginReturn.mjs'
test('login returns to the same rectification within the selected role',()=>{
 assert.equal(dormLoginReturn('teacher','9007199254740993'),'/pages/teacher/dorm-review/index?tab=recheck&recordId=9007199254740993')
 assert.equal(dormLoginReturn('student','9007199254740993'),'/pages/student/affairs/dorm?rectificationId=9007199254740993')
})
test('login return rejects URLs, extra query parameters, malformed identifiers and unknown roles',()=>{
 for(const id of ['https://example.com','//example.com','1&role=teacher','../1','0','-1','1.5','']) assert.equal(dormLoginReturn('student',id),'')
 assert.equal(dormLoginReturn('admin','1'),'')
})
