<template>
  <div v-if="product" class="yk-site yk-product-page yk-story-site">
    <header class="yk-header"><div class="yk-shell yk-nav">
      <router-link class="yk-brand" to="/" aria-label="返回跃科官网首页"><span class="yk-brand-dot" aria-hidden="true">跃</span><span class="yk-brand-copy"><strong>跃科 · {{ product.name }}</strong><small>职业院校学生全生命周期数字化平台</small></span></router-link>
      <nav class="yk-nav-links" aria-label="产品页导航"><a href="#capabilities">解决什么</a><a href="#roles">谁怎么用</a><a href="#screens">真实界面</a><a href="#evidence">沉淀什么</a><router-link to="/contact">预约演示</router-link></nav>
      <router-link class="yk-nav-cta" :to="contactRoute">预约产品演示</router-link>
    </div></header>

    <main>
      <section class="yk-detail-hero"><div class="yk-shell yk-detail-hero-grid">
        <div class="yk-detail-hero-copy"><router-link class="yk-back-link" to="/products">← 返回产品中心</router-link><p class="yk-kicker">{{ product.eyebrow }}</p><div class="yk-detail-title-row"><span class="yk-detail-mark" :style="{ color: product.accent, background: product.soft }">{{ product.mark }}</span><h1>{{ product.name }}</h1></div><h2>{{ product.heroTitle }}</h2><p class="yk-detail-lead">{{ product.summary }}</p>
          <div class="yk-role-row" aria-label="适用角色"><span v-for="role in product.roles" :key="role">{{ role }}</span></div>
          <div class="yk-hero-actions yk-detail-actions"><a class="yk-button yk-button-primary" href="#screens">看真实系统界面 →</a><router-link class="yk-button yk-button-ghost" :to="contactRoute">预约产品演示</router-link><a class="yk-button yk-button-ghost" :href="contact.phoneHref">电话 {{ contact.phone }}</a></div>
        </div>
        <figure class="yk-detail-hero-shot"><img :src="product.screenshots[0].src" :alt="`${product.name}真实产品界面`" decoding="async" /><figcaption><strong>{{ product.screenshots[0].title }}</strong><span>{{ product.screenshots[0].tag }}</span></figcaption></figure>
      </div></section>

      <section id="capabilities" class="yk-section yk-detail-capability-section"><div class="yk-shell">
        <div class="yk-section-heading yk-section-heading-left"><p class="yk-kicker">客户先看懂解决什么问题</p><h2>{{ product.name }}不是菜单集合，而是一条连续业务链</h2><p>官网只描述仓库真实存在的业务能力，不虚构客户数量、学校名称、业务规模或运营效果。</p></div>
        <div class="yk-detail-highlight-grid"><article v-for="item in product.highlights" :key="item.title"><span class="yk-highlight-index">0{{ product.highlights.indexOf(item) + 1 }}</span><h3>{{ item.title }}</h3><p>{{ item.desc }}</p></article></div>
        <div class="yk-workflow-band"><div class="yk-workflow-band-copy"><p class="yk-kicker">业务闭环</p><h3>从前置准备到最终结果，阶段之间持续传递同一业务事实</h3></div><ol><li v-for="(step, index) in product.workflow" :key="step"><span>{{ index + 1 }}</span><strong>{{ step }}</strong></li></ol></div>
        <p v-if="story?.fact" class="yk-story-fact"><strong>业务地图事实：</strong>{{ story.fact }} <template v-if="product.relationMap">客户还可以查看完整帮助中心业务地图。</template></p>
      </div></section>

      <section id="roles" class="yk-section yk-story-section"><div class="yk-shell">
        <div class="yk-section-heading"><p class="yk-kicker">谁在什么场景完成什么事情</p><h2>同一个产品，不同角色看到的是自己的工作</h2><p>管理人员负责规则和治理，老师围绕待办与学生工作，学生处理本人事项；企业只在被授权的实习协同范围内参与。</p></div>
        <div class="yk-role-journey-grid"><article v-for="item in roleJourneys" :key="item.role"><h3>{{ item.role }}</h3><p>{{ item.work }}</p></article></div>
      </div></section>

      <section id="screens" class="yk-section yk-detail-screens-section"><div class="yk-shell">
        <div class="yk-section-heading"><p class="yk-kicker">真实产品界面</p><h2>每一张图都告诉客户“这是干什么的”，不让官网只剩截图墙</h2><p>截图来自真实代码运行环境或已经跑绿的浏览器证据。允许网页展示裁切，不重绘、不篡改业务结论。</p></div>
        <div class="yk-detail-screenshot-list"><article v-for="(screen, index) in product.screenshots" :key="screen.src" class="yk-detail-screenshot-row" :class="{ 'yk-detail-screenshot-row-reverse': index % 2 === 1 }"><figure><img :src="screen.src" :alt="`${product.name} - ${screen.title}`" loading="lazy" decoding="async" /></figure><div><span class="yk-proof-tag">{{ screen.tag }}</span><h3>{{ screen.title }}</h3><p>{{ screen.desc }}</p></div></article></div>
      </div></section>

      <section id="devices" class="yk-section yk-detail-device-section"><div class="yk-shell">
        <div class="yk-section-heading"><p class="yk-kicker">多端协同</p><h2>PC 负责复杂工作，移动端负责高频任务</h2><p>同一模块按角色分配不同工作界面，不把管理后台简单缩成手机宽度。</p></div>
        <div class="yk-device-grid"><article v-for="device in product.devices" :key="`${device.label}-${device.title}`" class="yk-device-card"><div v-if="device.image" class="yk-device-image"><img :src="device.image" :alt="`${product.name} ${device.title}`" loading="lazy" decoding="async" /></div><div class="yk-device-card-body"><span>{{ device.label }}</span><h3>{{ device.title }}</h3><p>{{ device.desc }}</p><a v-if="device.enterprise && enterpriseLoginUrl" :href="enterpriseLoginUrl">企业注册 / 登录 →</a></div></article></div>
      </div></section>

      <section id="evidence" class="yk-section yk-story-section"><div class="yk-shell">
        <div class="yk-section-heading yk-section-heading-left"><p class="yk-kicker">最终沉淀什么</p><h2>学校买的不是“页面数量”，而是过程、结果和证据都能留下来</h2><p>不同产品沉淀的对象不同，但共同目标是让状态、材料、责任、异常、结果和归档有迹可循。</p></div>
        <ul class="yk-outcome-grid"><li v-for="item in outcomes" :key="item">{{ item }}</li></ul>
        <div class="yk-evidence-note"><strong>素材真实性说明</strong><p>当前公开图片使用隔离 E2E / Playwright 测试数据。它们用于证明产品真实存在和页面结构，不代表任何真实学校运营数据，也不作为客户案例。</p></div>
      </div></section>

      <section v-if="faqs.length" class="yk-section yk-story-section yk-pain-section"><div class="yk-shell"><div class="yk-section-heading"><p class="yk-kicker">产品常见问题</p><h2>客户第一次了解 {{ product.name }} 时，先回答最关键的疑问</h2></div><div class="yk-product-faq"><details v-for="item in faqs" :key="item.q"><summary>{{ item.q }}</summary><p>{{ item.a }}</p></details></div></div></section>

      <section id="access" class="yk-section yk-access-section yk-access-secondary"><div class="yk-shell"><div class="yk-section-heading yk-access-heading"><p class="yk-kicker">已经是系统用户？</p><h2>看懂产品之后，再按身份进入正式业务系统</h2></div><div class="yk-access-grid yk-access-grid-three"><a v-if="teacherLoginUrl" :href="teacherLoginUrl" class="yk-access-card yk-access-primary"><span>教师 / 管理人员</span><strong>进入教师与管理工作台</strong><small>{{ product.name }}管理、审核、指导与业务办理</small><b aria-hidden="true">→</b></a><a v-if="studentLoginUrl" :href="studentLoginUrl" class="yk-access-card"><span>学生</span><strong>进入学生门户</strong><small>查看本人事项、提交材料、查询进度与结果</small><b aria-hidden="true">→</b></a><a v-if="enterpriseLoginUrl && product.slug === 'internship'" :href="enterpriseLoginUrl" class="yk-access-card"><span>企业协同</span><strong>企业注册 / 登录</strong><small>首次注册由学校邀请激活，不开放自由注册</small><b aria-hidden="true">→</b></a></div><div class="yk-detail-secondary-actions"><router-link to="/products">返回产品中心</router-link><router-link :to="contactRoute">预约产品演示</router-link><a v-if="product.relationMap" :href="product.relationMap" target="_blank" rel="noopener noreferrer">查看{{ product.name }}完整业务地图</a></div></div></section>

      <section class="yk-final-cta"><div class="yk-shell yk-final-inner"><p class="yk-final-kicker">{{ product.name }}</p><h2>想把这套能力落到学校真实业务里？</h2><p>填写学校和联系电话即可预约产品演示；表单只用于把本次咨询短信通知给跃科商务联系人，不进入业务数据库。</p><div class="yk-final-actions"><router-link class="yk-button yk-button-light" :to="contactRoute">预约产品演示</router-link><a class="yk-button yk-button-ghost" :href="contact.phoneHref">拨打 {{ contact.phone }}</a></div></div></section>
    </main>

    <footer class="yk-footer"><div class="yk-shell yk-footer-inner"><div><strong>{{ companyName }}</strong><span>职业院校学生全生命周期数字化平台</span></div><div class="yk-footer-links"><router-link to="/products">产品中心</router-link><router-link to="/platform">平台能力</router-link><a :href="contact.phoneHref">{{ contact.phone }}</a><a v-if="icpNumber" :href="icpQueryUrl" target="_blank" rel="noopener noreferrer">{{ icpNumber }}</a><span>© {{ year }}</span></div></div></footer>
  </div>
