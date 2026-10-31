import catalog from '../../../products.json' with { type: 'json' }
import localProducts from '../config/officialLocalProducts.json' with { type: 'json' }
import { OFFICIAL_PRODUCTS } from '../config/officialProducts.js'
import { PRODUCT_STORIES, SALES_STORIES } from '../config/officialWebsiteStory.js'
import { OFFICIAL_SALES_PAGE_MAP, OFFICIAL_SEO_ROUTES, OFFICIAL_SITE_CONTACT } from '../config/officialSalesPages.js'

const origin=OFFICIAL_SITE_CONTACT.canonicalOrigin
export const SEARCH_CONTENT_UPDATED_AT='2026-10-11'
export function publicProduct(path){
  if(!OFFICIAL_SALES_PAGE_MAP[path])return null
  const slug=path.split('/').at(-1)
  const material=localProducts.find(item=>item.key===slug)
  const original=OFFICIAL_PRODUCTS[slug]
  const entry=catalog.products.find(item=>item.public && (item.path===path || item.children?.includes(slug)))
  if(!entry)return null
  const page=OFFICIAL_SALES_PAGE_MAP[path]
  const source=material || original
  return {key:material?.key || original?.slug || entry.key,name:source?.name || entry.name,
    summary:source?.summary || page.description,domain:entry.domain,roles:original?.roles || [],
    screenshots:source?.screenshots || page.screenshots.map(src=>({src,title:entry.name})),workflow:original?.workflow || []}
}
export function readingQuestions(path){
  const product=publicProduct(path)
  if(!product)return []
  const domain=catalog.domains.find(item=>item.key===product.domain)?.name || ''
  return [
    {q:product.roles.length ? `${product.name}面向哪些角色？` : `${product.name}属于哪个业务领域？`,a:product.roles.length ? product.roles.join('、') : domain,href:product.roles.length?'#roles':'#introduction',link:'继续看原介绍'},
    {q:product.workflow.length ? '怎样沿业务流程了解产品？' : '这套产品主要介绍什么？',a:product.workflow.length ? product.workflow.join(' → ') : product.summary,href:product.workflow.length ? '#capabilities' : '#introduction',link:'查看业务范围'},
    {q:'可以先查看哪些界面？',a:product.screenshots.slice(0,3).map(item=>item.title).join('、')+'。界面中的数据为演示或样例数据。',href:'#screens',link:'放大查看界面'}
  ]
}
export function visibleFaqs(path){
  if(['/', '/contact', '/products', '/solutions', '/about', '/services/delivery','/platform'].includes(path))return []
  const page=OFFICIAL_SALES_PAGE_MAP[path]
  const questions=readingQuestions(path)
  const original=page?.type==='product' ? PRODUCT_STORIES[path.split('/').at(-1)]?.faqs || OFFICIAL_PRODUCTS[path.split('/').at(-1)]?.faqs || [] : SALES_STORIES[path]?.faqs || []
  return [...questions,...original]
}
export function searchModifiedAt(path){
  return readingQuestions(path).length || ['/contact','/privacy'].includes(path) ? SEARCH_CONTENT_UPDATED_AT : OFFICIAL_SEO_ROUTES.find(item=>item.path===path)?.contentUpdatedAt
}
export function organizationData(){
  return {'@type':'Organization','@id':origin+'/#organization',name:OFFICIAL_SITE_CONTACT.company,alternateName:OFFICIAL_SITE_CONTACT.brand,
    url:origin+'/',telephone:OFFICIAL_SITE_CONTACT.phone.replaceAll(' ',''),contactPoint:{'@type':'ContactPoint',contactType:'sales and support',telephone:OFFICIAL_SITE_CONTACT.phone.replaceAll(' ',''),availableLanguage:['zh-CN']}}
}
export function shareImage(path){
  if(path==='/products/academic-affairs')return '/official-site/academic-course-catalog.png'
  return publicProduct(path)?.screenshots?.[0]?.src || OFFICIAL_SALES_PAGE_MAP[path]?.screenshots?.[0] || '/official-site/showcase-20260909/scenes/overview.webp'
}
export function searchGraph(path){
  const route=OFFICIAL_SEO_ROUTES.find(item=>item.path===path)
  if(!route)return null
  const page=OFFICIAL_SALES_PAGE_MAP[path],canonical=origin+(path==='/'?'/':path)
  const image=origin+shareImage(path)
  const product=publicProduct(path)
  const entity={'@type':path==='/about'?'AboutPage':path==='/contact'?'ContactPage':path==='/products' || path==='/solutions'?'CollectionPage':'WebPage',
    '@id':canonical+'#webpage',url:canonical,name:route.title,description:route.description,inLanguage:'zh-CN',dateModified:searchModifiedAt(path),
    isPartOf:{'@id':origin+'/#website'},publisher:{'@id':origin+'/#organization'},primaryImageOfPage:{'@type':'ImageObject',url:image}}
  const graph=[organizationData(),{'@type':'WebSite','@id':origin+'/#website',url:origin+'/',name:OFFICIAL_SITE_CONTACT.brand,inLanguage:'zh-CN',publisher:{'@id':origin+'/#organization'}},entity]
  if(path!=='/'){
    const crumbs=[{name:'官网首页',url:origin+'/'}]
    if(path.startsWith('/products/'))crumbs.push({name:'产品中心',url:origin+'/products'})
    crumbs.push({name:page?.navTitle || route.title.split('｜')[0],url:canonical})
    entity.breadcrumb={'@id':canonical+'#breadcrumb'}
    graph.push({'@type':'BreadcrumbList','@id':canonical+'#breadcrumb',itemListElement:crumbs.map((item,index)=>({'@type':'ListItem',position:index+1,name:item.name,item:item.url}))})
  }
  if(product){
    entity.mainEntity={'@id':canonical+'#software'}
    graph.push({'@type':'SoftwareApplication','@id':canonical+'#software',name:product.name,description:product.summary,url:canonical,
      applicationCategory:['teaching','training'].includes(product.domain)?'EducationalApplication':'BusinessApplication',inLanguage:'zh-CN',image:product.screenshots.map(item=>origin+item.src),publisher:{'@id':origin+'/#organization'}})
  }
  if(path==='/products')graph.push({'@type':'ItemList',name:'跃科产品目录',itemListElement:catalog.products.filter(item=>item.public).map((item,index)=>({'@type':'ListItem',position:index+1,name:item.name,url:origin+item.path}))})
  const faqs=visibleFaqs(path)
  if(faqs.length)graph.push({'@type':'FAQPage','@id':canonical+'#questions',mainEntity:faqs.map(item=>({'@type':'Question',name:item.q,acceptedAnswer:{'@type':'Answer',text:item.a}}))})
  return {'@context':'https://schema.org','@graph':graph}
}
