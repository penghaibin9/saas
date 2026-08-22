import { OFFICIAL_PRODUCT_LIST } from '../config/officialProducts'
import { OFFICIAL_SALES_PAGE_MAP, OFFICIAL_SALES_PAGES, OFFICIAL_SITE_CONTACT } from '../config/officialSalesPages'
import { API_BASE_URL, API_PREFIX } from './http/config'
import '../styles/official-mobile-wechat.css'

const WECHAT_SDK_URL = 'https://res.wx.qq.com/open/js/jweixin-1.6.0.js'
const SIGNATURE_ENDPOINT = `${API_BASE_URL}${API_PREFIX}/notification/website-wechat-signature`
const PRODUCT_PATH = /^\/products\/(academic-affairs|student-affairs|graduation|internship)$/
const OFFICIAL_PATHS = new Set(OFFICIAL_SALES_PAGES.map((item) => item.path))
const PRODUCT_BY_PATH = new Map(OFFICIAL_PRODUCT_LIST.map((item) => [`/products/${item.slug}`, item]))
const FALLBACK_SHARE_IMAGE = '/official-site/workbench.webp'

let sdkPromise = null
let installed = false
let dock = null
let lastConfiguredSignatureUrl = ''

export function isWechatBrowser(userAgent = typeof navigator !== 'undefined' ? navigator.userAgent : '') {
  return /MicroMessenger/i.test(String(userAgent || ''))
}

export function isOfficialSitePath(path = '') {
  return path === '/' || PRODUCT_PATH.test(path) || OFFICIAL_PATHS.has(path)
}

function absoluteUrl(value) {
  if (!value) return `${OFFICIAL_SITE_CONTACT.canonicalOrigin}${FALLBACK_SHARE_IMAGE}`
  try {
    return new URL(value, OFFICIAL_SITE_CONTACT.canonicalOrigin).toString()
  } catch {
    return `${OFFICIAL_SITE_CONTACT.canonicalOrigin}${FALLBACK_SHARE_IMAGE}`
  }
}

function shareMetaForPath(path) {
  const product = PRODUCT_BY_PATH.get(path)
  if (product) {
    return {
      title: `${product.name}｜跃科职业院校学生全生命周期数字化平台`,
      desc: product.summary,
      link: `${OFFICIAL_SITE_CONTACT.canonicalOrigin}${path}`,
      imgUrl: absoluteUrl(product.screenshots?.[0]?.src)
    }
  }

  const sales = OFFICIAL_SALES_PAGE_MAP[path]
  if (sales) {
    return {
      title: sales.title,
      desc: sales.description,
      link: `${OFFICIAL_SITE_CONTACT.canonicalOrigin}${path}`,
      imgUrl: absoluteUrl(sales.screenshots?.[0] || FALLBACK_SHARE_IMAGE)
    }
  }

  return {
    title: '跃科｜职业院校学生全生命周期数字化平台',
    desc: '面向职业院校，把教务、学工、毕业设计与岗位实习连接为可执行、可追踪、可审计的业务闭环。',
    link: OFFICIAL_SITE_CONTACT.canonicalOrigin,
    imgUrl: absoluteUrl(FALLBACK_SHARE_IMAGE)
  }
}

function loadWechatSdk() {
  if (typeof window === 'undefined') return Promise.resolve(null)
  if (window.wx) return Promise.resolve(window.wx)
  if (sdkPromise) return sdkPromise

  sdkPromise = new Promise((resolve) => {
    const existing = document.querySelector(`script[src="${WECHAT_SDK_URL}"]`)
    const script = existing || document.createElement('script')
    let settled = false
    const finish = (value) => {
      if (settled) return
      settled = true
      resolve(value)
    }

    script.addEventListener('load', () => finish(window.wx || null), { once: true })
    script.addEventListener('error', () => finish(null), { once: true })
    if (!existing) {
      script.src = WECHAT_SDK_URL
      script.async = true
      script.referrerPolicy = 'no-referrer-when-downgrade'
      document.head.appendChild(script)
    }
    window.setTimeout(() => finish(window.wx || null), 6000)
  })
  return sdkPromise
}

async function requestSignature(signatureUrl) {
  const response = await fetch(`${SIGNATURE_ENDPOINT}?url=${encodeURIComponent(signatureUrl)}`, {
    method: 'GET',
    headers: { Accept: 'application/json' }
  })
  if (!response.ok) throw new Error('WECHAT_SIGNATURE_UNAVAILABLE')
  const payload = await response.json().catch(() => ({}))
  return payload?.data || payload || {}
}

