import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'

test('an isolated future product flows into domains, paths and consultation without copied navigation', async () => {
  const catalog = JSON.parse(await readFile(new URL('../../products.json', import.meta.url), 'utf8'))
  const sample = { key: 'extension-check', name: '仅供目录扩展验收', interest: '扩展验收意向', domain: 'campus', path: '/products/extension-check', public: true }
  catalog.products.push(sample)
  const source = (await readFile(new URL('../src/config/companyProducts.js', import.meta.url), 'utf8'))
    .replace(/import \{ OFFICIAL_SALES_PAGE_MAP \}[^\n]+/, `const OFFICIAL_SALES_PAGE_MAP = ${JSON.stringify({[sample.path]:{description:'隔离样本正文'}})}`)
    .replace(/import catalog[^\n]+/, `const catalog = ${JSON.stringify(catalog)}`)
  const module = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
  assert.equal(module.productsInDomain('campus').find(p => p.key === sample.key).introduction, '隔离样本正文')
  assert.equal(module.COMPANY_PRODUCTS.find(p => p.key === sample.key).path, sample.path)
  assert.equal(module.PRODUCT_INTEREST_BY_SLUG[sample.key], sample.interest)
  assert.ok(module.PRODUCT_INTERESTS.includes(sample.interest))
  assert.equal(module.COMPANY_NAVIGATION.length, 5)
  const runtime=await readFile(new URL('../src/services/officialWechatRuntime.js',import.meta.url),'utf8')
  const functionSource=runtime.slice(runtime.indexOf('function updateDock('),runtime.indexOf('function syncRoute('))
  const contact={dataset:{},href:'',setAttribute(){}}
  const node={querySelector:()=>contact,querySelectorAll:()=>[]}
  const updateDock=new Function('buildDock','COMPANY_PRODUCTS','PRODUCT_BY_PATH','PRODUCT_PATHS','solutionContactRoute',functionSource+';return updateDock')
    (()=>node,module.COMPANY_PRODUCTS,new Map(),new Set([sample.path]),module.solutionContactRoute)
  updateDock({},sample.path)
  assert.equal(contact.href,'/contact?product='+sample.key)
})
