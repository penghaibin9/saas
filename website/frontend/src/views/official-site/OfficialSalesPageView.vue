<template>
  <div v-if="page" class="yk-site yk-sales-page yk-story-site">

    <main id="main">
      <section class="yk-sales-hero" :class="{ 'yk-contact-hero': page.path === '/contact' }"><div class="yk-shell yk-sales-hero-grid" :class="{ 'yk-sales-hero-solo': !page.screenshots?.length }">
        <div class="yk-sales-copy"><p class="yk-kicker">{{ page.eyebrow }}</p><h1>{{ page.hero }}</h1><p class="yk-sales-lead">{{ page.description }}</p>
          <div class="yk-hero-actions" v-if="page.path !== '/contact'"><router-link class="yk-button yk-button-primary" :to="solutionContactRoute(page.path)">预约产品演示</router-link><a class="yk-button yk-button-ghost" :href="contact.phoneHref">电话咨询 {{ contact.phone }}</a><router-link class="yk-button yk-button-ghost" to="/">返回官网</router-link></div>
          <div v-if="page.path !== '/contact'" class="yk-sales-trust-row"><span>学生管理与高校人事分别规划</span><span>具体范围以项目方案为准</span></div>
        </div>
        <figure v-if="page.screenshots?.[0]" class="yk-sales-hero-shot"><OfficialImageZoom :src="page.screenshots[0]" :alt="`${page.navTitle}产品运行界面`" loading="eager" :caption="`${page.navTitle}产品运行界面`" /><figcaption>产品运行界面 · 页面内容为演示数据</figcaption></figure>
      </div></section>

      <ProductReadingGuide :path="$route.path" />
      <section v-if="page.path === '/contact'" class="yk-section yk-lead-section"><div class="yk-shell yk-lead-grid">
        <div class="yk-lead-copy"><p class="yk-kicker">围绕学校、机构与单位的需求讲解</p><h2>这次演示，先看什么？</h2><ul class="yk-consult-topics"><li>关注的业务、角色和办理流程</li><li>现有系统、历史数据与衔接需求</li><li>部署方式、实施范围与后续服务</li></ul><a class="yk-lead-phone" :href="contact.phoneHref">直接电话沟通 {{ contact.phone }}</a></div>
        <form class="yk-lead-form" @submit.prevent="submitLead" novalidate>
          <p class="yk-form-intro">填写预约信息 <small>带 * 的项目必填</small></p>
          <label><span id="lead-school-label">学校／机构／单位名称 *</span><input aria-labelledby="lead-school-label" ref="schoolInput" v-model.trim="leadForm.schoolName" maxlength="80" autocomplete="organization" placeholder="填写学校、培训机构或单位名称" :aria-invalid="leadInvalidField === 'schoolName' || undefined" :aria-describedby="leadInvalidField === 'schoolName' ? 'lead-error' : undefined" required /><small v-if="leadInvalidField === 'schoolName'" id="lead-error" class="yk-lead-field-error" role="alert">{{ leadError }}</small></label>
          <div class="yk-lead-form-row"><label><span id="lead-phone-label">手机号码 *</span><input aria-labelledby="lead-phone-label" ref="phoneInput" v-model.trim="leadForm.phone" type="tel" maxlength="11" inputmode="numeric" autocomplete="tel" placeholder="11 位手机号" :aria-invalid="leadInvalidField === 'phone' || undefined" :aria-describedby="leadInvalidField === 'phone' ? 'lead-error' : undefined" required /><small v-if="leadInvalidField === 'phone'" id="lead-error" class="yk-lead-field-error" role="alert">{{ leadError }}</small></label><label><span>联系人（选填）</span><input v-model.trim="leadForm.contactName" maxlength="40" autocomplete="name" placeholder="例如：张老师" /></label></div>
          <label><span>意向产品 *</span><select ref="interestInput" v-model="leadForm.interest" required :aria-invalid="leadInvalidField === 'interest' || undefined" :aria-describedby="leadInvalidField === 'interest' ? 'lead-error' : undefined"><option disabled value="">请选择关注的产品或方案</option><option v-for="interest in productInterests" :key="interest" :value="interest">{{ interest }}</option></select><small v-if="leadInvalidField === 'interest'" id="lead-error" class="yk-lead-field-error" role="alert">{{ leadError }}</small></label>
          <label><span>想重点了解什么（选填）</span><textarea v-model.trim="leadForm.message" maxlength="200" rows="3" placeholder="例如：想看实习周报如何提交和批阅"></textarea><small>{{ leadForm.message.length }}/200</small></label>
          <label class="yk-lead-honeypot" aria-hidden="true"><span>Website</span><input v-model="leadForm.website" tabindex="-1" autocomplete="off" /></label>
          <p class="yk-form-privacy">{{ leadMode==='registered'?'预约资料在独立官网加密保存 90 天，仅官网超级管理员查看，用于沟通本次需求。':leadMode==='sms'?'本次预约通过短信转交商务联系人，不登记在官网咨询台账。':'在线预约暂未启用，可以直接电话沟通；填写内容会保留。' }} <router-link to="/privacy">查看隐私政策</router-link>。</p>
          <p v-if="leadCapabilityState === 'loading'" role="status">正在确认预约服务状态…</p><p v-else-if="leadCapabilityState === 'error'" role="alert">预约服务状态暂时读取失败，填写内容已保留。<button type="button" @click="loadLeadMode">重新读取</button></p><label v-if="leadMode==='registered'" class="yk-lead-consent"><input type="checkbox" v-model="leadConsent" :disabled="leadSubmitting||leadSubmitted">我已了解资料用途与 90 天保存期限，同意用于本次咨询。</label>
          <button class="yk-button yk-button-primary yk-lead-submit" type="submit" :disabled="leadSubmitting || leadSubmitted || leadCapabilityState !== 'ready' || leadMode === 'unavailable'">{{ leadSubmitting ? '正在提交…' : leadSubmitted ? (leadReceiptMode==='registered'?'预约已登记':'预约已转交') : '提交预约' }}</button>
          <p v-if="leadError && !leadInvalidField" id="lead-error" class="yk-lead-error" role="alert">{{ leadError }}</p><p v-else-if="leadSubmitted" class="yk-lead-success" role="status">{{ leadReceiptMode==='registered'?'预约已登记，官网超级管理员可在后台查看本次需求。':'预约已通过短信转交商务联系人。' }}也可直接拨打 {{ contact.phone }}。</p>
        </form>
      </div></section>

      <section v-if="page.path === '/products'" class="yk-section"><div class="yk-shell">
        <div class="yk-product-lines"><article><p class="yk-kicker">学生培养与服务</p><h2>学生全生命周期管理</h2><p>连接学工、教务、岗位实习与毕业设计，关注每个阶段的任务、材料、进度与结果。</p><router-link class="yk-button yk-button-primary" to="/solutions/student-lifecycle">了解整体方案 →</router-link></article><article><p class="yk-kicker">人事治理与教师发展</p><h2>高校人事管理</h2><p>围绕教职工主档，组织招聘入职、在岗任用、发展评价与个人服务。</p><router-link class="yk-button yk-button-primary" to="/products/renshi">了解人事产品 →</router-link></article></div>
        <div class="yk-section-heading yk-section-heading-left"><p class="yk-kicker">从当前工作进入产品</p><h2>四个学生业务产品</h2><p>可从一条最需要解决的业务主线开始，逐步明确建设范围。</p></div>
        <div class="yk-sales-related-grid"><router-link v-for="item in relatedPages" :key="item.path" :to="item.path" class="yk-sales-related-card"><span>{{ item.eyebrow }}</span><strong>{{ item.navTitle }}</strong><p>{{ item.description }}</p><b aria-hidden="true">→</b></router-link></div>
      </div></section>

      <section v-if="!['/products', '/contact'].includes(page.path)" id="introduction" class="yk-section yk-sales-value-section"><div class="yk-shell">
        <div class="yk-section-heading yk-section-heading-left"><p class="yk-kicker">客户先理解怎么工作</p><h2>{{ storyHeading }}</h2><p>{{ storyLead }}</p></div>
        <ol v-if="storyProcess.length" class="yk-sales-process"><li v-for="step in storyProcess" :key="step">{{ step }}</li></ol>
        <div v-else class="yk-value-grid"><article v-for="item in valuePoints" :key="item.title" class="yk-value-card"><span class="yk-icon-tile" aria-hidden="true">{{ item.mark }}</span><h3>{{ item.title }}</h3><p>{{ item.desc }}</p></article></div>
        <ul v-if="storyFacts.length" class="yk-sales-facts"><li v-for="fact in storyFacts" :key="fact">{{ fact }}</li></ul>
        <p class="yk-story-fact">公开内容最近更新：<time :datetime="page.contentUpdatedAt">{{ page.contentUpdatedAt }}</time>。具体启用模块、数据迁移、系统集成与交付范围，以双方确认的实施方案为准。</p>
      </div></section>

      <section v-if="page.screenshots?.length" id="screens" class="yk-section yk-products-section"><div class="yk-shell">
        <div class="yk-section-heading"><p class="yk-kicker">产品运行界面</p><h2>从界面直接理解角色、流程和下一步动作</h2><p>页面中的学校、人员和业务数据均为演示数据，不包含真实学生及学校敏感信息。</p></div>
        <div class="yk-sales-evidence-grid"><figure v-for="(shot, index) in page.screenshots" :key="shot" class="yk-sales-evidence-card"><OfficialImageZoom :src="shot" :alt="`${page.navTitle}产品截图 ${index + 1}`" :caption="evidenceCaption(index)" /><figcaption>{{ evidenceCaption(index) }}</figcaption></figure></div>
      </div></section>

      <section v-if="storyFaqs.length && page.path !== '/contact'" class="yk-section yk-story-section"><div class="yk-shell"><div class="yk-section-heading"><p class="yk-kicker">直接回答采购和老师常问的问题</p><h2>{{ page.navTitle }}常见问题</h2></div><div class="yk-product-faq"><details v-for="item in storyFaqs" :key="item.q"><summary>{{ item.q }}</summary><p>{{ item.a }}</p></details></div></div></section>

      <section v-if="!['/products', '/contact'].includes(page.path)" class="yk-section yk-sales-related-section"><div class="yk-shell"><div class="yk-section-heading"><p class="yk-kicker">继续了解</p><h2>选择与你的工作相关的产品</h2></div><div class="yk-sales-related-grid"><router-link v-for="item in relatedPages" :key="item.path" :to="item.path" class="yk-sales-related-card"><span>{{ item.eyebrow }}</span><strong>{{ item.navTitle }}</strong><p>{{ item.description }}</p><b aria-hidden="true">→</b></router-link></div></div></section>

      <section v-if="page.path !== '/contact'" class="yk-final-cta"><div class="yk-shell yk-final-inner"><p class="yk-final-kicker">湖南跃科信息工程有限公司</p><h2>{{ page.path === '/contact' ? '从真实业务问题开始沟通' : '需要把这套能力落到学校真实流程里？' }}</h2><p>可直接沟通学生管理、高校人事、部署方式与系统集成。我们优先从学校当前的业务流程、角色和数据边界出发。</p><div class="yk-final-actions"><a class="yk-button yk-button-light" :href="contact.phoneHref">拨打 {{ contact.phone }}</a><router-link v-if="page.path !== '/contact'" class="yk-button yk-button-ghost" :to="solutionContactRoute(page.path)">预约产品演示</router-link></div></div></section>
    </main>

  </div>
