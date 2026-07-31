import fs from 'node:fs/promises'
import path from 'node:path'

export function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)) }

export function slug(value) {
  return String(value || 'page').normalize('NFKC')
    .replace(/[\\/:*?"<>|\s]+/g, '-')
    .replace(/^-+|-+$/g, '').slice(0, 90)
}

export async function ensureOutput(outputDir) {
  await fs.rm(outputDir, { recursive: true, force: true })
  await fs.mkdir(path.join(outputDir, 'screenshots'), { recursive: true })
}

export async function capture(page, outputDir, name, fullPage = true) {
  const file = path.join(outputDir, 'screenshots', `${slug(name)}.jpg`)
  await page.screenshot({ path: file, type: 'jpeg', quality: 76, fullPage })
  return path.relative(outputDir, file).replaceAll('\\', '/')
}

export function attachDiagnostics(page, report, scope) {
  page.on('console', (msg) => {
    if (msg.type() === 'error') report.consoleErrors.push({ scope: scope.value, text: msg.text().slice(0, 800) })
  })
  page.on('pageerror', (err) => report.consoleErrors.push({ scope: scope.value, text: String(err?.stack || err).slice(0, 1200) }))
  page.on('response', (res) => {
    if (res.status() < 400) return
    const url = res.url()
    if (!url.includes('/api/') && !url.includes('127.0.0.1:5199')) return
    report.networkFailures.push({ scope: scope.value, status: res.status(), method: res.request().method(), url })
  })
  page.on('requestfailed', (req) => report.networkFailures.push({
    scope: scope.value, status: 0, method: req.method(), url: req.url(), error: req.failure()?.errorText || 'request failed'
  }))
}

export async function waitStable(page) {
  await page.waitForLoadState('domcontentloaded')
  await sleep(900)
  await page.locator('.sp-state').filter({ hasText: /加载中|正在加载/ }).first()
    .waitFor({ state: 'hidden', timeout: 12000 }).catch(() => {})
  await sleep(250)
}

export async function setTheme(page, key) {
  await page.evaluate((theme) => {
    localStorage.setItem('student-portal-theme', theme)
    document.documentElement.dataset.spTheme = theme
    window.dispatchEvent(new CustomEvent('student-portal-theme-change', { detail: theme }))
  }, key)
  await sleep(180)
}

export async function analyzeLayout(page) {
  return page.evaluate(() => {
    const vw = document.documentElement.clientWidth
    const vh = document.documentElement.clientHeight
    const rect = (el) => {
      if (!el) return null
      const r = el.getBoundingClientRect()
      return { left: Math.round(r.left), top: Math.round(r.top), right: Math.round(r.right), bottom: Math.round(r.bottom), width: Math.round(r.width), height: Math.round(r.height) }
    }
    const visible = (el) => {
      const style = getComputedStyle(el)
      const r = el.getBoundingClientRect()
      return style.display !== 'none' && style.visibility !== 'hidden' && Number(style.opacity || 1) > 0 && r.width > 0 && r.height > 0
    }
    const shell = document.querySelector('.sp-shell')
    const tabs = document.querySelector('.sp-page > .sp-tabs')
    const keys = [...document.querySelectorAll('.sp-header,.sp-aside,.sp-content,.sp-tabs,.sp-card,.sp-table,.sp-inp,.sp-btn,.home-hero,.home-card,.section-route,[role="dialog"],dialog,.modal,.dialog,.drawer')]
    const overflow = keys.flatMap((el) => {
      if (!visible(el)) return []
      const r = el.getBoundingClientRect()
      const outsideViewport = r.left < -2 || r.right > vw + 2
      return outsideViewport ? [{ cls: String(el.className || '').slice(0, 140), ...rect(el) }] : []
    }).slice(0, 30)
    const dialogs = [...document.querySelectorAll('[role="dialog"],dialog,.modal,.dialog,.drawer')]
      .filter(visible)
      .map((el) => { const r = rect(el); return { ...r, outside: r.left < 0 || r.top < 0 || r.right > vw || r.bottom > vh } })

    const parseRgb = (value) => {
      const match = String(value || '').match(/rgba?\((\d+(?:\.\d+)?)[, ]+(\d+(?:\.\d+)?)[, ]+(\d+(?:\.\d+)?)(?:[, /]+([\d.]+))?\)/)
      return match ? [Number(match[1]), Number(match[2]), Number(match[3]), match[4] == null ? 1 : Number(match[4])] : null
    }
    const luminance = (rgb) => {
      const channel = (value) => {
        const v = value / 255
        return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4
      }
      return .2126 * channel(rgb[0]) + .7152 * channel(rgb[1]) + .0722 * channel(rgb[2])
    }
    const contrast = (a, b) => {
      const l1 = luminance(a)
      const l2 = luminance(b)
      return (Math.max(l1, l2) + .05) / (Math.min(l1, l2) + .05)
    }
    const effectiveBackground = (el) => {
      let current = el
      while (current) {
        const rgba = parseRgb(getComputedStyle(current).backgroundColor)
        if (rgba && rgba[3] >= .92) return rgba
        current = current.parentElement
      }
      return parseRgb(getComputedStyle(document.body).backgroundColor) || [255, 255, 255, 1]
    }
    const contrastIssues = [...document.querySelectorAll('button,a,label,th,td,p,small,strong,h1,h2,h3,h4,.sp-tab,.mtab,.sp-header__title,.sp-nav__text')]
      .flatMap((el) => {
        if (!visible(el)) return []
        const text = String(el.textContent || '').trim().replace(/\s+/g, ' ')
        if (!text || text.length > 180) return []
        const style = getComputedStyle(el)
        const fg = parseRgb(style.color)
        const bg = effectiveBackground(el)
        if (!fg || !bg || fg[3] < .85) return []
        const ratio = contrast(fg, bg)
        const size = Number.parseFloat(style.fontSize || '0')
        const weight = Number.parseInt(style.fontWeight || '400', 10) || 400
        const large = size >= 24 || (size >= 18.66 && weight >= 700)
        const minimum = large ? 3 : 4.5
        return ratio + .02 < minimum ? [{ text: text.slice(0, 90), cls: String(el.className || '').slice(0, 100), ratio: Number(ratio.toFixed(2)), minimum, color: style.color, background: `rgb(${bg[0]}, ${bg[1]}, ${bg[2]})` }] : []
      }).slice(0, 60)

    return {
      url: location.pathname + location.search,
      viewport: { width: vw, height: vh },
      document: { scrollWidth: document.documentElement.scrollWidth, scrollHeight: document.documentElement.scrollHeight },
      horizontalOverflow: document.documentElement.scrollWidth > vw + 4,
      shellClasses: shell?.className || '',
      aside: rect(document.querySelector('.sp-aside')),
      header: rect(document.querySelector('.sp-header')),
      tabs: tabs ? { ...rect(tabs), count: tabs.querySelectorAll('.sp-tab').length } : null,
      overflow,
      dialogs,
      contrastIssues,
      states: [...document.querySelectorAll('.sp-state,[role="alert"],.error,.domain-error,.gd-health')]
        .filter(visible)
        .map((el) => (el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 240)).filter(Boolean),
      tables: document.querySelectorAll('table').length,
      controls: document.querySelectorAll('input,select,textarea,button').length,
      disabledButtons: [...document.querySelectorAll('button:disabled')].map((el) => (el.textContent || '').trim()).filter(Boolean).slice(0, 20)
    }
  })
}

export function dedupe(rows, keyFn) { return [...new Map(rows.map((row) => [keyFn(row), row])).values()] }
