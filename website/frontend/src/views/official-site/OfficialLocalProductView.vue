<template>
  <div v-if="product" class="yk-site local-product">
    <main id="main">
      <section id="overview" class="local-hero">
        <div class="local-shell hero-grid">
          <div>
            <RouterLink class="back-link" to="/products">← 返回产品中心</RouterLink>
            <p class="eyebrow">{{ domainName }}</p>
            <h1>{{ product.name }}</h1>
            <p class="lead">{{ product.summary }}</p>
            <div class="hero-actions"><a class="yk-button yk-button-primary" href="#screens">查看产品界面 →</a><RouterLink class="yk-button yk-button-ghost" :to="contactRoute">预约产品演示</RouterLink></div>
          </div>
          <figure class="hero-screen"><OfficialImageZoom :src="product.screenshots[0].src" :alt="product.name + ' · ' + product.screenshots[0].title" :caption="product.screenshots[0].title" loading="eager" /><figcaption><strong>{{ product.screenshots[0].title }}</strong><span>{{ product.screenshots[0].kind }}</span></figcaption></figure>
        </div>
      </section>
      <nav class="local-reading" aria-label="产品阅读导航"><div class="local-shell reading-inner"><strong>{{ product.name }}</strong><div class="reading-links"><a v-for="chapter in chapters" :key="chapter.id" :href="'#'+chapter.id" :aria-current="route.hash === '#'+chapter.id ? 'location' : undefined">{{ chapter.label }}</a></div><select aria-label="跳转产品章节" :value="route.hash || '#overview'" @change="jump"><option v-for="chapter in chapters" :key="chapter.id" :value="'#'+chapter.id">{{ chapter.label }}</option></select></div></nav>
      <ProductReadingGuide :path="route.path" />
      <section id="introduction" class="introduction-section local-shell">
        <header class="section-heading"><p class="eyebrow">产品介绍</p><h2>了解产品的业务范围</h2></header>
        <div class="introduction-grid"><article v-for="section in product.sections" :key="section.title"><h3>{{ section.title }}</h3><p v-for="paragraph in section.paragraphs" :key="paragraph" class="original-copy">{{ paragraph }}</p><p v-if="section.glossary" class="glossary">{{ section.glossary }}</p></article></div>
        <details v-if="product.technical?.length" class="technical-copy"><summary>实施人员使用：资产、共享与安全能力原文</summary><article v-for="item in product.technical" :key="item.title"><h3>{{ item.title }}</h3><p class="original-copy">{{ item.text }}</p></article><p class="glossary">API（接口）；RBAC（基于角色的权限控制）；AppKey/Secret（应用调用凭据）；Markdown（文本排版格式）。</p></details>
      </section>
      <section id="screens" class="screens-section"><div class="local-shell"><header class="section-heading"><p class="eyebrow">产品界面</p><h2>从画面了解具体工作</h2><p>点击图片放大查看。界面中的数据为演示或样例数据。</p></header><div class="screen-grid"><figure v-for="screen in product.screenshots" :key="screen.src"><OfficialImageZoom :src="screen.src" :alt="product.name + ' · ' + screen.title" :caption="screen.title" /><figcaption><strong>{{ screen.title }}</strong><span>{{ screen.kind }}</span></figcaption></figure></div></div></section>
      <section id="consult" class="consult-section"><div class="local-shell consult-inner"><div><p class="eyebrow">产品咨询</p><h2>围绕实际工作，沟通建设方案</h2><p>按业务流程、数据准备和部署条件，确认适合的产品与实施范围。</p></div><div class="hero-actions"><RouterLink class="yk-button yk-button-primary" :to="contactRoute">预约产品演示 →</RouterLink><a class="yk-button yk-button-ghost" :href="contact.phoneHref">电话 {{ contact.phone }}</a></div></div></section>
    </main>
  </div>