</template>

<script>
import publicConfig from '../../config/publicWebsiteConfig.json'
import { OFFICIAL_SALES_PAGE_MAP, OFFICIAL_SALES_PAGES, OFFICIAL_SITE_CONTACT } from '@/config/officialSalesPages'
import OfficialImageZoom from '@/components/official-site/OfficialImageZoom.vue'
import ProductReadingGuide from '@/components/official-site/ProductReadingGuide.vue'
import { SALES_STORIES } from '@/config/officialWebsiteStory'
import { API_BASE_URL, API_PREFIX } from '@/services/http/config'
import { consultationContext, solutionContactRoute, PRODUCT_INTERESTS } from '@/config/companyProducts.js'
import '@/styles/official-site.css'
import '@/styles/official-site-story.css'

const DEFAULT_POINTS = Object.freeze([
  { mark: '1', title: '先解决真实工作', desc: '页面只讲现有业务闭环、角色和证据，不用抽象概念替代老师每天真正要处理的事情。' },
  { mark: '2', title: '状态与责任可追踪', desc: '关键业务以状态、责任人、下一动作和过程留痕组织，减少线下口头确认与重复沟通。' },
  { mark: '3', title: '多端共享业务事实', desc: '管理 PC、教师端、学生端与企业协同端共享同一业务状态，不让不同端各自维护一套真值。' },
  { mark: '4', title: '安全边界先于便利', desc: '多租户、权限、数据范围和审计继续作为生产底座，官网展示不改变系统已有安全边界。' }
])
const TYPE_COPY = Object.freeze({ solution: { title: '把分散功能收敛成可持续运行的学校工作方式', lead: '解决方案页面重点说明角色怎么协同、业务怎么连续、异常怎么处理，而不是重新罗列菜单。' }, service: { title: '功能上线之后，还要能稳定交付和持续维护', lead: '从学校开通、初始化、数据到运行支持和升级，交付过程同样需要标准化和可追踪。' }, contact: { title: '把需求说清楚，比先选一堆功能更重要', lead: '可以直接从学校当前最难推进的一条流程开始，先判断角色、状态、数据和部署边界，再讨论产品组合。' } })

