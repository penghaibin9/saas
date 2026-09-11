import test from 'node:test'
import assert from 'node:assert/strict'
import { permissionDisplayLabel } from '../src/modules/system/utils/permissionLabels.js'
import { makeReadOnlyDraft } from '../src/modules/system/utils/workspaceContract.js'
import fs from 'node:fs'
import { roleDisplayLabel } from '../src/modules/system/utils/permissionLabels.js'

test('concrete IAM catalog has Chinese display names for every entry', () => {
  for (const file of ['permission-catalog.json', 'permission-catalog-b8-concrete.json', 'permission-catalog-b8-compatibility.json']) {
    const catalog = JSON.parse(fs.readFileSync(new URL(`../../shared/contracts/${file}`, import.meta.url)))
    for (const item of catalog.entries) {
      const code = typeof item === 'string' ? item : item.permissionCode
      assert.notEqual(permissionDisplayLabel(code), '权限名称待维护', code)
    }
  }
  assert.equal(roleDisplayLabel('ACADEMIC_TEACHER'), '任课教师')
  assert.equal(roleDisplayLabel('GD_DEFENSE_EXPERT'), '答辩专家')
  assert.equal(roleDisplayLabel('CUSTOM', '学校自定角色'), '学校自定角色')
})

test('permission codes receive Chinese names without overwriting existing Chinese labels', () => {
  assert.equal(permissionDisplayLabel('academicAffairs.calendar.manage'), '教务 · 校历 · 管理')
  assert.equal(permissionDisplayLabel('academicAffairs.classTimeBand.view'), '教务 · 上课时间段 · 查看')
  assert.equal(permissionDisplayLabel('academicAffairs.calendarArchive.manage'), '教务 · 校历归档 · 管理')
  assert.equal(permissionDisplayLabel('academicAffairs.classroom.create', '新增教室'), '新增教室')
  assert.equal(permissionDisplayLabel('unknown.future.view'), '权限名称待维护')
})

test('readonly translation preserves exact granted codes and version', () => {
  const code = 'academicAffairs.classroom.delete'
  const draft = makeReadOnlyDraft({ id: '1', version: 0, permissionCodes: [code] }, '1')
  assert.equal(draft.groups[0].rows[0].label, '教务 · 教室 · 删除')
  assert.deepEqual(draft.menuKeys, [code])
  assert.equal(draft.version, 0)
})
