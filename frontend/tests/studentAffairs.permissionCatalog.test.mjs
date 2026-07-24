import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

import { STUDENT_AFFAIRS_PERMISSION_CATALOG } from '../src/modules/studentAffairs/config/permissionCatalog.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const navPlanPath = path.join(root, 'src/config/navPlan.js')
const routesPath = path.join(root, 'src/modules/studentAffairs/studentAffairs.routes.js')
const catalogCodes = new Set(STUDENT_AFFAIRS_PERMISSION_CATALOG.map(({ permissionCode }) => permissionCode))

async function sources() {
  const [nav, routes] = await Promise.all([readFile(navPlanPath, 'utf8'), readFile(routesPath, 'utf8')])
  return { nav, routes }
}

function codesIn(source) {
  return [...source.matchAll(/studentAffairs\.[A-Za-z0-9_.]+/g)].map(([code]) => code)
}

function navPermissionForPath(source, pathValue) {
  const escaped = pathValue.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = source.match(new RegExp(`${escaped}',\\s*'(studentAffairs\\.[A-Za-z0-9_.]+)'`))
  assert.ok(match, `navPlan 未找到 ${pathValue}`)
  return match[1]
}

function routePermissionForPath(source, pathValue) {
  const escaped = pathValue.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = source.match(new RegExp(`path:\\s*'${escaped}'[\\s\\S]{0,500}?permissionKey:\\s*'(studentAffairs\\.[A-Za-z0-9_.]+)'`))
  assert.ok(match, `routes 未找到 ${pathValue}`)
  return match[1]
}

test('学工导航和路由引用的权限均已登记', async () => {
  const { nav, routes } = await sources()
  const missing = [...new Set([...codesIn(nav), ...codesIn(routes)])].filter((code) => !catalogCodes.has(code))
  assert.deepEqual(missing, [])
})

test('关键页面导航与路由权限一致', async () => {
  const { nav, routes } = await sources()
  const cases = [
    ['/admin/student-affairs/profile', 'profile'],
    ['/admin/student-affairs/activity/second-class', 'activity/second-class'],
    ['/admin/student-affairs/mental/stats', 'mental/stats'],
    ['/admin/student-affairs/aid/stats', 'aid/stats']
  ]
  for (const [navPath, routePath] of cases) {
    assert.equal(navPermissionForPath(nav, navPath), routePermissionForPath(routes, routePath), navPath)
  }
})

test('权限目录不登记虚构 back 或 refresh 码', () => {
  for (const { permissionCode } of STUDENT_AFFAIRS_PERMISSION_CATALOG) {
    assert.ok(!/\.(?:back|refresh)$/i.test(permissionCode), permissionCode)
  }
})