function safeServerLeadMessage(payload, fallback) {
  const detail = typeof payload?.message === 'string' ? payload.message.trim() : ''
  if (!detail || detail.length > 100) return fallback
  if (['在线咨询暂时不可用','提交过于频繁','请确认咨询资料','本次预约内容已变化','请选择官网现有','来源文章暂不可用'].some(text=>detail.startsWith(text))) return detail
  return fallback
}

export default {
  name: 'OfficialSalesPageView',
  components: { OfficialImageZoom, ProductReadingGuide },
  data() { return { leadForm: { schoolName: '', contactName: '', phone: '', interest: '', message: '', website: '' }, leadMode:publicConfig.consultation.mode, leadContextMessage:'', leadCapabilityState:'loading', leadConsent:false, leadRequestId:'', leadRequestPayload:'', leadReceiptMode:'', leadSubmitting: false, leadSubmitted: false, leadError: '', leadInvalidField: '', valuePoints: DEFAULT_POINTS } },
  computed: {
    productInterests() { return PRODUCT_INTERESTS },
    page() { return OFFICIAL_SALES_PAGE_MAP[this.$route.path] || null }, contact() { return OFFICIAL_SITE_CONTACT }, year() { return new Date().getFullYear() },
    story() { return SALES_STORIES[this.page?.path] || null },
    storyHeading() { return this.story?.heading || (TYPE_COPY[this.page?.type] || TYPE_COPY.solution).title },
    storyLead() { return this.story?.lead || (TYPE_COPY[this.page?.type] || TYPE_COPY.solution).lead },
    storyProcess() { return this.story?.process || [] }, storyFacts() { return this.story?.facts || [] }, storyFaqs() { return this.story?.faqs || [] },
    relatedPages() {
      const priority = ['/products/academic-affairs', '/products/student-affairs', '/products/graduation', '/products/internship']
      if (this.page?.path === '/products') return priority.map((path) => OFFICIAL_SALES_PAGE_MAP[path]).filter(Boolean)
      if (this.page?.type === 'product') return OFFICIAL_SALES_PAGES.filter((item) => !['product', 'legal'].includes(item.type) && item.path !== '/contact').slice(0, 4)
      return [...priority, '/products/renshi'].map((path) => OFFICIAL_SALES_PAGE_MAP[path]).filter(Boolean)
    }
  },
  watch: {
    '$route.path': { immediate: true, handler() { this.syncHead() } },
    '$route.query': { handler(query) { this.applyContactContext(query) } }
  },
  mounted(){ this.applyContactContext(this.$route.query); this.loadLeadMode() },
  methods: {
    solutionContactRoute,
    applyContactContext(query) { const context = consultationContext(query); if (context.interest) this.leadForm.interest = context.interest; if (!this.leadForm.message || this.leadForm.message === this.leadContextMessage) this.leadForm.message = context.message; this.leadContextMessage = context.message },
    async loadLeadMode(){
      this.leadCapabilityState='loading'
      const controller = new AbortController()
      const timeout = setTimeout(() => controller.abort(), 10000)
      try {
        const response=await fetch(`${API_BASE_URL}${API_PREFIX}/notification/website-lead-capabilities`, { signal: controller.signal })
        const payload=await response.json()
        if(!response.ok || payload.code!==0 || !['registered','sms','unavailable'].includes(payload.data?.mode)) throw new Error('Capability unavailable')
        this.leadMode=payload.data.mode
        this.leadCapabilityState='ready'
      } catch { this.leadCapabilityState='error' }
      finally { clearTimeout(timeout) }
    },
    evidenceCaption(index) { return index === 0 ? `${this.page.navTitle}核心工作区 · 产品运行界面` : `${this.page.navTitle}业务界面 ${index + 1} · 演示数据` },
    async submitLead() {
      if (this.leadSubmitting || this.leadSubmitted || this.leadCapabilityState !== 'ready') return
      this.leadError = ''
      this.leadInvalidField = ''
      const phone = String(this.leadForm.phone || '').replace(/\D/g, '')
      if (this.leadForm.schoolName.trim().length < 2) { this.leadError = '请填写学校、机构或单位名称'; this.leadInvalidField = 'schoolName'; this.$refs.schoolInput.focus(); return }
      if (!/^1[3-9]\d{9}$/.test(phone)) { this.leadError = '请输入有效的 11 位手机号'; this.leadInvalidField = 'phone'; this.$refs.phoneInput.focus(); return }
      if (!this.productInterests.includes(this.leadForm.interest)) { this.leadError = '请选择关注的产品或方案'; this.leadInvalidField = 'interest'; this.$refs.interestInput.focus(); return }
      if(this.leadMode==='unavailable'){this.leadError=`在线预约暂未启用，请直接电话联系 ${this.contact.phone}。已填写内容会保留。`;return}
      if(this.leadMode==='registered'&&!this.leadConsent){this.leadError='请先确认资料用途与 90 天保存期限。';return}
      this.leadSubmitting = true
      const fallback = `提交失败，请直接电话联系 ${this.contact.phone}`
      try {
        const body={school_name:this.leadForm.schoolName,contact_name:this.leadForm.contactName,phone,interest:this.leadForm.interest,message:this.leadForm.message,website:this.leadForm.website,source_path:this.$route.query.source==='official-showcase'?'/#showcase':'/contact',source_article:/^[a-f0-9]{32}$/.test(String(this.$route.query.article||''))?String(this.$route.query.article):null,consent:this.leadConsent}
        const stable=JSON.stringify(body)
        if(!this.leadRequestId||stable!==this.leadRequestPayload){this.leadRequestId=crypto.randomUUID().replaceAll('-','');this.leadRequestPayload=stable}
        const response = await fetch(`${API_BASE_URL}${API_PREFIX}/notification/website-lead`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({...body,request_id:this.leadRequestId}) })
        const payload = await response.json().catch(() => null)
        if (!response.ok || payload?.code !== 0 || payload?.data?.accepted !== true) throw new Error(safeServerLeadMessage(payload, fallback))
        this.leadSubmitted = true
        this.leadReceiptMode=payload.data.mode
      } catch (error) { this.leadError = error instanceof Error && error.message ? error.message : fallback }
      finally { this.leadSubmitting = false }
    },
    syncHead() {
      if (typeof document === 'undefined') return
      this.$nextTick(() => {
        if (!this.page) { this.$router.replace('/'); return }
        document.title = this.page.title
        let meta = document.querySelector('meta[name="description"]')
        if (!meta) { meta = document.createElement('meta'); meta.setAttribute('name', 'description'); document.head.appendChild(meta) }
        meta.setAttribute('content', this.page.description)
      })
    }
  }
}
</script>

