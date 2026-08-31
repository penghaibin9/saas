#!/usr/bin/env node
import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { chromium } from '@playwright/test'

import { assertSafeEnvironment, config } from '../lib/config.mjs'
import { StaffLoginPage } from '../pages/login.page.mjs'

assertSafeEnvironment()
const statePath = process.env.INTERNSHIP_V8_BROWSER_STATE_OUT || ''
const sessionPath = process.env.INTERNSHIP_V8_BROWSER_SESSION_OUT || ''
if (!statePath || !sessionPath) {
  console.error('INTERNSHIP_V8_BROWSER_STATE_OUT and INTERNSHIP_V8_BROWSER_SESSION_OUT are required')
  process.exit(2)
}

const browser = await chromium.launch({ headless: true })
try {
  const context = await browser.newContext()
  const page = await context.newPage()
  const login = new StaffLoginPage(page, config.staffBaseUrl)
  await login.login(config.sandboxAdmin)
  await page.waitForLoadState('networkidle', { timeout: 60_000 })
  const stateOutput = path.resolve(statePath)
  const sessionOutput = path.resolve(sessionPath)
  fs.mkdirSync(path.dirname(stateOutput), { recursive: true })
  fs.mkdirSync(path.dirname(sessionOutput), { recursive: true })
  await context.storageState({ path: stateOutput })
  const sessionStorage = await page.evaluate(() => Object.fromEntries(
    Array.from({ length: window.sessionStorage.length }, (_, index) => {
      const key = window.sessionStorage.key(index)
      return [key, window.sessionStorage.getItem(key)]
    })
  ))
  fs.writeFileSync(sessionOutput, JSON.stringify(sessionStorage, null, 2))
  console.log(`internship-v8 browser state ready state=${stateOutput} session=${sessionOutput}`)
  await context.close()
} finally {
  await browser.close()
}
