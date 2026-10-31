<template>
  <div v-if="product" class="yk-site yk-product-page yk-story-site" :style="{ '--yk-product-accent': product.accent, '--yk-product-soft': product.soft }">

    <main id="main">
      <section id="overview" class="yk-detail-hero"><div class="yk-shell yk-detail-hero-grid">
        <div class="yk-detail-hero-copy"><router-link class="yk-back-link" to="/products">← 返回产品中心</router-link><p class="yk-kicker">{{ product.eyebrow }}</p><div class="yk-detail-title-row"><span class="yk-detail-mark" :style="{ color: product.accent, background: product.soft }">{{ product.mark }}</span><h1>{{ product.name }}</h1></div><h2>{{ product.heroTitle }}</h2><p class="yk-detail-lead">{{ product.summary }}</p><p v-if="product.promise" class="yk-detail-promise">{{ product.promise }}</p>
          <div class="yk-role-row" aria-label="适用角色"><span v-for="role in product.roles" :key="role">{{ role }}</span></div>
          <div class="yk-hero-actions yk-detail-actions"><a class="yk-button yk-button-primary" href="#screens">查看产品界面 →</a><router-link class="yk-button yk-button-ghost" :to="contactRoute">预约产品演示</router-link><a class="yk-button yk-button-ghost" :href="contact.phoneHref">电话 {{ contact.phone }}</a></div>
        </div>
        <figure class="yk-detail-hero-shot"><OfficialImageZoom :src="heroScreen.src" :alt="`${product.name}产品界面`" loading="eager" :caption="heroScreen.title" /><figcaption><strong>{{ heroScreen.title }}</strong><span>{{ heroScreen.tag }}</span></figcaption></figure>
      </div></section>

      <nav class="product-reading-nav" aria-label="产品阅读导航"><div class="yk-shell reading-inner"><strong>{{ product.name }}</strong><div class="reading-links"><a v-for="section in readingSections" :key="section.id" :href="`#${section.id}`" :aria-current="$route.hash === `#${section.id}` ? 'location' : undefined">{{ section.label }}</a></div><select aria-label="跳转产品章节" :value="$route.hash || '#overview'" @change="jumpToSection"><option v-for="section in readingSections" :key="section.id" :value="`#${section.id}`">{{ section.label }}</option></select><router-link class="reading-contact" :to="contactRoute">预约演示 →</router-link></div></nav>

      <ProductReadingGuide :path="$route.path" />
      <section v-if="concerns.length" id="concerns" class="yk-section yk-product-concern-section"><div class="yk-shell">
        <div class="yk-section-heading yk-section-heading-left"><p class="yk-kicker">{{ marketing.concernKicker }}</p><h2>{{ marketing.concernTitle }}</h2><p>{{ marketing.concernLead }}</p></div>
        <ul class="yk-product-concern-grid"><li v-for="(item, index) in concerns" :key="item"><span>0{{ index + 1 }}</span><strong>{{ item }}</strong></li></ul>
        <div class="yk-product-answer"><span>系统给学校的答案</span><strong>{{ marketing.answer }}</strong></div>
      </div></section>

      <section id="capabilities" class="yk-section yk-detail-capability-section"><div class="yk-shell">
        <div class="yk-section-heading yk-section-heading-left"><p class="yk-kicker">{{ marketing.capabilityKicker || '客户先看懂解决什么问题' }}</p><h2>{{ marketing.capabilityTitle || `${product.name}不是菜单集合，而是一条连续业务链` }}</h2><p>{{ marketing.capabilityLead || '从学校角色、流程状态与下一步动作出发，理解产品如何进入日常工作。' }}</p></div>
        <div class="yk-detail-highlight-grid"><article v-for="item in product.highlights" :key="item.title"><span class="yk-highlight-index">0{{ product.highlights.indexOf(item) + 1 }}</span><h3>{{ item.title }}</h3><p>{{ item.desc }}</p></article></div>
        <div class="yk-workflow-band"><div class="yk-workflow-band-copy"><p class="yk-kicker">一条业务主线</p><h3>{{ marketing.workflowTitle || '从前置准备到最终结果，阶段之间持续传递同一业务事实' }}</h3></div><ol><li v-for="(step, index) in product.workflow" :key="step"><span>{{ index + 1 }}</span><strong>{{ step }}</strong></li></ol><p v-if="marketing.workflowSummary" class="yk-workflow-summary">{{ marketing.workflowSummary }}</p></div>
        <p v-if="story?.fact" class="yk-story-fact"><strong>业务范围：</strong>{{ story.fact }} <template v-if="product.relationMap">还可以查看完整业务地图。</template></p>
      </div></section>

      <section id="roles" class="yk-section yk-story-section"><div class="yk-shell">
        <div class="yk-section-heading"><p class="yk-kicker">谁在什么场景完成什么事情</p><h2>同一个产品，不同角色看到的是自己的工作</h2><p>{{ marketing.roleLead || '管理人员负责规则和治理，老师围绕待办与学生工作，学生处理本人事项。' }}</p></div>
        <div class="yk-role-journey-grid"><article v-for="item in roleJourneys" :key="item.role"><h3>{{ item.role }}</h3><p>{{ item.work }}</p></article></div>
      </div></section>

      <section v-if="visibility.length" class="yk-section yk-product-visibility-section"><div class="yk-shell yk-product-visibility-layout">
        <div class="yk-section-heading yk-section-heading-left"><p class="yk-kicker">{{ marketing.visibilityKicker }}</p><h2>{{ marketing.visibilityTitle }}</h2><p>{{ marketing.visibilityLead }}</p></div>
        <div class="yk-product-visibility-grid"><article v-for="(item, index) in visibility" :key="item.title"><span>0{{ index + 1 }}</span><div><h3>{{ item.title }}</h3><p>{{ item.desc }}</p></div></article></div>
      </div></section>

      <section id="screens" class="yk-section yk-detail-screens-section"><div class="yk-shell">
        <div class="yk-section-heading"><p class="yk-kicker">产品界面</p><h2>从界面看清角色、流程和办理动作</h2><p>点击截图可放大查看；界面中的学校、人员和业务数据均为演示数据。</p></div>
        <div class="yk-detail-screenshot-list"><article v-for="(screen, index) in product.screenshots" v-show="index < 4 || expandedScreens" :key="screen.src" class="yk-detail-screenshot-row" :class="{ 'yk-detail-screenshot-row-reverse': index % 2 === 1 }"><figure><OfficialImageZoom :src="screen.src" :alt="`${product.name} - ${screen.title}`" :caption="screen.title" /></figure><div><span class="yk-proof-tag">{{ screen.tag }}</span><h3>{{ screen.title }}</h3><p>{{ screen.desc }}</p></div></article></div>
      </div></section>

      <div v-if="product.screenshots.length > 4" class="yk-shell yk-more-screens"><button class="yk-button yk-button-ghost" :aria-expanded="expandedScreens" @click="expandedScreens = !expandedScreens">{{ expandedScreens ? '收起完整界面' : `查看其余 ${product.screenshots.length - 4} 个产品界面` }}</button></div>

      <section id="devices" class="yk-section yk-detail-device-section"><div class="yk-shell">
        <div class="yk-section-heading"><p class="yk-kicker">多端协同</p><h2>{{ product.slug === 'renshi' ? '分工清楚，协同办理' : '电脑端处理复杂工作，移动端承接高频任务' }}</h2><p>不同角色使用适合自己的工作入口，具体启用范围在项目方案中确认。</p></div>
        <div class="yk-device-grid"><article v-for="device in product.devices" :key="`${device.label}-${device.title}`" class="yk-device-card"><div v-if="device.image" class="yk-device-image"><img :src="device.image" :width="imageSizes[device.image]?.width" :height="imageSizes[device.image]?.height" :alt="`${product.name} ${device.title}`" loading="lazy" decoding="async" /></div><div class="yk-device-card-body"><span>{{ device.label }}</span><h3>{{ device.title }}</h3><p>{{ device.desc }}</p><a v-if="device.enterprise && enterpriseLoginUrl" :href="enterpriseLoginUrl">企业注册 / 登录 →</a></div></article></div>
      </div></section>

      <section id="evidence" class="yk-section yk-story-section"><div class="yk-shell">
        <div class="yk-section-heading yk-section-heading-left"><p class="yk-kicker">最终沉淀什么</p><h2>{{ marketing.evidenceTitle || '学校买的不是“页面数量”，而是过程、结果和证据都能留下来' }}</h2><p>{{ marketing.evidenceLead || '不同产品沉淀的对象不同，但共同目标是让状态、材料、责任、异常、结果和归档有迹可循。' }}</p></div>
        <ul class="yk-outcome-grid"><li v-for="item in outcomes" :key="item">{{ item }}</li></ul>
        <div class="yk-evidence-note"><strong>数据说明</strong><p>产品截图使用演示数据，不包含真实学生、教师或学校敏感信息。</p></div>
      </div></section>

      <section v-if="faqs.length" id="faq" class="yk-section yk-story-section yk-pain-section"><div class="yk-shell"><div class="yk-section-heading"><p class="yk-kicker">产品常见问题</p><h2>客户第一次了解 {{ product.name }} 时，先回答最关键的疑问</h2></div><div class="yk-product-faq"><details v-for="item in faqs" :key="item.q"><summary>{{ item.q }}</summary><p>{{ item.a }}</p></details></div></div></section>

      <section id="access" class="yk-section yk-access-section yk-access-secondary"><div class="yk-shell"><div class="yk-section-heading yk-access-heading"><p class="yk-kicker">已经是系统用户？</p><h2>按身份进入学校授权的业务系统</h2></div><div class="yk-access-grid yk-access-grid-three"><a v-if="product.slug === 'renshi' && hrLoginUrl" :href="hrLoginUrl" class="yk-access-card yk-access-primary"><span>人事与教职工服务</span><strong>进入高校人事系统</strong><small>使用学校授权的账号办理本人职责范围内事项</small><b aria-hidden="true">→</b></a><a v-if="teacherLoginUrl && product.slug !== 'renshi'" :href="teacherLoginUrl" class="yk-access-card yk-access-primary"><span>教师 / 管理人员</span><strong>进入教师与管理工作台</strong><small>{{ product.name }}管理、审核、指导与业务办理</small><b aria-hidden="true">→</b></a><a v-if="studentLoginUrl && product.slug !== 'renshi'" :href="studentLoginUrl" class="yk-access-card"><span>学生</span><strong>进入学生门户</strong><small>查看本人事项、提交材料、查询进度与结果</small><b aria-hidden="true">→</b></a><a v-if="enterpriseLoginUrl && product.slug === 'internship'" :href="enterpriseLoginUrl" class="yk-access-card"><span>企业协同</span><strong>企业注册 / 登录</strong><small>首次注册由学校邀请激活，不开放自由注册</small><b aria-hidden="true">→</b></a></div><div class="yk-detail-secondary-actions"><router-link to="/">返回官网首页</router-link><router-link to="/products">返回产品中心</router-link><router-link :to="contactRoute">预约产品演示</router-link><a v-if="product.relationMap" :href="product.relationMap" rel="noopener noreferrer">查看{{ product.name }}完整业务地图</a></div></div></section>

      <section class="yk-final-cta"><div class="yk-shell yk-final-inner"><p class="yk-final-kicker">{{ product.name }}</p><h2>{{ marketing.finalTitle || '想把这套能力落到学校真实业务里？' }}</h2><p>{{ marketing.finalLead || '选择关注的产品，填写单位与联系电话，沟通本次演示需求。资料处理方式在预约页提交前说明。' }}</p><div class="yk-final-actions"><router-link class="yk-button yk-button-light" :to="contactRoute">预约产品演示</router-link><a class="yk-button yk-button-ghost" :href="contact.phoneHref">拨打 {{ contact.phone }}</a></div></div></section>
    </main>

  </div>
