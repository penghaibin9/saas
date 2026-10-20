#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { chromium } from '@playwright/test'

import { assertSafeEnvironment, config } from '../lib/config.mjs'
import { StaffLoginPage, StudentLoginPage } from '../pages/login.page.mjs'

assertSafeEnvironment()
const outputRoot = path.resolve(process.env.E2E_INTERNSHIP_V8_SCREENSHOT_DIR || 'runtime/internship-v8-final-screenshots')
const advanced = JSON.parse(fs.readFileSync(path.resolve('runtime/internship-v8-advanced-fixture.json'), 'utf8'))
const base = JSON.parse(fs.readFileSync(path.resolve('runtime/internship-fixture.json'), 'utf8'))
const staff = config.staffBaseUrl.replace(/\/+$/, '')
const student = config.studentBaseUrl.replace(/\/+$/, '')

const journeys = [
  { id: 'IX-GJ-01', batchId: base.batchId, a: '/admin/internship', b: `/admin/internship/batches/${base.batchId}`, c: '/internship' },
  { id: 'IX-GJ-02', batchId: base.batchId, a: '/admin/internship/enterprises?panel=list', b: `/admin/internship/match?panel=results&batchId=${base.batchId}`, c: '/internship/selection' },
  { id: 'IX-GJ-03', batchId: base.batchId, a: '/admin/internship/applications?status=ALL', b: `/admin/internship/compliance?batchId=${base.batchId}`, c: '/internship/compliance' },
  { id: 'IX-GJ-04', batchId: base.batchId, a: `/admin/internship/attendance?batchId=${base.batchId}`, b: `/admin/internship/exceptions?batchId=${base.batchId}`, c: '/internship' },
  { id: 'IX-GJ-05', batchId: advanced.gj05.batchId, a: `/admin/internship/reports?batchId=${advanced.gj05.batchId}`, b: `/admin/internship/guidance?batchId=${advanced.gj05.batchId}`, c: '/internship' },
  { id: 'IX-GJ-06', batchId: advanced.gj06.batchId, a: `/admin/internship/changes?panel=pending&batchId=${advanced.gj06.batchId}`, b: `/admin/internship/students/${advanced.gj06.internshipId}?batchId=${advanced.gj06.batchId}`, c: '/internship' },
  { id: 'IX-GJ-07', batchId: advanced.gj07.batchId, a: `/admin/internship/risks?panel=board&batchId=${advanced.gj07.batchId}`, b: `/admin/internship/risk-disposal?stage=closed&batchId=${advanced.gj07.batchId}`, c: '/internship' },
  { id: 'IX-GJ-08', batchId: advanced.gj08.batchId, a: `/admin/internship/student-evals?batchId=${advanced.gj08.batchId}`, b: `/admin/internship/scores?stage=publish&batchId=${advanced.gj08.batchId}`, c: '/internship' },
  { id: 'IX-GJ-09', batchId: advanced.gj08.batchId, a: `/admin/internship/material-center?batchId=${advanced.gj08.batchId}`, b: `/admin/internship/archive?panel=records&batchId=${advanced.gj08.batchId}&id=${advanced.gj08.internshipId}`, c: '/internship/profile' },
]

async function settle(page, expectedPath) {
  await page.waitForLoadState('networkidle', { timeout: 60_000 })
  await page.waitForTimeout(500)
  const current = new URL(page.url())
  if (current.pathname.endsWith('/login')) throw new Error(`authentication lost for ${expectedPath}`)
  if (!current.pathname.includes(expectedPath.split('?')[0])) {
    throw new Error(`unexpected final route ${current.pathname} for ${expectedPath}`)
  }
}

fs.mkdirSync(outputRoot, { recursive: true })
const browser = await chromium.launch({ headless: true })
const manifest = []
try {
  const staffContext = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
  const staffPage = await staffContext.newPage()
  await new StaffLoginPage(staffPage, staff).login(config.sandboxAdmin)
  await staffPage.waitForLoadState('networkidle', { timeout: 60_000 })

  const studentContext = await browser.newContext({ viewport: { width: 1280, height: 900 } })
  const studentPage = await studentContext.newPage()
  await new StudentLoginPage(studentPage, student).login(config.student)

  for (const journey of journeys) {
    const prefix = journey.id.toLowerCase()
    const a = path.join(outputRoot, `${prefix}-a.png`)
    const b = path.join(outputRoot, `${prefix}-b.png`)
    const c = path.join(outputRoot, `${prefix}-c.png`)
    await staffPage.goto(`${staff}${journey.a}${journey.a.includes('?') ? '&' : '?'}batchId=${journey.batchId}`)
    await settle(staffPage, journey.a)
    await staffPage.screenshot({ path: a, fullPage: true })
    await staffPage.goto(`${staff}${journey.b}`)
    await settle(staffPage, journey.b)
    await staffPage.screenshot({ path: b, fullPage: true })
    await studentPage.evaluate((batchId) => {
      sessionStorage.setItem('student_portal_internship_batch_v1', String(batchId))
    }, journey.batchId)
    await studentPage.goto(`${student}${journey.c}?batchId=${journey.batchId}`)
    await settle(studentPage, journey.c)
    await studentPage.screenshot({ path: c, fullPage: true })
    manifest.push({
      id: journey.id,
      screenshots: {
        A: path.relative(path.resolve('..'), a).replaceAll('\\', '/'),
        B: path.relative(path.resolve('..'), b).replaceAll('\\', '/'),
        C: path.relative(path.resolve('..'), c).replaceAll('\\', '/'),
      },
    })
  }
  await staffContext.close()
  await studentContext.close()
} finally {
  await browser.close()
}

const manifestPath = path.join(outputRoot, 'manifest.json')
fs.writeFileSync(manifestPath, JSON.stringify({ schema: 'internship-v8-screenshots/1', journeys: manifest }, null, 2))
console.log(`internship-v8 screenshot evidence journeys=${manifest.length} manifest=${manifestPath}`)
