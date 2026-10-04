import test from 'node:test'
import assert from 'node:assert/strict'
import { getVisibleNavPlan } from '../src/config/navPlan.js'
import { workspacePages, restoreWorkspace } from '../src/components/workspace/teacherWorkspace.js'
import { activeWorkspacePage } from '../src/components/workspace/workspaceRouting.js'
import { internshipLocation, internshipWorkspaces } from '../src/modules/internship/navigation.js'
const route = fullPath => ({ fullPath, path: fullPath.split('?')[0], query: Object.fromEntries(new URL(fullPath, 'http://workspace.local').searchParams) })
test('协议模板与异常详情继承业务菜单，额外批次不会丢失高亮', () => {
  const pages = workspacePages(getVisibleNavPlan({ permissionPatterns: ['internship.agreement.view', 'internship.attendance.view'] }).find(item => item.key === 'internship')?.children || [])
  assert.equal(activeWorkspacePage(pages, route('/admin/internship/agreement-templates/9/edit?batchId=23')).title, '三方协议')
  assert.equal(activeWorkspacePage(pages, route('/admin/internship/exceptions?batchId=23')).title, '异常核验')
})
test('工作区按照当前权限建立菜单，撤权后移除旧页签及收藏', () => {
  const allowed = workspacePages(getVisibleNavPlan({ permissionPatterns: ['internship.agreement.view'] }).find(item => item.key === 'internship')?.children || [])
  assert.ok(allowed.length)
  assert.ok(allowed.every(item => item.permissionKey === 'internship.agreement.view'))
  const restored = restoreWorkspace({ tabs: [allowed[0].id, '/admin/other-school'], shortcuts: ['/admin/other-school', allowed[0].id] }, allowed)
  assert.deepEqual(restored.tabs, [allowed[0].id])
  assert.deepEqual(restored.shortcuts, [allowed[0].id])
  assert.deepEqual(restoreWorkspace(restored, []).tabs, [])
})
test('业务筛选与批次参数保留准确高亮，详情不误认总览', () => {
  const pages = workspacePages([{ key: 'students', label: '学生', children: [{ path: '/admin/internship/students?panel=roster', label: '名单' }, { path: '/admin/internship/students?panel=eligibility', label: '资格' }] }, { key: 'home', label: '今日工作', children: [{ path: '/admin/internship', label: '总览' }] }])
  assert.equal(activeWorkspacePage(pages, route('/admin/internship/students?batchId=23&page=2&panel=eligibility')).title, '资格')
  assert.equal(activeWorkspacePage(pages, route('/admin/internship/agreements/3?batchId=23')), undefined)
})
test('重复菜单地址只接受同一页面的有效工作区标识', () => {
  const pages = workspacePages([{ key: 'first', label: '一级', children: [{ path: '/admin/internship/agreements', label: '协议' }] }, { key: 'second', label: '二级', children: [{ path: '/admin/internship/agreements', label: '复核' }] }])
  assert.equal(activeWorkspacePage(pages, route('/admin/internship/agreements?batchId=23&_workspace=second%3A%E5%A4%8D%E6%A0%B8')).title, '复核')
  assert.equal(activeWorkspacePage(pages, route('/admin/internship/students?_workspace=second%3A%E5%A4%8D%E6%A0%B8')), undefined)
})
test('未授权身份的菜单为空，存储不能恢复被撤销页面', () => {
  const modules = getVisibleNavPlan({ permissionPatterns: [] }).find(item => item.key === 'internship')?.children || []
  assert.equal(workspacePages(modules).length, 0)
  assert.deepEqual(restoreWorkspace({ tabs: ['/admin/internship'], shortcuts: ['/admin/internship'] }, []).shortcuts, [])
})
test('材料收件深链刷新属于材料归档，批次切换不误入今日工作或学生配置', () => {
  const context = { permissionPatterns: ['internship.archive.view'] }
  const modules = getVisibleNavPlan(context).find(item => item.key === 'internship')?.children || []
  const pages = workspacePages(modules)
  const ref = '/admin/internship/material-requirements?batchId=9007199254740993001'
  assert.equal(activeWorkspacePage(pages, route(ref)).title, '材料归档')
  const owner = internshipLocation(ref, internshipWorkspaces(context))
  assert.equal(owner.workspaceKey, 'in-archive-stats'); assert.equal(owner.label, '材料归档')
  assert.equal(activeWorkspacePage(workspacePages([]), route(ref)), undefined)
})