</template>

<script>
import imageSizes from '../../config/officialImageSizes.json'
import { getOfficialProduct } from '../../config/officialProducts'
import OfficialImageZoom from '../../components/official-site/OfficialImageZoom.vue'
import ProductReadingGuide from '../../components/official-site/ProductReadingGuide.vue'
import { OFFICIAL_SITE_CONTACT } from '../../config/officialSalesPages'
import { syncOfficialSeo } from '../../services/officialSeoRuntime'
import { PRODUCT_STORIES } from '../../config/officialWebsiteStory'
import { COMPANY_NAME, ENTERPRISE_LOGIN_URL, ICP_NUMBER, ICP_QUERY_URL, HR_LOGIN_URL, STUDENT_LOGIN_URL, TEACHER_LOGIN_URL } from '../../config/portalConfig'
import '../../styles/official-site.css'
import '../../styles/official-site-story.css'

export default {
  name: 'OfficialProductView',
  components: { OfficialImageZoom, ProductReadingGuide },
  data() { return { imageSizes, expandedScreens: false, hrLoginUrl: HR_LOGIN_URL, companyName: COMPANY_NAME, icpNumber: ICP_NUMBER, icpQueryUrl: ICP_QUERY_URL, teacherLoginUrl: TEACHER_LOGIN_URL, studentLoginUrl: STUDENT_LOGIN_URL, enterpriseLoginUrl: ENTERPRISE_LOGIN_URL } },
  computed: {
    product() { return getOfficialProduct(this.$route.path.split('/').at(-1)) }, contact() { return OFFICIAL_SITE_CONTACT },
    heroScreen() { return (this.product?.slug === 'academic-affairs' && this.product.screenshots.find(screen => screen.src === '/official-site/academic-course-catalog.png')) || this.product?.screenshots[0] },
    readingSections() { return [{ id: 'overview', label: '产品概览' }, { id: 'questions', label: '选型导览' }, { id: 'capabilities', label: '核心能力' }, { id: 'roles', label: '角色分工' }, { id: 'screens', label: '产品界面' }, { id: 'devices', label: '多端协同' }, { id: 'evidence', label: '成果材料' }, ...(this.faqs.length ? [{ id: 'faq', label: '常见问题' }] : [])] },
    story() { return PRODUCT_STORIES[this.product?.slug] || null }, roleJourneys() { return this.story?.roles || this.product?.roleJourneys || [] }, outcomes() { return this.story?.outcomes || this.product?.outcomes || [] }, faqs() { return this.story?.faqs || this.product?.faqs || [] },
    concerns() { return this.product?.concerns || [] }, visibility() { return this.product?.visibility || [] }, marketing() { return this.product?.marketing || {} },
    contactRoute() { return { path: '/contact', query: { product: this.product?.slug || '' } } }, year() { return new Date().getFullYear() }
  },
  watch: { '$route.path': { immediate: true, handler() { this.expandedScreens = false; this.syncDocumentMeta() } } },
  methods: {
    jumpToSection(event) { this.$router.push({ path: this.$route.path, hash: event.target.value }) },
    syncDocumentMeta() { if (typeof document === 'undefined') return; this.$nextTick(() => syncOfficialSeo(this.$route.path)) }
  }
}
</script>

