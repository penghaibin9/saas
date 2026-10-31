import test from 'node:test'
import assert from 'node:assert/strict'
import { OFFICIAL_SEO_ROUTES } from '../src/config/officialSalesPages.js'
import { COMPANY_PRODUCTS, PRODUCT_DOMAINS, PRODUCT_INTEREST_BY_SLUG } from '../src/config/companyProducts.js'
const origin = process.env.WEBSITE_TEST_ORIGIN || 'http://127.0.0.1:5210'
if (!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(origin)) throw new Error('仅允许本机独立官网验收地址')
test('every public deep link returns its own readable content without JavaScript', async () => {
  for (const route of OFFICIAL_SEO_ROUTES) {
    const response = await fetch(origin + route.path)
    assert.equal(response.status, 200, route.path)
    const html = await response.text()
    assert.ok(html.includes(`<title>${route.title}</title>`), `${route.path} returned the wrong page`)
    assert.match(html, /<h1(?:\s[^>]*)?>[^<]+/, route.path)
    assert.ok(html.includes(`href="https://www.hnyueke.com${route.path}"`), route.path)
    if (route.path !== '/') assert.ok(!html.includes('id="ykw-site"'), 'deep link must not fall back to the homepage')
  }
})
test('management is isolated and excluded from indexing', async () => {
  const response = await fetch(origin + '/manage')
  const html = await response.text()
  assert.equal(response.status, 200)
  assert.match(html, /noindex,nofollow/)
  assert.ok(!html.includes('id="ykw-site"'))
  assert.equal((await fetch(origin + '/api/manage/news/packages')).status, 401)
})
test('unknown pages have a real not-found status', async () => {
  const response = await fetch(origin + '/does-not-exist')
  assert.equal(response.status, 404)
  assert.match(await response.text(), /页面不存在/)
})
test('company directory serves every product and consultation entry without JavaScript', async () => {
  const html = await (await fetch(origin + '/products')).text()
  for (const domain of PRODUCT_DOMAINS) assert.ok(html.includes(`id="domain-${domain.key}"`), domain.name)
  for (const product of COMPANY_PRODUCTS) {
    assert.ok(html.includes(product.name), product.name)
    const target = product.path || `/contact?product=${product.key}`
    assert.ok(html.includes(`href="${target}"`), `${product.name} has no entry`)
    const response = await fetch(origin + target)
    assert.equal(response.status, 200, target)
    if (!product.path) assert.ok((await response.text()).includes(PRODUCT_INTEREST_BY_SLUG[product.key]), `${product.name} cannot be requested`)
  }
  for (const key of ['academic', 'affairs', 'graduation', 'internship']) {
    const src = `/official-site/showcase-20260909/boards/${key}.webp`
    assert.ok(html.includes(src), `${key} dashboard is absent`)
    const response = await fetch(origin + src)
    assert.equal(response.status, 200, src)
    assert.match(response.headers.get('content-type'), /image\/webp/)
  }
})
test('sitemap includes public pages and independent news', async () => {
  assert.match(await (await fetch(origin + '/sitemap.xml')).text(), /https:\/\/www.hnyueke.com\/news\/sitemap.xml/)
  const pages = await (await fetch(origin + '/sitemap-pages.xml')).text()
  assert.ok(!pages.includes('/manage'))
  assert.equal((await fetch(origin + '/news')).status, 200)
  assert.equal((await fetch(origin + '/news/sitemap.xml')).status, 200)
})

test('company and newsroom share styling, while product chapters and original images remain reachable', async () => {
  for (const path of ['/products', '/news', '/about']) {
    const html = await (await fetch(origin + path)).text()
    for (const value of ['/official-site/company-shell.css', 'class="brand-mark"', 'class="footer-wrap"', 'tel:13549666867']) assert.ok(html.includes(value), `${path}: ${value}`)
  }
  const html = await (await fetch(origin + '/products/academic-affairs')).text()
  assert.ok(html.indexOf('academic-course-catalog.png') < html.indexOf('academic-workbench.png'), 'the positive course screen precedes the retained blocker example')
  for (const id of ['overview', 'capabilities', 'roles', 'screens', 'devices', 'evidence', 'faq']) {
    assert.ok(html.includes(`href="#${id}"`) && html.includes(`id="${id}"`), `${id} chapter must have a real destination`)
  }
})
