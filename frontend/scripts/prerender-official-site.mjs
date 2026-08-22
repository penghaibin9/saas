import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import {
  OFFICIAL_SALES_PAGE_MAP,
  OFFICIAL_SEO_ROUTES,
  OFFICIAL_SITE_CONTACT,
  officialCanonicalUrl
} from '../src/config/officialSalesPages.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const frontendRoot = path.resolve(__dirname, '..')
const distDir = path.join(frontendRoot, 'dist')
const baseIndexPath = path.join(distDir, 'index.html')

if (!fs.existsSync(baseIndexPath)) {
  throw new Error(`official prerender: missing ${baseIndexPath}`)
}

const baseHtml = fs.readFileSync(baseIndexPath, 'utf-8')

function escapeHtml(value = '') {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;')
}

function absoluteAssetUrl(assetPath = '') {
  const normalized = String(assetPath || '').startsWith('/') ? assetPath : `/${assetPath}`
  return `${OFFICIAL_SITE_CONTACT.canonicalOrigin}${normalized}`
}

function setTitle(html, title) {
  if (/<title>[\s\S]*?<\/title>/i.test(html)) {
    return html.replace(/<title>[\s\S]*?<\/title>/i, `<title>${escapeHtml(title)}</title>`)
  }
  return html.replace('</head>', `  <title>${escapeHtml(title)}</title>\n</head>`)
}

function upsertHeadTag(html, matcher, tag) {
  if (matcher.test(html)) return html.replace(matcher, tag)
  return html.replace('</head>', `  ${tag}\n</head>`)
}