export async function configureOfficialWechatShare(path = window.location.pathname) {
  if (typeof window === 'undefined' || !isWechatBrowser() || !isOfficialSitePath(path)) {
    return { status: 'not-applicable' }
  }

  const signatureUrl = window.location.href.split('#')[0]
  if (signatureUrl === lastConfiguredSignatureUrl) return { status: 'already-configured' }

  try {
    const signed = await requestSignature(signatureUrl)
    if (!signed.enabled) return { status: 'disabled' }

    const wx = await loadWechatSdk()
    if (!wx?.config) return { status: 'sdk-unavailable' }

    const share = shareMetaForPath(path)
    return await new Promise((resolve) => {
      let settled = false
      const finish = (status) => {
        if (settled) return
        settled = true
        resolve({ status })
      }

      wx.ready(() => {
        try {
          wx.updateAppMessageShareData?.({
            title: share.title,
            desc: share.desc,
            link: share.link,
            imgUrl: share.imgUrl
          })
          wx.updateTimelineShareData?.({
            title: share.title,
            link: share.link,
            imgUrl: share.imgUrl
          })
          lastConfiguredSignatureUrl = signatureUrl
          finish('ready')
        } catch {
          finish('share-api-error')
        }
      })
      wx.error?.(() => finish('config-error'))
      wx.config({
        debug: false,
        appId: signed.appId,
        timestamp: signed.timestamp,
        nonceStr: signed.nonceStr,
        signature: signed.signature,
        jsApiList: ['updateAppMessageShareData', 'updateTimelineShareData']
      })
      window.setTimeout(() => finish('timeout'), 6500)
    })
  } catch {
    return { status: 'unavailable' }
  }
}

function buildDock(router) {
  if (dock || typeof document === 'undefined') return dock
  dock = document.createElement('nav')
  dock.className = 'yk-mobile-site-dock'
  dock.setAttribute('aria-label', '移动官网主导航')
  dock.innerHTML = `
    <a href="/" data-route="/" data-key="home"><span aria-hidden="true">⌂</span><b>首页</b></a>
    <a href="/#products" data-route="/#products" data-key="products"><span aria-hidden="true">▦</span><b>产品</b></a>
    <a href="/contact" data-route="/contact" data-key="contact"><span aria-hidden="true">✦</span><b>预约咨询</b></a>
    <a href="${OFFICIAL_SITE_CONTACT.phoneHref}" data-key="phone"><span aria-hidden="true">☎</span><b>电话</b></a>
  `
  dock.addEventListener('click', (event) => {
    const link = event.target.closest('a[data-route]')
    if (!link) return
    event.preventDefault()
    router.push(link.dataset.route)
  })
  document.body.appendChild(dock)
  return dock
}

function updateDock(router, path) {
  const node = buildDock(router)
  if (!node) return
  const productMatch = path.match(PRODUCT_PATH)
  const contactRoute = productMatch ? `/contact?product=${productMatch[1]}` : '/contact'
  const contactLink = node.querySelector('[data-key="contact"]')
  if (contactLink) {
    contactLink.href = contactRoute
    contactLink.dataset.route = contactRoute
  }

  node.querySelectorAll('a[data-key]').forEach((link) => link.removeAttribute('aria-current'))
  const activeKey = path === '/' ? 'home' : path === '/contact' ? 'contact' : PRODUCT_PATH.test(path) ? 'products' : null
  if (activeKey) node.querySelector(`[data-key="${activeKey}"]`)?.setAttribute('aria-current', 'page')
}

function syncRoute(router, path) {
  const official = isOfficialSitePath(path)
  document.body.classList.toggle('yk-official-site-route', official)
  document.documentElement.classList.toggle('yk-wechat-webview', official && isWechatBrowser())
  if (!official) {
    if (dock) dock.hidden = true
    return
  }

  updateDock(router, path)
  dock.hidden = false
  if (isWechatBrowser()) {
    window.setTimeout(() => { void configureOfficialWechatShare(path) }, 30)
  }
}

export function installOfficialWechatRuntime(router) {
  if (installed || typeof window === 'undefined' || typeof document === 'undefined') return
  installed = true
  router.afterEach((to) => window.setTimeout(() => syncRoute(router, to.path), 0))
  router.isReady().then(() => syncRoute(router, router.currentRoute.value.path))
}
