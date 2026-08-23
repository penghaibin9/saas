import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'
import { fileURLToPath } from 'node:url'
import { OFFICIAL_SALES_PAGE_MAP, OFFICIAL_SEO_ROUTES, OFFICIAL_SITE_CONTACT, officialCanonicalUrl } from '../src/config/officialSalesPages.js'
import { HOME_FAQS, HOME_PAIN_POINTS, LIFECYCLE_STAGES, PRODUCT_STORIES, SALES_STORIES } from '../src/config/officialWebsiteStory.js'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const frontendRoot = path.resolve(__dirname, '..')
const distDir = path.join(frontendRoot, 'dist')
const baseIndexPath = path.join(distDir, 'index.html')
if (!fs.existsSync(baseIndexPath)) throw new Error(`official prerender: missing ${baseIndexPath}`)
const baseHtml = fs.readFileSync(baseIndexPath, 'utf-8')

function escapeHtml(value = '') { return String(value).replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;').replaceAll("'", '&#39;') }
function absoluteAssetUrl(assetPath = '') { const normalized = String(assetPath || '').startsWith('/') ? assetPath : `/${assetPath}`; return `${OFFICIAL_SITE_CONTACT.canonicalOrigin}${normalized}` }
function setTitle(html, title) { return /<title>[\s\S]*?<\/title>/i.test(html) ? html.replace(/<title>[\s\S]*?<\/title>/i, `<title>${escapeHtml(title)}</title>`) : html.replace('</head>', `  <title>${escapeHtml(title)}</title>\n</head>`) }
function upsertHeadTag(html, matcher, tag) { return matcher.test(html) ? html.replace(matcher, tag) : html.replace('</head>', `  ${tag}\n</head>`) }
function pageFaqs(route, page) {
  if (route.path === '/') return HOME_FAQS
  const sales = SALES_STORIES[route.path]?.faqs || []
  if (sales.length) return sales
  if (page?.type === 'product') return PRODUCT_STORIES[route.path.split('/').at(-1)]?.faqs || []
  return []
}

function injectSeoHead(html, route) {
  const canonical = officialCanonicalUrl(route.path)
  const page = OFFICIAL_SALES_PAGE_MAP[route.path]
  const keywords = page?.keywords?.join(',') || '职业院校,学生全生命周期,岗位实习,毕业设计,学工,教务,数字迎新'
  const socialImage = absoluteAssetUrl(page?.screenshots?.[0] || '/official-site/workbench.webp')
  const faqs = pageFaqs(route, page)
  const jsonLd = {
    '@context': 'https://schema.org', '@type': route.path === '/contact' ? 'ContactPage' : 'WebPage',
    name: route.title, description: route.description, url: canonical, inLanguage: 'zh-CN', dateModified: route.contentUpdatedAt,
    primaryImageOfPage: { '@type': 'ImageObject', url: socialImage },
    isPartOf: { '@type': 'WebSite', name: '跃科职业院校学生全生命周期平台', url: OFFICIAL_SITE_CONTACT.canonicalOrigin },
    about: page?.keywords || [],
    publisher: { '@type': 'Organization', name: OFFICIAL_SITE_CONTACT.company, url: OFFICIAL_SITE_CONTACT.canonicalOrigin, telephone: OFFICIAL_SITE_CONTACT.phone.replaceAll(' ', ''), contactPoint: { '@type': 'ContactPoint', contactType: 'sales', telephone: OFFICIAL_SITE_CONTACT.phone.replaceAll(' ', ''), availableLanguage: ['zh-CN'] } }
  }
  let next = setTitle(html, route.title)
  next = upsertHeadTag(next, /<meta\s+name=["']description["'][^>]*>/i, `<meta name="description" content="${escapeHtml(route.description)}">`)
  next = upsertHeadTag(next, /<meta\s+name=["']keywords["'][^>]*>/i, `<meta name="keywords" content="${escapeHtml(keywords)}">`)
  next = upsertHeadTag(next, /<link\s+rel=["']canonical["'][^>]*>/i, `<link rel="canonical" href="${escapeHtml(canonical)}">`)
  next = upsertHeadTag(next, /<meta\s+property=["']og:title["'][^>]*>/i, `<meta property="og:title" content="${escapeHtml(route.title)}">`)
  next = upsertHeadTag(next, /<meta\s+property=["']og:description["'][^>]*>/i, `<meta property="og:description" content="${escapeHtml(route.description)}">`)
  next = upsertHeadTag(next, /<meta\s+property=["']og:type["'][^>]*>/i, '<meta property="og:type" content="website">')
  next = upsertHeadTag(next, /<meta\s+property=["']og:url["'][^>]*>/i, `<meta property="og:url" content="${escapeHtml(canonical)}">`)
  next = upsertHeadTag(next, /<meta\s+property=["']og:site_name["'][^>]*>/i, '<meta property="og:site_name" content="跃科职业院校学生全生命周期平台">')
  next = upsertHeadTag(next, /<meta\s+property=["']og:locale["'][^>]*>/i, '<meta property="og:locale" content="zh_CN">')
  next = upsertHeadTag(next, /<meta\s+property=["']og:image["'][^>]*>/i, `<meta property="og:image" content="${escapeHtml(socialImage)}">`)
  next = upsertHeadTag(next, /<meta\s+property=["']og:image:alt["'][^>]*>/i, `<meta property="og:image:alt" content="${escapeHtml(`${page?.navTitle || '跃科'}真实产品界面`)}">`)
  next = upsertHeadTag(next, /<meta\s+name=["']twitter:card["'][^>]*>/i, '<meta name="twitter:card" content="summary_large_image">')
  next = upsertHeadTag(next, /<meta\s+name=["']twitter:title["'][^>]*>/i, `<meta name="twitter:title" content="${escapeHtml(route.title)}">`)
  next = upsertHeadTag(next, /<meta\s+name=["']twitter:description["'][^>]*>/i, `<meta name="twitter:description" content="${escapeHtml(route.description)}">`)
  next = upsertHeadTag(next, /<meta\s+name=["']twitter:image["'][^>]*>/i, `<meta name="twitter:image" content="${escapeHtml(socialImage)}">`)
  next = next.replace('</head>', `  <script type="application/ld+json">${JSON.stringify(jsonLd)}</script>\n</head>`)
  if (faqs.length) {
    const faqLd = { '@context': 'https://schema.org', '@type': 'FAQPage', mainEntity: faqs.map((item) => ({ '@type': 'Question', name: item.q, acceptedAnswer: { '@type': 'Answer', text: item.a } })) }
    next = next.replace('</head>', `  <script type="application/ld+json">${JSON.stringify(faqLd)}</script>\n</head>`)
  }
  return next
}

function renderScreenshots(page) {
  return (page?.screenshots || []).slice(0, 4).map((src, index) => `<figure><img src="${escapeHtml(src)}" alt="${escapeHtml(`${page.navTitle}真实产品界面 ${index + 1}`)}" width="1536" height="1024"><figcaption>${escapeHtml(page.navTitle)}真实代码运行界面；业务数据来自隔离测试环境，不代表客户运营规模。</figcaption></figure>`).join('')
}
function renderFaqs(faqs) { return faqs.length ? `<section><h2>常见问题</h2>${faqs.map((item) => `<details><summary>${escapeHtml(item.q)}</summary><p>${escapeHtml(item.a)}</p></details>`).join('')}</section>` : '' }

function renderHomeSnapshot(route) {
  const lifecycle = LIFECYCLE_STAGES.map((item) => `<li><a href="${escapeHtml(item.route)}"><strong>${escapeHtml(item.stage)} · ${escapeHtml(item.title)}</strong><span>${escapeHtml(item.desc)}</span></a></li>`).join('')
  const pains = HOME_PAIN_POINTS.map((item) => `<article><h2>${escapeHtml(item.title)}</h2><p>${escapeHtml(item.answer)}</p></article>`).join('')
  return `<main data-official-prerender="home"><article>
    <p>面向职业院校的学生全生命周期数字化平台</p><h1>让职业院校学生业务真正连起来</h1><p>${escapeHtml(route.description)}</p>
    <p><a href="/products">查看产品中心</a> · <a href="/contact">预约产品演示</a> · <a href="${OFFICIAL_SITE_CONTACT.phoneHref}">电话 ${OFFICIAL_SITE_CONTACT.phone}</a></p>
    <section aria-label="学校真实痛点">${pains}</section>
    <section><h2>学生生命周期业务地图</h2><ol>${lifecycle}</ol></section>
    <section><h2>四大核心产品</h2><p><a href="/products/internship">岗位实习</a> · <a href="/products/graduation">毕业设计</a> · <a href="/products/student-affairs">学工中心</a> · <a href="/products/academic-affairs">教务系统</a></p></section>
    <section><h2>统一工作台、审批与消息</h2><p>重要事项汇聚到工作台、待办、审批和消息，减少老师在不同模块之间寻找今天要处理的事情。</p></section>
    <section><h2>平台底座与实施交付</h2><p>多学校租户、组织身份、角色权限、数据范围、学校品牌、审计、数据交换，与初始化、历史数据导入、上线检查、验收和后续升级共同支撑学校项目。</p></section>
    <p>公开内容最近更新：<time datetime="${escapeHtml(route.contentUpdatedAt)}">${escapeHtml(route.contentUpdatedAt)}</time></p>
    ${renderFaqs(HOME_FAQS)}
  </article></main>`
}

function renderStaticSnapshot(route) {
  const page = OFFICIAL_SALES_PAGE_MAP[route.path]
  if (!page) return renderHomeSnapshot(route)
  const productLinks = [['/products/academic-affairs','教务系统'],['/products/student-affairs','学工中心'],['/products/graduation','毕业设计'],['/products/internship','岗位实习']].map(([href,label]) => `<a href="${href}">${label}</a>`).join(' · ')
  const story = SALES_STORIES[route.path]
  const productStory = page.type === 'product' ? PRODUCT_STORIES[route.path.split('/').at(-1)] : null
  const facts = story?.facts || (productStory?.fact ? [productStory.fact] : [])
  const process = story?.process || []
  const faqs = pageFaqs(route, page)
  return `<main data-official-prerender="${escapeHtml(page.key)}"><article>
    <p>${escapeHtml(page.eyebrow)}</p><h1>${escapeHtml(page.hero)}</h1><p>${escapeHtml(page.description)}</p>
    <p><a href="${OFFICIAL_SITE_CONTACT.phoneHref}">电话咨询 ${OFFICIAL_SITE_CONTACT.phone}</a> · <a href="/contact">预约产品演示</a></p>
    ${process.length ? `<section><h2>业务怎么推进</h2><ol>${process.map((step) => `<li>${escapeHtml(step)}</li>`).join('')}</ol></section>` : ''}
    ${facts.length ? `<section><h2>可核验产品事实</h2><ul>${facts.map((fact) => `<li>${escapeHtml(fact)}</li>`).join('')}</ul></section>` : ''}
    ${productStory?.roles?.length ? `<section><h2>不同角色怎么工作</h2>${productStory.roles.map((item) => `<article><h3>${escapeHtml(item.role)}</h3><p>${escapeHtml(item.work)}</p></article>`).join('')}</section>` : ''}
    ${productStory?.outcomes?.length ? `<section><h2>最终沉淀什么</h2><ul>${productStory.outcomes.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul></section>` : ''}
    <section><h2>真实产品证据</h2><p>官网仅使用真实系统界面，不把 Playwright/E2E 测试数据包装成真实学校客户案例。</p><div>${renderScreenshots(page)}</div></section>
    <section><h2>四大核心产品</h2><p>${productLinks}</p></section>
    <p>公开内容最近更新：<time datetime="${escapeHtml(route.contentUpdatedAt)}">${escapeHtml(route.contentUpdatedAt)}</time></p>
    ${renderFaqs(faqs)}
  </article></main>`
}

function injectSnapshot(html, snapshot) { return /<div\s+id=["']app["']\s*><\/div>/i.test(html) ? html.replace(/<div\s+id=["']app["']\s*><\/div>/i, `<div id="app">${snapshot}</div>`) : html }
function writeRoute(route) {
  let html = injectSeoHead(baseHtml, route); html = injectSnapshot(html, renderStaticSnapshot(route))
  const target = route.path === '/' ? baseIndexPath : path.join(distDir, route.path.replace(/^\/+|\/+$/g, ''), 'index.html')
  fs.mkdirSync(path.dirname(target), { recursive: true }); fs.writeFileSync(target, html)
}
for (const route of OFFICIAL_SEO_ROUTES) writeRoute(route)
const sitemap = ['<?xml version="1.0" encoding="UTF-8"?>','<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',...OFFICIAL_SEO_ROUTES.map((route) => `  <url><loc>${escapeHtml(officialCanonicalUrl(route.path))}</loc><lastmod>${escapeHtml(route.contentUpdatedAt)}</lastmod><changefreq>${route.path === '/' ? 'weekly' : 'monthly'}</changefreq><priority>${route.path === '/' ? '1.0' : '0.8'}</priority></url>`),'</urlset>'].join('\n')
fs.writeFileSync(path.join(distDir, 'sitemap.xml'), sitemap)
fs.writeFileSync(path.join(distDir, 'robots.txt'), `User-agent: *\nAllow: /\nSitemap: ${OFFICIAL_SITE_CONTACT.canonicalOrigin}/sitemap.xml\n`)
process.stdout.write(`official prerender: generated ${OFFICIAL_SEO_ROUTES.length} routes, visible facts/FAQ, sitemap.xml and robots.txt\n`)