function injectSeoHead(html, route) {
  const canonical = officialCanonicalUrl(route.path)
  const page = OFFICIAL_SALES_PAGE_MAP[route.path]
  const keywords = page?.keywords?.join(',') || '职业院校,学生全生命周期,SaaS,教务,学工,毕业设计,岗位实习'
  const socialImage = absoluteAssetUrl(page?.screenshots?.[0] || '/official-site/workbench.webp')
  const jsonLd = {
    '@context': 'https://schema.org',
    '@type': route.path === '/contact' ? 'ContactPage' : 'WebPage',
    name: route.title,
    description: route.description,
    url: canonical,
    inLanguage: 'zh-CN',
    primaryImageOfPage: {
      '@type': 'ImageObject',
      url: socialImage
    },
    isPartOf: {
      '@type': 'WebSite',
      name: '跃科职业院校学生全生命周期平台',
      url: OFFICIAL_SITE_CONTACT.canonicalOrigin
    },
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

  let next = setTitle(html, route.title)
  next = upsertHeadTag(next, /<meta\s+name=["']description["'][^>]*>/i,
    `<meta name="description" content="${escapeHtml(route.description)}">`)
  next = upsertHeadTag(next, /<meta\s+name=["']keywords["'][^>]*>/i,
    `<meta name="keywords" content="${escapeHtml(keywords)}">`)
  next = upsertHeadTag(next, /<link\s+rel=["']canonical["'][^>]*>/i,
    `<link rel="canonical" href="${escapeHtml(canonical)}">`)
  next = upsertHeadTag(next, /<meta\s+property=["']og:title["'][^>]*>/i,
    `<meta property="og:title" content="${escapeHtml(route.title)}">`)
  next = upsertHeadTag(next, /<meta\s+property=["']og:description["'][^>]*>/i,
    `<meta property="og:description" content="${escapeHtml(route.description)}">`)
  next = upsertHeadTag(next, /<meta\s+property=["']og:type["'][^>]*>/i,
    '<meta property="og:type" content="website">')
  next = upsertHeadTag(next, /<meta\s+property=["']og:url["'][^>]*>/i,
    `<meta property="og:url" content="${escapeHtml(canonical)}">`)
  next = upsertHeadTag(next, /<meta\s+property=["']og:site_name["'][^>]*>/i,
    '<meta property="og:site_name" content="跃科职业院校学生全生命周期平台">')
  next = upsertHeadTag(next, /<meta\s+property=["']og:locale["'][^>]*>/i,
    '<meta property="og:locale" content="zh_CN">')
  next = upsertHeadTag(next, /<meta\s+property=["']og:image["'][^>]*>/i,
    `<meta property="og:image" content="${escapeHtml(socialImage)}">`)
  next = upsertHeadTag(next, /<meta\s+property=["']og:image:alt["'][^>]*>/i,
    `<meta property="og:image:alt" content="${escapeHtml(`${page?.navTitle || '跃科'}真实产品界面`)}">`)
  next = upsertHeadTag(next, /<meta\s+name=["']twitter:card["'][^>]*>/i,
    '<meta name="twitter:card" content="summary_large_image">')
  next = upsertHeadTag(next, /<meta\s+name=["']twitter:title["'][^>]*>/i,
    `<meta name="twitter:title" content="${escapeHtml(route.title)}">`)
  next = upsertHeadTag(next, /<meta\s+name=["']twitter:description["'][^>]*>/i,
    `<meta name="twitter:description" content="${escapeHtml(route.description)}">`)
  next = upsertHeadTag(next, /<meta\s+name=["']twitter:image["'][^>]*>/i,
    `<meta name="twitter:image" content="${escapeHtml(socialImage)}">`)
  next = next.replace('</head>', `  <script type="application/ld+json">${JSON.stringify(jsonLd)}</script>\n</head>`)
  return next
}

function renderStaticSnapshot(route) {
  const page = OFFICIAL_SALES_PAGE_MAP[route.path]
  if (!page) {
    return `<main data-official-prerender="home"><section><h1>跃科职业院校学生全生命周期 SaaS 平台</h1><p>${escapeHtml(route.description)}</p><p>教务系统 · 学工中心 · 毕业设计 · 岗位实习 · 教师工作台 · 学生服务门户</p><p><a href="${OFFICIAL_SITE_CONTACT.phoneHref}">商务咨询 ${OFFICIAL_SITE_CONTACT.phone}</a></p></section></main>`
  }

  const productLinks = [
    ['/products/academic-affairs', '教务系统'],
    ['/products/student-affairs', '学工中心'],
    ['/products/graduation', '毕业设计'],
    ['/products/internship', '岗位实习']
  ].map(([href, label]) => `<a href="${href}">${label}</a>`).join(' · ')

  const screenshots = (page.screenshots || []).slice(0, 4)
    .map((src, index) => `<figure><img src="${escapeHtml(src)}" alt="${escapeHtml(`${page.navTitle}真实产品界面 ${index + 1}`)}"><figcaption>真实代码运行截图，业务数据来自隔离测试环境</figcaption></figure>`)
    .join('')

  return `<main data-official-prerender="${escapeHtml(page.key)}">
    <article>
      <p>${escapeHtml(page.eyebrow)}</p>
      <h1>${escapeHtml(page.hero)}</h1>
      <p>${escapeHtml(page.description)}</p>
      <p><a href="${OFFICIAL_SITE_CONTACT.phoneHref}">电话咨询 ${OFFICIAL_SITE_CONTACT.phone}</a> · <a href="/contact">联系跃科</a></p>
      <h2>真实产品证据</h2>
      <p>官网仅使用真实系统界面，不把 Playwright/E2E 演示数据包装成真实学校运营数据或客户案例。</p>
      <div>${screenshots}</div>
      <h2>四大核心产品</h2>
      <p>${productLinks}</p>
    </article>
  </main>`
}

function injectSnapshot(html, snapshot) {
  if (/<div\s+id=["']app["']\s*><\/div>/i.test(html)) {
    return html.replace(/<div\s+id=["']app["']\s*><\/div>/i, `<div id="app">${snapshot}</div>`)
  }
  return html
}

function writeRoute(route) {
  let html = injectSeoHead(baseHtml, route)
  html = injectSnapshot(html, renderStaticSnapshot(route))
  const target = route.path === '/'
    ? baseIndexPath
    : path.join(distDir, route.path.replace(/^\/+|\/+$/g, ''), 'index.html')
  fs.mkdirSync(path.dirname(target), { recursive: true })
  fs.writeFileSync(target, html)
}

for (const route of OFFICIAL_SEO_ROUTES) writeRoute(route)

const sitemap = [
  '<?xml version="1.0" encoding="UTF-8"?>',
  '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
  ...OFFICIAL_SEO_ROUTES.map((route) => `  <url><loc>${escapeHtml(officialCanonicalUrl(route.path))}</loc><changefreq>${route.path === '/' ? 'weekly' : 'monthly'}</changefreq><priority>${route.path === '/' ? '1.0' : '0.8'}</priority></url>`),
  '</urlset>'
].join('\n')
fs.writeFileSync(path.join(distDir, 'sitemap.xml'), sitemap)
fs.writeFileSync(path.join(distDir, 'robots.txt'), `User-agent: *\nAllow: /\nSitemap: ${OFFICIAL_SITE_CONTACT.canonicalOrigin}/sitemap.xml\n`)

process.stdout.write(`official prerender: generated ${OFFICIAL_SEO_ROUTES.length} routes, sitemap.xml and robots.txt\n`)
