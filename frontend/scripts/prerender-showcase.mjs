import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { checkShowcaseAssets } from './check-showcase-assets.mjs'
import { OFFICIAL_SITE_CONTACT } from '../src/config/officialSalesPages.js'
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const releasePath = path.join(root, 'public/official-site/showcase-20260909/release.json')
// Keep the approved old homepage until the complete, hash-verified image release exists.
if (fs.existsSync(releasePath)) {
  const report = checkShowcaseAssets(root)
  if (!report.ready) throw new Error(`Incomplete official showcase assets: ${report.errors.join('; ')}`)
  const file = path.join(root, 'dist/index.html')
  let html = fs.readFileSync(file, 'utf8')
  const template = fs.readFileSync(path.join(root, 'src/components/official-site/showcase/approved-home.html'), 'utf8')
  const marker = /<div\s+id=["']app["'][^>]*>/i.exec(html)
  if (!marker) throw new Error('Cannot find the public app root in the built index')
  const start = marker.index + marker[0].length
  const divs = /<div\b[^>]*>|<\/div\s*>/gi
  divs.lastIndex = start
  let depth = 1, end = -1, token
  while ((token = divs.exec(html))) {
    depth += /^<\//.test(token[0]) ? -1 : 1
    if (!depth) { end = token.index; break }
  }
  if (end < 0) throw new Error('Unbalanced public app root')
  html = html.slice(0, start) + template + html.slice(end)
  const title = '跃科｜服务学生成长，成就教师发展'
  const description = '学生全生命周期管理 × 高校人事管理与教师发展。教务、学工、岗位实习、毕业设计 PC 各十页，教师与学生微信小程序各十页，预约完整产品讲解。'
  const image = `${OFFICIAL_SITE_CONTACT.canonicalOrigin}/official-site/showcase-20260909/scenes/overview.webp`
  html = html.replace(/<title>[\s\S]*?<\/title>/i, `<title>${title}</title>`)
  for (const [kind, key, value] of [['name','description',description], ['property','og:title',title], ['property','og:description',description], ['property','og:image',image], ['property','og:image:alt','跃科彩色校园品牌场景'], ['property','og:site_name','跃科高校师生全生命周期解决方案'], ['name','twitter:title',title], ['name','twitter:description',description], ['name','twitter:image',image]]) {
    const re = new RegExp(`<meta\\s+${kind}=["']${key}["'][^>]*>`, 'i')
    const tag = `<meta ${kind}="${key}" content="${value}">`
    html = re.test(html) ? html.replace(re, tag) : html.replace('</head>', tag + '\n</head>')
  }
  const styles = fs.readdirSync(path.join(root, 'dist/assets')).filter(name => name.endsWith('.css') && fs.readFileSync(path.join(root, 'dist/assets', name), 'utf8').includes('#ykw-site'))
  for (const style of styles) html = html.replace('</head>', `<link rel="stylesheet" href="/assets/${style}" data-showcase-prerender>\n</head>`)
  const ld = { '@context': 'https://schema.org', '@type': 'WebPage', name: title, description, url: OFFICIAL_SITE_CONTACT.canonicalOrigin, inLanguage: 'zh-CN', primaryImageOfPage: image, publisher: { '@type': 'Organization', name: OFFICIAL_SITE_CONTACT.company } }
  html = html.replace(/<script type="application\/ld\+json" data-official-seo="page">[\s\S]*?<\/script>/, `<script type="application/ld+json" data-official-seo="page">${JSON.stringify(ld)}</script>`)
  fs.writeFileSync(file, html)
  console.log('Approved 60-page showcase prerendered; 143 asset hashes verified.')
} else console.log('Showcase release not installed: preserved the working legacy homepage.')