<style scoped>
.yk-lead-form label > .yk-lead-field-error{justify-self:start;color:#a82e2e;font-size:13px;line-height:1.6}
.yk-lead-form .yk-lead-consent{display:flex;gap:10px;align-items:flex-start;font-size:13px;font-weight:400;line-height:1.8}.yk-lead-form .yk-lead-consent input{width:20px;min-width:20px;height:20px;margin:3px 0;padding:0}
.yk-contact-hero .yk-sales-hero-grid{padding-top:36px;padding-bottom:28px}.yk-contact-hero h1{font-size:clamp(28px,3.6vw,42px);line-height:1.45}.yk-contact-hero .yk-sales-lead{margin-top:12px}.yk-lead-section{padding-top:32px}.yk-consult-topics{padding-left:20px;margin:24px 0;color:#53677b;line-height:2.2;font-size:15px}.yk-form-intro{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:0;color:#173d71;font-weight:700}.yk-form-intro small{font-size:12px;font-weight:400;color:#53677b}.yk-form-privacy{margin:0;color:#53677b;font-size:12px;line-height:1.8}.yk-form-privacy a{color:#145cc9;text-decoration:underline}.yk-lead-form input[aria-invalid=true]{border-color:#a82e2e}@media(max-width:900px){.yk-lead-form{order:0}.yk-lead-copy{order:1}.yk-lead-grid{gap:32px}.yk-lead-copy h2{font-size:25px}.yk-contact-hero .yk-sales-hero-grid{padding-top:26px;padding-bottom:20px}.yk-lead-section{padding-top:24px}.yk-consult-topics{margin:16px 0}.yk-lead-phone{margin-top:12px}}
.yk-sales-hero-solo{grid-template-columns:1fr;max-width:1000px}.yk-sales-hero-solo .yk-sales-copy{max-width:880px}.yk-product-lines{display:grid;grid-template-columns:1fr 1fr;gap:32px;margin-bottom:72px}.yk-product-lines article{border-top:3px solid #2371e8;padding:32px;background:#f5f8fc}.yk-product-lines h2{font-size:28px;color:#102d45}.yk-product-lines article>p:not(.yk-kicker){color:#53677b;line-height:1.9;margin:20px 0 28px}.yk-lead-privacy a{text-decoration:underline}@media(max-width:700px){.yk-product-lines{grid-template-columns:1fr;gap:24px}.yk-product-lines article{padding:24px}.yk-product-lines h2{font-size:24px}}
</style>
