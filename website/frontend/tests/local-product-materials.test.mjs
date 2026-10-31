import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import products from '../src/config/officialLocalProducts.json' with { type: 'json' }
import { OFFICIAL_SALES_PAGE_MAP, OFFICIAL_SEO_ROUTES } from '../src/config/officialSalesPages.js'
import { COMPANY_PRODUCTS, PRODUCT_INTEREST_BY_SLUG } from '../src/config/companyProducts.js'

test('six original product materials reach detail metadata, directory, consultation and crawl routes', async () => {
  assert.equal(products.length,6)
  const ledger=JSON.parse(await readFile(new URL('../../materials/20261011/source-ledger.json',import.meta.url),'utf8'))
  for(const product of products){
    const path='/products/'+product.key
    assert.equal(OFFICIAL_SALES_PAGE_MAP[path].description,product.summary)
    assert.equal(COMPANY_PRODUCTS.find(item=>item.key===product.key).path,path)
    assert.equal(PRODUCT_INTEREST_BY_SLUG[product.key],product.name)
    assert.ok(OFFICIAL_SEO_ROUTES.some(item=>item.path===path))
    const source=ledger.products.find(item=>item.key===product.key)
    for(const text of [product.summary,...product.sections.flatMap(item=>item.paragraphs),...(product.technical || []).map(item=>item.text)]){
      assert.ok(source.quotes.some(quote=>text===quote.text || text.endsWith('：'+quote.text)),product.key+' 原文未能对应来源')
    }
    for(const picture of product.screenshots){
      const copied=source.images.find(image=>'/' + image.target.replace('frontend/public/','')===picture.src)
      assert.ok(copied,picture.src)
      const bytes=await readFile(new URL('../public'+picture.src,import.meta.url))
      assert.equal(createHash('sha256').update(bytes).digest('hex'),copied.sha256)
    }
  }
})
