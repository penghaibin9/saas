// Isolated helper regression: synthetic DOM, not real API/login acceptance.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { chromium } from '@playwright/test'
import { loginMiniH5 } from '../lib/miniapp-login.mjs'

for (const wrapped of [false, true]) {
  for (const entry of ['student', 'teacher']) {
    test(`login helper: ${entry}, ${wrapped ? 'uni-app wrappers' : 'native HTML'}`, async () => {
      const browser = await chromium.launch({ executablePath: chromium.executablePath(), args: ['--no-sandbox'] })
      try {
        const page = await browser.newPage()
        const label = entry === 'teacher' ? '工号或统一账号' : '学号或统一账号'
        const button = wrapped ? 'uni-button' : 'button'
        const input = (name, cls = 'field') => wrapped
          ? `<uni-input class="${cls}" aria-label="${name}"><input></uni-input>`
          : `<input class="${cls}" aria-label="${name}">`
        const target = entry === 'teacher' ? 'teacher/workbench' : 'student/home'
        await page.route('http://login-helper.test/', route => route.fulfill({ contentType: 'text/html', body: `
          <div class="login-field">${input(label)}</div>
          <div class="login-field">${input('密码')}</div>
          <${button} class="tenant-box" onclick="document.querySelector('#tenant').hidden=false">学校编码</${button}>
          <div id="tenant" hidden></div>
          <${button} class="agreement-toggle" aria-label="同意用户协议与隐私政策" aria-checked="false"
            onclick="this.setAttribute('aria-checked','true')">同意</${button}>
          <${button} class="account-button" onclick="location.hash='/pages/${target}/index'">${entry === 'teacher' ? '进入教师工作台' : '进入学生首页'}</${button}>
          <script>document.querySelector('.tenant-box').onclick=()=>{const t=document.querySelector('#tenant');t.hidden=false;t.innerHTML=${JSON.stringify(input('学校编码', 'field--tenant'))}}</script>
        ` }))
        await loginMiniH5(page, {
          baseUrl: 'http://login-helper.test', entry, timeout: 1500,
          account: { username: 'fixture-user', password: 'fixture-password', tenant: 'fixture-school' },
        })
        assert.deepEqual(await page.locator('input').evaluateAll(nodes => nodes.map(n => n.value)),
          ['fixture-user', 'fixture-password', 'fixture-school'])
        assert.equal(await page.locator('.agreement-toggle').getAttribute('aria-checked'), 'true')
        assert.match(page.url(), new RegExp(target))
      } finally {
        await browser.close()
      }
    })
  }
}
