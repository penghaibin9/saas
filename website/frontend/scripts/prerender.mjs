import { readFile, writeFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { render } from '../.ssr/entry-server.js'
import { OFFICIAL_SEO_ROUTES, OFFICIAL_SITE_CONTACT, OFFICIAL_SALES_PAGE_MAP } from '../src/config/officialSalesPages.js'
import { searchGraph, searchModifiedAt, shareImage } from '../src/services/officialSearchData.js'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const dist = path.join(root, 'dist')
const template = await readFile(path.join(dist, 'index.html'), 'utf8')
const manifest = JSON.parse(await readFile(path.join(dist, '.vite/manifest.json'), 'utf8'))
const existingCss = new Set([...template.matchAll(/<link[^>]+href="([^"]+)"[^>]*>/g)].map(match => match[1]))
const css = [...new Set(Object.values(manifest).flatMap(entry => entry.css || []))].filter(file => !existingCss.has('/' + file))
const escape = value => String(value).replaceAll('&', '&amp;').replaceAll('"', '&quot;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
for (const route of [...OFFICIAL_SEO_ROUTES, { path: '/manage', title: '官网内容管理｜跃科', noindex: true }, { path: '/404', title: '页面不存在｜跃科', noindex: true }]) {
  const canonical = `${OFFICIAL_SITE_CONTACT.canonicalOrigin}${route.path === '/' ? '/' : route.path}`
  const image = `${OFFICIAL_SITE_CONTACT.canonicalOrigin}${shareImage(route.path)}`
  const head = [
    `<title>${escape(route.title)}</title>`,
    `<meta name="robots" content="${route.noindex ? 'noindex,nofollow' : 'index,follow,max-image-preview:large'}">`,
    ...(!route.noindex ? [
      `<meta name="description" content="${escape(route.description)}">`,
      `<link rel="canonical" href="${escape(canonical)}">`,
      `<meta property="og:title" content="${escape(route.title)}">`,
      `<meta property="og:description" content="${escape(route.description)}">`,
      `<meta property="og:url" content="${escape(canonical)}">`,
      `<meta property="og:image" content="${escape(image)}">`,
      `<meta property="og:type" content="website">`,
      `<script type="application/ld+json" data-official-seo="graph">${JSON.stringify(searchGraph(route.path)).replaceAll('<', '\\u003c')}</script>`
    ] : []),
    ...css.map(file => `<link rel="stylesheet" href="/${file}">`)
  ].join('\n')
  const html = template.replace(/<title>.*?<\/title>/, '').replace('<!--website-head-->', head)
    .replace('<!--website-content-->', await render(route.path)).replace('<body>', `<body data-prerendered="true"${route.path === '/' ? ' data-yueke-showcase="active"' : ''}>`)
  const target = route.path === '/404' ? path.join(dist, '404.html') : path.join(dist, route.path.slice(1), 'index.html')
  await mkdir(path.dirname(target), { recursive: true }); await writeFile(target, html)
}
const urls = OFFICIAL_SEO_ROUTES.map(route => `<url><loc>${escape(OFFICIAL_SITE_CONTACT.canonicalOrigin + route.path)}</loc><lastmod>${escape(searchModifiedAt(route.path))}</lastmod></url>`).join('')
await writeFile(path.join(dist, 'sitemap-pages.xml'), `<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">${urls}</urlset>`)
await writeFile(path.join(dist, 'sitemap.xml'), `<?xml version="1.0" encoding="UTF-8"?><sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><sitemap><loc>${OFFICIAL_SITE_CONTACT.canonicalOrigin}/sitemap-pages.xml</loc></sitemap><sitemap><loc>${OFFICIAL_SITE_CONTACT.canonicalOrigin}/news/sitemap.xml</loc></sitemap></sitemapindex>`)
await writeFile(path.join(dist, 'robots.txt'), `User-agent: *\nAllow: /\nDisallow: /manage\nDisallow: /api/\nSitemap: ${OFFICIAL_SITE_CONTACT.canonicalOrigin}/sitemap.xml\n`)
console.log(`已预渲染 ${OFFICIAL_SEO_ROUTES.length} 个公开页面和独立后台入口。`)
