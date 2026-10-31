import { OFFICIAL_PRODUCT_LIST } from '../config/officialProducts'
import { COMPANY_PRODUCTS, solutionContactRoute } from '../config/companyProducts'
import { OFFICIAL_SALES_PAGE_MAP, OFFICIAL_SALES_PAGES, OFFICIAL_SITE_CONTACT, OFFICIAL_SEO_ROUTES } from '../config/officialSalesPages'
import { API_BASE_URL, API_PREFIX } from './http/config'
import '../styles/official-mobile-wechat.css'

const WECHAT_SDK_URL = 'https://res.wx.qq.com/open/js/jweixin-1.6.0.js'
const SIGNATURE_ENDPOINT = `${API_BASE_URL}${API_PREFIX}/notification/website-wechat-signature`
const PRODUCT_PATHS = new Set(OFFICIAL_SALES_PAGES.filter(item => ['product', 'local-product'].includes(item.type)).map(item => item.path))
const OFFICIAL_PATHS = new Set(OFFICIAL_SALES_PAGES.map((item) => item.path))
const PRODUCT_BY_PATH = new Map(OFFICIAL_PRODUCT_LIST.map((item) => [`/products/${item.slug}`, item]))
const FALLBACK_SHARE_IMAGE = '/official-site/workbench.webp'
const WECHAT_ENTRY_URL = typeof window !== 'undefined' ? window.location.href.split('#')[0] : ''

let sdkPromise = null
let installed = false
let dock = null
let lastConfiguredShareKey = ''
let shareQueue = Promise.resolve()

export function isWechatBrowser(userAgent = typeof navigator !== 'undefined' ? navigator.userAgent : '') {
  return /MicroMessenger/i.test(String(userAgent || ''))
}

export function isIosWechat(userAgent = typeof navigator !== 'undefined' ? navigator.userAgent : '') {
  const ua = String(userAgent || '')
  return isWechatBrowser(ua) && /iPhone|iPad|iPod/i.test(ua)
}

export function isOfficialSitePath(path = '') {
  return path === '/' || PRODUCT_PATHS.has(path) || OFFICIAL_PATHS.has(path)
}

export function resolveWechatSignatureUrl(
  currentUrl = typeof window !== 'undefined' ? window.location.href : '',
  userAgent = typeof navigator !== 'undefined' ? navigator.userAgent : ''
) {
  const current = String(currentUrl || '').split('#')[0]
  // iOS 微信的 history-SPA 验签仍可能绑定首次落地 URL；Android 使用当前地址。
  // 分享出去的 link 仍始终使用当前业务页 canonical URL，不使用入口 URL。
  return isIosWechat(userAgent) ? (WECHAT_ENTRY_URL || current) : current
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
    title: OFFICIAL_SEO_ROUTES[0].title,
    desc: OFFICIAL_SEO_ROUTES[0].description,
    link: OFFICIAL_SITE_CONTACT.canonicalOrigin,
    imgUrl: absoluteUrl(document.querySelector('#ykw-site') ? '/official-site/showcase-20260909/scenes/overview.webp' : FALLBACK_SHARE_IMAGE)
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

  const signatureUrl = resolveWechatSignatureUrl()
  const shareKey = `${signatureUrl}|${path}|${document.querySelector('#ykw-site') ? 'showcase' : 'legacy'}`
  if (shareKey === lastConfiguredShareKey) return { status: 'already-configured' }

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
      const onReady = () => {
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
          lastConfiguredShareKey = shareKey
          finish('ready')
        } catch {
          finish('share-api-error')
        }
      }

      wx.error?.(() => finish('config-error'))
      // 按微信标准顺序先注入 config，再注册 ready；重复配置时也不会误用上一条路由的 ready 状态。
      wx.config({
        debug: false,
        appId: signed.appId,
        timestamp: signed.timestamp,
        nonceStr: signed.nonceStr,
        signature: signed.signature,
        jsApiList: ['updateAppMessageShareData', 'updateTimelineShareData']
      })
      wx.ready(onReady)
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
    <a href="/products" data-route="/products" data-key="products"><span aria-hidden="true">▦</span><b>产品中心</b></a>
    <a href="/contact" data-route="/contact" data-key="contact"><span aria-hidden="true">✦</span><b>预约产品演示</b></a>
    <a href="/#login" data-route="/#login" data-key="login"><span aria-hidden="true">↗</span><b>系统登录</b></a>
  `
  dock.addEventListener('click', (event) => {
    const target = event.target instanceof Element ? event.target : null
    const link = target?.closest('a[data-route]')
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
  const productKey = COMPANY_PRODUCTS.find(product => product.path === path)?.key || PRODUCT_BY_PATH.get(path)?.slug
  const solution = solutionContactRoute(path)
  const solutionUrl = solution.query ? '/contact?' + new URLSearchParams(solution.query) : '/contact'
  const contactRoute = solution.query ? solutionUrl : productKey ? `/contact?product=${encodeURIComponent(productKey)}` : path === '/contact' ? router.currentRoute.value.fullPath : solutionUrl
  const contactLink = node.querySelector('[data-key="contact"]')
  if (contactLink) {
    contactLink.href = contactRoute
    contactLink.dataset.route = contactRoute
  }

  node.querySelectorAll('a[data-key]').forEach((link) => link.removeAttribute('aria-current'))
  const activeKey = path === '/' ? 'home' : path === '/contact' ? 'contact' : path === '/products' || PRODUCT_PATHS.has(path) ? 'products' : null
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
    // 串行配置，避免 router.isReady 与 afterEach 在首屏同时触发 wx.config 造成竞态。
    shareQueue = shareQueue.then(() => configureOfficialWechatShare(path)).catch(() => ({ status: 'unavailable' }))
  }
}

export function installOfficialWechatRuntime(router) {
  if (installed || typeof window === 'undefined' || typeof document === 'undefined') return
  installed = true
  router.afterEach((to) => window.setTimeout(() => syncRoute(router, to.path), 0))
  router.isReady().then(() => syncRoute(router, router.currentRoute.value.path))
}


// Refresh through the existing serialized share queue after the approved homepage is mounted.
export function refreshOfficialHomeShare() {
  shareQueue = shareQueue.then(() => typeof window !== 'undefined' && window.location.pathname === '/' ? configureOfficialWechatShare('/') : { status: 'not-applicable' }).catch(() => ({ status: 'unavailable' }))
  return shareQueue
}
