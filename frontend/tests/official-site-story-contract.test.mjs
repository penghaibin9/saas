import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { OFFICIAL_SALES_PAGE_MAP, OFFICIAL_SEO_ROUTES } from '../src/config/officialSalesPages.js'
import { HOME_FAQS, HOME_PAIN_POINTS, IMPLEMENTATION_STEPS, LIFECYCLE_STAGES, PLATFORM_FOUNDATION, PRODUCT_STORIES, WORK_HUB_PROOFS } from '../src/config/officialWebsiteStory.js'

const here = path.dirname(fileURLToPath(import.meta.url))
const root = path.resolve(here, '..')
const homeSource = fs.readFileSync(path.join(root, 'src/views/PortalHomeView.vue'), 'utf8')
const salesSource = fs.readFileSync(path.join(root, 'src/views/official-site/OfficialSalesPageView.vue'), 'utf8')
const prerenderSource = fs.readFileSync(path.join(root, 'scripts/prerender-official-site.mjs'), 'utf8')
const publicAsset = (url) => path.join(root, 'public', url.replace(/^\//, ''))

test('homepage keeps a concise sales narrative, visible system access and GEO answer layers', () => {
  assert.equal(HOME_PAIN_POINTS.length, 4)
  assert.equal(LIFECYCLE_STAGES.length, 6)
  assert.equal(WORK_HUB_PROOFS.length, 3)
  assert.ok(PLATFORM_FOUNDATION.length >= 8)
  assert.equal(IMPLEMENTATION_STEPS.length, 9)
  assert.ok(HOME_FAQS.length >= 5)
  for (const marker of ['id="login"', 'id="lifecycle"', 'id="products"', 'yk-home-trust-section', 'id="platform"', 'id="delivery"', 'id="faq"']) {
    assert.ok(homeSource.includes(marker), `missing homepage story section: ${marker}`)
  }
  for (const marker of ['登录系统', '进入管理工作台', '进入学生门户', '企业注册 / 登录', '<time :datetime="contentUpdatedAt">']) {
    assert.ok(homeSource.includes(marker), `missing homepage sales/GEO marker: ${marker}`)
  }
  for (const removedSection of ['id="pain"', 'id="work-hub"', 'id="orientation"', 'id="devices"', 'id="access"']) {
    assert.ok(!homeSource.includes(removedSection), `homepage should route detail content away from ${removedSection}`)
  }
})

test('official sales information architecture includes product center, orientation, platform and company pages', () => {
  for (const route of ['/products', '/solutions/orientation', '/platform', '/about', '/privacy', '/terms', '/support']) {
    assert.ok(OFFICIAL_SALES_PAGE_MAP[route], `missing official sales route ${route}`)
    assert.ok(OFFICIAL_SEO_ROUTES.some((item) => item.path === route), `missing SEO route ${route}`)
  }
  assert.ok(!OFFICIAL_SALES_PAGE_MAP['/solutions/integration'].title.includes('CAS'))
  assert.ok(!OFFICIAL_SALES_PAGE_MAP['/solutions/integration'].keywords.includes('CAS 单点登录'))
})

test('new P0 evidence images are real public assets, not remote or generated placeholders', () => {
  const required = [
    '/official-site/approval-center.webp', '/official-site/message-center.webp', '/official-site/orientation-overview.webp',
    '/official-site/orientation-progress.webp', '/official-site/leadership-cockpit.webp',
    '/official-site/student-affairs-dashboard.png', '/official-site/student-affairs-master.png'
  ]
  for (const asset of required) {
    assert.ok(fs.existsSync(publicAsset(asset)), `missing real official-site evidence ${asset}`)
    assert.ok(fs.statSync(publicAsset(asset)).size > 10_000, `evidence asset unexpectedly small ${asset}`)
  }
})

test('all four product pages explain role work, evidence outcomes and FAQ', () => {
  for (const slug of ['academic-affairs', 'student-affairs', 'graduation', 'internship']) {
    const story = PRODUCT_STORIES[slug]
    assert.ok(story?.fact)
    assert.ok(story.roles.length >= 4)
    assert.ok(story.outcomes.length >= 6)
    assert.ok(story.faqs.length >= 2)
  }
})

test('GEO prerender exposes visible facts, FAQ, true updated date and sitemap lastmod', () => {
  for (const marker of ['FAQPage', 'dateModified', '<lastmod>', '<time datetime=', '可核验产品事实', '学生生命周期业务地图']) {
    assert.ok(prerenderSource.includes(marker), `missing GEO marker ${marker}`)
  }
})

test('website lead surfaces only known-safe backend failure messages', () => {
  assert.ok(salesSource.includes("detail.startsWith('在线咨询暂时不可用')"))
  assert.ok(salesSource.includes("detail.startsWith('提交过于频繁')"))
  assert.ok(salesSource.includes('提交失败，请直接电话联系'))
})
