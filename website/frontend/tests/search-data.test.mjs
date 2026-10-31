import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { OFFICIAL_SEO_ROUTES } from '../src/config/officialSalesPages.js'
import { searchGraph, visibleFaqs, readingQuestions, publicProduct, shareImage, searchModifiedAt } from '../src/services/officialSearchData.js'

const escape=text=>String(text).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;').replaceAll("'",'&#39;')
test('initial public HTML has the same entities and visible answers as the browser source',async()=>{
  for(const route of OFFICIAL_SEO_ROUTES){
    const path=route.path==='/'?'index.html':route.path.slice(1)+'/index.html'
    const html=await readFile(new URL('../dist/'+path,import.meta.url),'utf8')
    const script=html.match(/<script type="application\/ld\+json" data-official-seo="graph">([\s\S]*?)<\/script>/)
    assert.ok(script,route.path)
    assert.deepEqual(JSON.parse(script[1]),searchGraph(route.path))
    const body=html.slice(html.indexOf('<body'))
    for(const question of visibleFaqs(route.path)){
      assert.ok(body.includes(escape(question.q)),route.path+' question is absent from the visible body: '+question.q)
      assert.ok(body.includes(escape(question.a)),route.path+' answer is absent from the visible body: '+question.a)
    }
    for(const question of readingQuestions(route.path))assert.ok(body.includes('id="'+question.href.slice(1)+'"'),route.path+' guide target does not exist')
    assert.ok(!JSON.stringify(searchGraph(route.path)).match(/"(?:offers|aggregateRating|awards)":/),'no invented prices, reviews or awards')
  }
})
test('software names, business domains, share images and source dates remain exact',()=>{
  const governance=searchGraph('/products/data-governance')['@graph']
  assert.equal(governance.find(node=>node['@type']==='SoftwareApplication').name,'澜青数治')
  assert.equal(governance.find(node=>node['@type']==='SoftwareApplication').applicationCategory,'BusinessApplication')
  assert.equal(searchGraph('/products/training-saas')['@graph'].find(node=>node['@type']==='SoftwareApplication').applicationCategory,'EducationalApplication')
  assert.equal(shareImage('/products/academic-affairs'),'/official-site/academic-course-catalog.png')
  assert.equal(searchGraph('/products')['@graph'].find(node=>node['@type']==='ItemList').itemListElement.length,9)
  for(const path of ['/manage','/api/auth/session','/missing','/manage/academic-affairs']){
    assert.equal(searchGraph(path),null);assert.equal(publicProduct(path),null)
  }
  assert.equal(searchModifiedAt('/products/data-governance'),'2026-10-11')
})