</template>
<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import localProducts from '../../config/officialLocalProducts.json'
import { PRODUCT_DOMAINS } from '../../config/companyProducts.js'
import { OFFICIAL_SITE_CONTACT as contact } from '../../config/officialSalesPages.js'
import OfficialImageZoom from '../../components/official-site/OfficialImageZoom.vue'
import ProductReadingGuide from '../../components/official-site/ProductReadingGuide.vue'
import '../../styles/official-site.css'
const route=useRoute(), router=useRouter()
const product=computed(()=>localProducts.find(item=>item.key===route.path.split('/').at(-1)))
const domainName=computed(()=>PRODUCT_DOMAINS.find(item=>item.key===product.value?.domain)?.name || '')
const contactRoute=computed(()=>({path:'/contact',query:{product:product.value?.key}}))
const chapters=[{id:'overview',label:'产品概览'},{id:'questions',label:'选型导览'},{id:'introduction',label:'产品介绍'},{id:'screens',label:'产品界面'},{id:'consult',label:'沟通方案'}]
function jump(event){router.push({path:route.path,hash:event.target.value})}
</script>
<style scoped>
.yk-site.local-product{overflow:visible;color:#172f49}.local-shell{width:min(1280px,calc(100% - 80px));margin:auto}.local-hero{padding:66px 0;background:linear-gradient(120deg,#f3f7ff,#eaf2fc)}.hero-grid{display:grid;grid-template-columns:1fr 1.12fr;gap:56px;align-items:center}.back-link{font-size:14px;color:#52718e;text-decoration:none}.eyebrow{font-size:13px;font-weight:650;color:#2268df;margin:26px 0 16px}.local-hero h1{font-size:clamp(30px,3.2vw,46px);line-height:1.3;margin:0 0 24px;letter-spacing:-.5px}.lead{font-size:18px;line-height:1.9;white-space:pre-line;overflow-wrap:anywhere}.hero-actions{display:flex;flex-wrap:wrap;gap:12px;margin-top:28px}.local-product figure{margin:0;min-width:0}.hero-screen,.screen-grid figure{background:white;border:1px solid #dbe5f0;border-radius:14px;padding:14px;box-shadow:0 16px 34px #193b6410}.local-product figcaption{display:flex;flex-wrap:wrap;justify-content:space-between;gap:8px 20px;line-height:1.8;font-size:13px;padding:12px 4px 0}.local-product figcaption span{color:#62768e}.hero-screen :deep(.yk-image-zoom img){max-height:390px;object-fit:contain}.local-reading{position:sticky;top:86px;z-index:20;background:#ffffffed;border-bottom:1px solid #dce5ef;backdrop-filter:blur(12px)}.reading-inner{display:flex;align-items:center;justify-content:space-between;gap:20px;min-height:62px}.reading-inner>strong{font-size:14px;max-width:40%;line-height:1.6}.reading-links{display:flex;gap:28px}.reading-links a{padding:18px 0;color:#62768e;font-size:14px;text-decoration:none;white-space:nowrap}.reading-links a:hover,.reading-links a[aria-current]{color:#2268df}.local-reading select{display:none;min-height:44px;border:1px solid #cfdae8;border-radius:7px;padding:8px;color:#21496d;background:white;max-width:52%}.introduction-section{padding:64px 0}.section-heading{margin-bottom:32px}.section-heading .eyebrow{margin-top:0}.section-heading h2,.consult-inner h2{margin:0 0 16px;font-size:30px;line-height:1.5}.section-heading>p:last-child,.consult-inner>div>p:last-child{color:#62768e;line-height:1.8}.introduction-grid{display:grid;grid-template-columns:1fr 1fr;gap:28px}.introduction-grid article{border-top:3px solid #3375db;padding:22px 0}.introduction-grid h3{font-size:22px;line-height:1.6;margin:0 0 18px}.original-copy{font-size:16px;line-height:2;white-space:pre-line;overflow-wrap:anywhere;margin:0 0 16px;color:#425d76}.glossary{font-size:13px;color:#62768e;line-height:1.8}.screens-section{background:#f5f8fc;padding:64px 0}.screen-grid{display:grid;grid-template-columns:1fr 1fr;gap:28px;align-items:start}.screen-grid figure:only-child{grid-column:1/-1;max-width:1100px;width:100%;margin:auto}.screen-grid :deep(.yk-image-zoom img){max-height:580px;object-fit:contain}.consult-section{padding:56px 0;background:#fff}.consult-inner{display:flex;align-items:center;justify-content:space-between;gap:32px}.consult-inner .eyebrow{margin-top:0}#overview,#introduction,#screens,#consult{scroll-margin-top:164px}.local-product :deep(:focus-visible){outline:3px solid #85b1f5;outline-offset:3px}
@media(max-width:980px){.hero-grid{gap:30px}.hero-grid{grid-template-columns:1fr 1fr}.local-hero h1{font-size:34px}.reading-links{gap:16px}.introduction-grid{gap:24px}.local-shell{width:calc(100% - 48px)}}
@media(max-width:720px){.local-shell{width:calc(100% - 32px)}.local-hero{padding:36px 0}.hero-grid,.introduction-grid,.screen-grid{grid-template-columns:1fr;gap:26px}.local-hero h1{font-size:30px;margin-bottom:20px}.lead{font-size:16px}.local-hero .eyebrow{margin-top:24px}.local-reading{top:66px}.reading-inner{min-height:64px;gap:12px}.reading-inner>strong{max-width:48%;font-size:12px}.reading-links{display:none}.local-reading select{display:block}.introduction-section,.screens-section{padding:42px 0}.section-heading h2,.consult-inner h2{font-size:25px}.introduction-grid article{padding-top:18px}.introduction-grid h3{font-size:21px}.original-copy{font-size:15px}.hero-screen,.screen-grid figure{padding:10px}.consult-section{padding:42px 0}.consult-inner{display:block}.hero-actions{gap:10px}.hero-actions .yk-button{font-size:14px;flex:1;white-space:nowrap;padding:12px}.hero-screen :deep(.yk-image-zoom img),.screen-grid :deep(.yk-image-zoom img){max-height:none}#overview,#introduction,#screens,#consult{scroll-margin-top:144px}}
</style>
<style scoped>.technical-copy{border:1px solid #dbe5f0;border-radius:8px;padding:18px 22px;margin-top:22px}.technical-copy summary{cursor:pointer;color:#52718e;line-height:1.8}.technical-copy article{margin:22px 0}.technical-copy h3{font-size:18px}.technical-copy .original-copy{font-size:14px}</style>
