import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'

const formView = fs.readFileSync(
  new URL('../src/modules/graduation/views/GraduationDefenseGradeFormView.vue', import.meta.url),
  'utf8',
)

test('every defense-grade form key maps to its authoritative backend permission', () => {
  const expected = [
    ['plagiarismResult', 'graduationDesign.plagiarism.result'],
    ['dispute', 'graduationDesign.plagiarism.start'],
    ['reviewSubmit', 'graduationDesign.review.submit'],
    ['reviewReturn', 'graduationDesign.review.return'],
    ['scoreEntry', 'graduationDesign.defense.score'],
    ['secondDefense', 'graduationDesign.defense.secondRound'],
    ['calculate', 'graduationDesign.grade.calculate'],
    ['returnGrade', 'graduationDesign.grade.review'],
    ['withdraw', 'graduationDesign.grade.withdraw'],
  ]
  for (const [formKey, permission] of expected) {
    assert.match(formView, new RegExp(`${formKey}: '${permission.replaceAll('.', '\\.')}'`))
  }
})

test('forged formKey and missing record context fail closed before business APIs run', () => {
  assert.match(formView, /if \(!this\.canOpenForm\(this\.formKey\)\) \{ this\.error = '当前角色无权执行该毕业设计操作，请返回对应工作区'/)
  assert.match(formView, /RECORD_CONTEXT_FORMS = new Set\(\['plagiarismResult', 'dispute', 'reviewSubmit', 'reviewReturn'\]\)/)
  assert.match(formView, /RECORD_CONTEXT_FORMS\.has\(this\.formKey\) && !this\.recordId/)
  assert.match(formView, /matchPermission\(this\.permissionPatterns, permissionKey\)/)
})

test('submit rechecks authorization instead of trusting a form initialized earlier', () => {
  assert.match(formView, /async submit\(\) \{[\s\S]*if \(!this\.canOpenForm\(this\.formKey\)\) \{ this\.formError = '当前角色无权执行该毕业设计操作'; return \}/)
})
