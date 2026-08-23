import {
  OFFICIAL_SALES_PAGE_MAP,
  OFFICIAL_SEO_ROUTES,
  OFFICIAL_SITE_CONTACT,
  officialCanonicalUrl
} from '../config/officialSalesPages'
import { HOME_FAQS, PRODUCT_STORIES, SALES_STORIES } from '../config/officialWebsiteStory'

const SITE_NAME = '跃科职业院校学生全生命周期平台'
const FALLBACK_SHARE_IMAGE = '/official-site/workbench.webp'
const SEO_ROUTE_MAP = new Map(OFFICIAL_SEO_ROUTES.map((route) => [route.path, route]))
let installed = false

function absoluteAssetUrl(assetPath = '') {
  const value = String(assetPath || FALLBACK_SHARE_IMAGE)
  const normalized = value.startsWith('/') ? value : `/${value}`
  return `${OFFICIAL_SITE_CONTACT.canonicalOrigin}${normalized}`
}

function pageFaqs(path, page) {
  if (path === '/') return HOME_FAQS
  const salesFaqs = SALES_STORIES[path]?.faqs || []
  if (salesFaqs.length) return salesFaqs
  if (page?.type === 'product') return PRODUCT_STORIES[path.split('/').at(-1)]?.faqs || []
  return []
}

function upsertMeta(attribute, key, content) {
  let node = document.head.querySelector(`meta[${attribute}="${key}"]`)
  if (!node) {
    node = document.createElement('meta')
    node.setAttribute(attribute, key)
    document.head.appendChild(node)
  }
  node.setAttribute('content', content)
}

function upsertCanonical(href) {
  let node = document.head.querySelector('link[rel="canonical"]')
  if (!node) {
    node = document.createElement('link')
    node.setAttribute('rel', 'canonical')
    document.head.appendChild(node)
  }
  node.setAttribute('href', href)
}

function removeOfficialJsonLd() {
  document.head.querySelectorAll('script[type="application/ld+json"]').forEach((node) => {
    if (node.hasAttribute('data-official-seo')) {
      node.remove()
      return
    }
    try {
      const payload = JSON.parse(node.textContent || '{}')
      if (payload?.isPartOf?.name === SITE_NAME || payload?.['@type'] === 'FAQPage') node.remove()
    } catch {
      // 非官网 JSON-LD 或格式异常时不碰，避免影响业务系统自己的 head 内容。
    }
  })
}

function appendJsonLd(payload, kind) {
  const node = document.createElement('script')
  node.type = 'application/ld+json'
  node.setAttribute('data-official-seo', kind)
  node.textContent = JSON.stringify(payload)
  document.head.appendChild(node)
}

function buildPageJsonLd(route, page, canonical, socialImage) {
  return {
    '@context': 'https://schema.org',
    '@type': route.path === '/contact' ? 'ContactPage' : 'WebPage',
    name: route.title,
    description: route.description,
    url: canonical,
    inLanguage: 'zh-CN',
    dateModified: route.contentUpdatedAt,
    primaryImageOfPage: { '@type': 'ImageObject', url: socialImage },
    isPartOf: { '@type': 'WebSite', name: SITE_NAME, url: OFFICIAL_SITE_CONTACT.canonicalOrigin },
    about: page?.keywords || [],
    publisher: {
      '@type': 'Organization',
      name: OFFICIAL_SITE_CONTACT.company,
      url: OFFICIAL_SITE_CONTACT.canonicalOrigin,
      telephone: OFFICIAL_SITE_CONTACT.phone.replaceAll(' ', ''),
      contactPoint: {
        '@type': 'ContactPoint',
        contactType: 'sales',
        telephone: OFFICIAL_SITE_CONTACT.phone.replaceAll(' ', ''),
        availableLanguage: ['zh-CN']
      }
    }
  }
}

export function syncOfficialSeo(path = '/') {
  if (typeof document === 'undefined') return false
  const route = SEO_ROUTE_MAP.get(path)
  if (!route) return false

  const page = OFFICIAL_SALES_PAGE_MAP[path]
  const canonical = officialCanonicalUrl(route.path)
  const socialImage = absoluteAssetUrl(page?.screenshots?.[0] || FALLBACK_SHARE_IMAGE)
  const keywords = page?.keywords?.join(',') || '职业院校,学生全生命周期,岗位实习,毕业设计,学工,教务,数字迎新'

  document.title = route.title
  upsertMeta('name', 'description', route.description)
  upsertMeta('name', 'keywords', keywords)
  upsertCanonical(canonical)
  upsertMeta('property', 'og:title', route.title)
  upsertMeta('property', 'og:description', route.description)
  upsertMeta('property', 'og:type', 'website')
  upsertMeta('property', 'og:url', canonical)
  upsertMeta('property', 'og:site_name', SITE_NAME)
  upsertMeta('property', 'og:locale', 'zh_CN')
  upsertMeta('property', 'og:image', socialImage)
  upsertMeta('property', 'og:image:alt', `${page?.navTitle || '跃科'}真实产品界面`)
  upsertMeta('name', 'twitter:card', 'summary_large_image')
  upsertMeta('name', 'twitter:title', route.title)
  upsertMeta('name', 'twitter:description', route.description)
  upsertMeta('name', 'twitter:image', socialImage)

  removeOfficialJsonLd()
  appendJsonLd(buildPageJsonLd(route, page, canonical, socialImage), 'page')
  const faqs = pageFaqs(route.path, page)
  if (faqs.length) {
    appendJsonLd({
      '@context': 'https://schema.org',
      '@type': 'FAQPage',
      mainEntity: faqs.map((item) => ({
        '@type': 'Question',
        name: item.q,
        acceptedAnswer: { '@type': 'Answer', text: item.a }
      }))
    }, 'faq')
  }
  return true
}

function scrollToOfficialHash(hash = '') {
  if (!hash || typeof document === 'undefined') return
  window.setTimeout(() => {
    try {
      const id = decodeURIComponent(String(hash).replace(/^#/, ''))
      if (id) document.getElementById(id)?.scrollIntoView({ block: 'start' })
    } catch {
      // 无效 hash 不应阻断官网导航。
    }
  }, 0)
}

export function installOfficialSeoRuntime(router) {
  if (installed || typeof window === 'undefined' || typeof document === 'undefined') return
  installed = true
  const applyRoute = (route) => {
    const path = String(route?.path || window.location.pathname || '/')
    if (!SEO_ROUTE_MAP.has(path)) return
    syncOfficialSeo(path)
    scrollToOfficialHash(route?.hash || window.location.hash)
  }
  router.afterEach((to) => window.setTimeout(() => applyRoute(to), 0))
  router.isReady().then(() => applyRoute(router.currentRoute.value))
}