</template>

<script>
import { getOfficialProduct } from '../../config/officialProducts'
import { OFFICIAL_SITE_CONTACT } from '../../config/officialSalesPages'
import { PRODUCT_STORIES } from '../../config/officialWebsiteStory'
import { COMPANY_NAME, ENTERPRISE_LOGIN_URL, ICP_NUMBER, ICP_QUERY_URL, STUDENT_LOGIN_URL, TEACHER_LOGIN_URL } from '../../config/portalConfig'
import '../../styles/official-site.css'
import '../../styles/official-site-story.css'

export default {
  name: 'OfficialProductView',
  data() { return { companyName: COMPANY_NAME, icpNumber: ICP_NUMBER, icpQueryUrl: ICP_QUERY_URL, teacherLoginUrl: TEACHER_LOGIN_URL, studentLoginUrl: STUDENT_LOGIN_URL, enterpriseLoginUrl: ENTERPRISE_LOGIN_URL } },
  computed: {
    product() { return getOfficialProduct(this.$route.params.slug) }, contact() { return OFFICIAL_SITE_CONTACT },
    story() { return PRODUCT_STORIES[this.product?.slug] || null }, roleJourneys() { return this.story?.roles || [] }, outcomes() { return this.story?.outcomes || [] }, faqs() { return this.story?.faqs || [] },
    contactRoute() { return { path: '/contact', query: { product: this.product?.slug || '' } } }, year() { return new Date().getFullYear() }
  },
  watch: { '$route.params.slug': { immediate: true, handler() { this.syncDocumentMeta() } } },
  methods: {
    syncDocumentMeta() { this.$nextTick(() => { if (!this.product) { this.$router.replace('/'); return } document.title = `${this.product.name}｜跃科职业院校学生全生命周期数字化平台`; let meta = document.querySelector('meta[name="description"]'); if (!meta) { meta = document.createElement('meta'); meta.setAttribute('name', 'description'); document.head.appendChild(meta) } meta.setAttribute('content', this.product.summary) }) }
  }
}
</script>