<style scoped>
.yk-product-page{overflow-x:clip;overflow-y:visible}.yk-more-screens{text-align:center;padding:0 0 48px}.yk-detail-lead{max-width:38em}.yk-detail-screenshot-list article[style*="display: none"]{display:none!important}
.yk-detail-screenshot-row :deep(img){aspect-ratio:auto!important;object-fit:contain!important;height:auto!important}.yk-detail-screenshot-row .yk-proof-tag{color:#344e69!important;background:#edf3fb!important}
.yk-product-page section[id]{scroll-margin-top:calc(var(--website-header-height,80px) + 84px)}.product-reading-nav{position:sticky;top:var(--website-header-height,80px);z-index:30;background:#fff;border-bottom:1px solid #dce6ef;box-shadow:0 3px 10px #172f4908}.reading-inner{display:flex;align-items:center;gap:24px;min-height:68px}.reading-inner>strong{font-size:15px;white-space:nowrap;max-width:14em;overflow:hidden;text-overflow:ellipsis}.reading-links{display:flex;align-items:center;gap:20px;margin-left:auto}.reading-links a{font-size:14px;white-space:nowrap;padding:20px 0;color:#526c83}.reading-links a[aria-current],.reading-links a:hover{color:#2268df}.reading-contact{font-size:14px;color:#2268df;font-weight:600;white-space:nowrap}.reading-inner select{display:none}.yk-detail-hero-shot :deep(img){object-fit:contain!important;height:auto!important;aspect-ratio:auto!important}.yk-detail-hero-copy h2{font-size:clamp(30px,3.1vw,44px);line-height:1.4}
@media(max-width:1200px){.reading-links{gap:14px}.reading-inner{gap:16px}.reading-inner>strong{max-width:10em;font-size:14px}}
@media(max-width:1000px){.reading-links{display:none}.reading-inner select{display:block;min-width:0;max-width:160px;margin-left:auto;border:1px solid #cbd8e5;border-radius:6px;padding:10px 28px 10px 10px;min-height:44px;background:#fff;color:#172f49;font:inherit;font-size:14px}.reading-inner{gap:12px}.reading-inner>strong{flex:1;max-width:none}.reading-contact{font-size:13px}}
@media(max-width:600px){.reading-inner{min-height:68px}.reading-inner>strong{display:none}.reading-inner select{margin-left:0;flex:1;max-width:none}.reading-contact{padding:10px 0}.yk-detail-hero-copy h2{font-size:29px}}
</style>
