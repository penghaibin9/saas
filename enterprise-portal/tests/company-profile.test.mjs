import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const page=fs.readFileSync(new URL('../src/views/CompanyProfileView.vue',import.meta.url),'utf8')
const request=fs.readFileSync(new URL('../src/services/request.js',import.meta.url),'utf8')

test('A02-3 company profile uses human file selection instead of raw file id editing',()=>{
  assert.doesNotMatch(page,/Logo 文件 ID/)
  assert.match(page,/type="file"/)
  assert.match(page,/image\/png,image\/jpeg,image\/webp/)
  assert.match(page,/不需要填写文件编号/)
})

test('A02-3 logo upload goes through canonical file center and keeps auth refresh semantics',()=>{
  assert.match(request,/uploadTemporaryFile/)
  assert.match(request,/FormData/)
  assert.match(request,/\$\{API_BASE\}\$\{API_PREFIX\}\/files/)
  assert.match(page,/INTERNSHIP_ENTERPRISE_LOGO/)
})

test('A02-3 unfrozen Company facade blocks edits and orphan logo upload before any file network side effect',()=>{
  assert.match(page,/facadeReady=ref\(false\)/)
  assert.match(page,/:disabled="loading\|\|saving\|\|!facadeReady"/)
  assert.match(page,/<fieldset class="profile-fields" :disabled="!facadeReady">/)
  const saveAt=page.indexOf('async function save()')
  const guardAt=page.indexOf('if(!facadeReady.value)',saveAt)
  const uploadAt=page.indexOf('uploadTemporaryFile(',saveAt)
  assert.ok(saveAt>=0&&guardAt>saveAt,'save must fail closed on Company facade readiness')
  assert.ok(uploadAt>guardAt,'File Center upload must only occur after Company facade readiness guard')
})

test('A02-3 school authority fields remain display-only',()=>{
  for(const field of ['qualificationStatus','coopStatus','accessValidUntil','blacklist','schoolReview'])assert.match(page,new RegExp(field))
  const patchFields=page.match(/function publicPatch\(\)\{return \{([^}]*)\}\}/)?.[1]||''
  assert.ok(patchFields,'publicPatch editable payload must be discoverable')
  for(const forbidden of [/qualificationStatus\s*:/,/coopStatus\s*:/,/blacklist\s*:/,/accessValidUntil\s*:/,/schoolReview\s*:/])assert.doesNotMatch(patchFields,forbidden)
  assert.match(page,/以上信息由学校审核维护，企业端仅查看，不能修改/)
})
