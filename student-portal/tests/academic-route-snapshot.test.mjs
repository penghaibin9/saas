import assert from 'node:assert/strict'
import test from 'node:test'

import { academicRoute } from '../src/router/academicRoutes.js'

function routeByPath(path) {
  return academicRoute.children.find((route) => route.path === path)
}

function componentOwner(route) {
  return String(route?.component || '')
}

const expected = {
  exam: {
    name: 'academic-exam',
    modulePath: 'academic',
    component: 'StudentExamView.vue'
  },
  makeup: {
    name: 'academic-makeup',
    modulePath: 'academic',
    component: 'StudentMakeupView.vue'
  },
  attendance: {
    name: 'academic-attendance',
    modulePath: 'academic',
    academicReadModel: 'attendance',
    component: 'StudentAcademicReadOnlyView.vue'
  },
  calendar: {
    name: 'academic-calendar',
    modulePath: 'academic',
    academicReadModel: 'calendar',
    component: 'StudentAcademicReadOnlyView.vue'
  },
  clearance: {
    name: 'academic-clearance',
    modulePath: 'academic',
    academicReadModel: 'clearance',
    component: 'StudentAcademicReadOnlyView.vue'
  },
  credits: {
    name: 'academic-credits',
    modulePath: 'academic',
    academicReadModel: 'credits',
    component: 'StudentAcademicReadOnlyView.vue'
  },
  warning: {
    name: 'academic-warning',
    modulePath: 'academic',
    academicReadModel: 'warning',
    component: 'StudentAcademicReadOnlyView.vue'
  },
  textbook: {
    name: 'academic-textbook',
    modulePath: 'academic',
    component: 'StudentTextbookView.vue'
  },
  'level-exam': {
    name: 'academic-level-exam',
    modulePath: 'academic',
    component: 'StudentLevelExamView.vue'
  },
  'major-split': {
    name: 'academic-major-split',
    modulePath: 'academic',
    component: 'StudentMajorSplitView.vue'
  }
}

test('post-PR58 academic dedicated/read-only route snapshot stays stable', () => {
  assert.equal(academicRoute.path, '/academic')
  assert.equal(academicRoute.name, 'academic-shell')

  for (const [path, contract] of Object.entries(expected)) {
    const route = routeByPath(path)
    assert.ok(route, `missing student academic route: ${path}`)
    assert.equal(route.name, contract.name, `${path} name drift`)
    assert.equal(route.meta?.modulePath, contract.modulePath, `${path} modulePath drift`)
    assert.equal(
      route.meta?.academicReadModel,
      contract.academicReadModel,
      `${path} academicReadModel drift`
    )
    assert.match(componentOwner(route), new RegExp(contract.component.replace('.', '\\.')))
    assert.equal(route.redirect, undefined, `${path} unexpectedly became a redirect`)
  }
})
