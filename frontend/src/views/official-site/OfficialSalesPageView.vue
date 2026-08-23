<template>
  <div v-if="page" class="yk-site yk-sales-page yk-story-site">
    <header class="yk-header"><div class="yk-shell yk-nav">
      <router-link class="yk-brand" to="/" aria-label="返回跃科官网首页"><span class="yk-brand-dot" aria-hidden="true">跃</span><span class="yk-brand-copy"><strong>跃科</strong><small>职业院校学生全生命周期平台</small></span></router-link>
      <nav class="yk-nav-links" aria-label="销售页面导航"><router-link to="/products">产品</router-link><router-link to="/solutions/student-lifecycle">学生生命周期</router-link><router-link to="/platform">平台能力</router-link><router-link to="/solutions/deployment">部署与服务</router-link><router-link to="/contact">联系跃科</router-link></nav>
      <router-link class="yk-nav-cta" to="/contact">预约产品演示</router-link>
    </div></header>

    <main>
      <section class="yk-sales-hero"><div class="yk-shell yk-sales-hero-grid">
        <div class="yk-sales-copy"><p class="yk-kicker">{{ page.eyebrow }}</p><h1>{{ page.hero }}</h1><p class="yk-sales-lead">{{ page.description }}</p>
          <div class="yk-hero-actions"><router-link v-if="page.path !== '/contact'" class="yk-button yk-button-primary" to="/contact">预约产品演示</router-link><a class="yk-button yk-button-ghost" :href="contact.phoneHref">电话咨询 {{ contact.phone }}</a><router-link class="yk-button yk-button-ghost" to="/">返回官网</router-link></div>
          <div class="yk-sales-trust-row"><span>真实产品截图</span><span>真实业务代码</span><span>不伪造客户数据</span><span>口径核验 {{ factAuditDate }}</span></div>
        </div>
        <figure v-if="page.screenshots?.[0]" class="yk-sales-hero-shot"><img :src="page.screenshots[0]" :alt="`${page.navTitle}真实产品界面`" decoding="async" /><figcaption>真实运行界面 · 业务数据来自隔离测试环境</figcaption></figure>
      </div></section>

      <section v-if="page.path === '/contact'" class="yk-section yk-lead-section"><div class="yk-shell yk-lead-grid">
        <div class="yk-lead-copy"><p class="yk-kicker">预约产品演示</p><h2>留下学校和电话，我会直接收到短信</h2><p>填写后，系统会把学校、联系人、联系电话、意向产品和留言摘要直接短信发送给跃科商务联系人。</p><div class="yk-lead-privacy"><strong>不进入业务数据库</strong><span>本次咨询不创建销售线索表，不保存访客手机号或留言到跃科业务数据库。</span></div><a class="yk-lead-phone" :href="contact.phoneHref">也可以直接拨打 {{ contact.phone }}</a></div>
        <form class="yk-lead-form" @submit.prevent="submitLead" novalidate>
          <label><span>学校名称 *</span><input v-model.trim="leadForm.schoolName" maxlength="80" autocomplete="organization" placeholder="例如：湖南某职业学院" required /></label>
          <div class="yk-lead-form-row"><label><span>联系人</span><input v-model.trim="leadForm.contactName" maxlength="40" autocomplete="name" placeholder="例如：张老师" /></label><label><span>联系电话 *</span><input v-model.trim="leadForm.phone" maxlength="11" inputmode="numeric" autocomplete="tel" placeholder="11 位手机号" required /></label></div>
          <label><span>意向产品 *</span><select v-model="leadForm.interest" required><option value="教务系统">教务系统</option><option value="学工中心">学工中心</option><option value="毕业设计">毕业设计</option><option value="岗位实习">岗位实习</option><option value="数字迎新">数字迎新</option><option value="学生全生命周期平台">学生全生命周期平台</option><option value="私有化部署与系统集成">私有化部署与系统集成</option></select></label>
          <label><span>想重点了解什么</span><textarea v-model.trim="leadForm.message" maxlength="200" rows="4" placeholder="例如：想了解岗位实习模块、部署方式和报价"></textarea><small>{{ leadForm.message.length }}/200</small></label>
          <label class="yk-lead-honeypot" aria-hidden="true"><span>Website</span><input v-model="leadForm.website" tabindex="-1" autocomplete="off" /></label>
          <button class="yk-button yk-button-primary yk-lead-submit" type="submit" :disabled="leadSubmitting || leadSubmitted">{{ leadSubmitting ? '正在提交…' : leadSubmitted ? '已提交，我们会尽快联系' : '提交并短信通知跃科' }}</button>
          <p v-if="leadError" class="yk-lead-error" role="alert">{{ leadError }}</p><p v-else-if="leadSubmitted" class="yk-lead-success" role="status">提交成功。你的信息已用于本次短信通知，不会写入跃科业务数据库。</p>
        </form>
      </div></section>

      <section class="yk-section yk-sales-value-section"><div class="yk-shell">
        <div class="yk-section-heading yk-section-heading-left"><p class="yk-kicker">客户先理解怎么工作</p><h2>{{ storyHeading }}</h2><p>{{ storyLead }}</p></div>
        <ol v-if="storyProcess.length" class="yk-sales-process"><li v-for="step in storyProcess" :key="step">{{ step }}</li></ol>
        <div v-else class="yk-value-grid"><article v-for="item in valuePoints" :key="item.title" class="yk-value-card"><span class="yk-icon-tile" aria-hidden="true">{{ item.mark }}</span><h3>{{ item.title }}</h3><p>{{ item.desc }}</p></article></div>
        <ul v-if="storyFacts.length" class="yk-sales-facts"><li v-for="fact in storyFacts" :key="fact">{{ fact }}</li></ul>
        <p class="yk-story-fact">公开口径最近更新：<time :datetime="page.contentUpdatedAt">{{ page.contentUpdatedAt }}</time>。产品事实核验基线：{{ factAuditDate }}。页面只描述当前能够回到代码、帮助中心或真实浏览器证据的能力。</p>
      </div></section>

      <section v-if="page.screenshots?.length" class="yk-section yk-products-section"><div class="yk-shell">
        <div class="yk-section-heading"><p class="yk-kicker">真实产品证据</p><h2>客户看到的是已经运行的系统界面，不是概念效果图</h2><p>截图来自仓库真实代码和隔离 Playwright / E2E 环境，仅用于说明产品能力与界面结构，不代表真实学校运营规模或客户案例。</p></div>
        <div class="yk-sales-evidence-grid"><figure v-for="(shot, index) in page.screenshots" :key="shot" class="yk-sales-evidence-card"><img :src="shot" :alt="`${page.navTitle}真实产品截图 ${index + 1}`" loading="lazy" decoding="async" /><figcaption>{{ evidenceCaption(index) }}</figcaption></figure></div>
      </div></section>

      <section v-if="storyFaqs.length" class="yk-section yk-story-section"><div class="yk-shell"><div class="yk-section-heading"><p class="yk-kicker">直接回答采购和老师常问的问题</p><h2>{{ page.navTitle }}常见问题</h2></div><div class="yk-product-faq"><details v-for="item in storyFaqs" :key="item.q"><summary>{{ item.q }}</summary><p>{{ item.a }}</p></details></div></div></section>

      <section class="yk-section yk-sales-related-section"><div class="yk-shell"><div class="yk-section-heading"><p class="yk-kicker">继续了解</p><h2>从当前问题进入对应产品，而不是在官网里迷路</h2></div><div class="yk-sales-related-grid"><router-link v-for="item in relatedPages" :key="item.path" :to="item.path" class="yk-sales-related-card"><span>{{ item.eyebrow }}</span><strong>{{ item.navTitle }}</strong><p>{{ item.description }}</p><b aria-hidden="true">→</b></router-link></div></div></section>

      <section class="yk-final-cta"><div class="yk-shell yk-final-inner"><p class="yk-final-kicker">湖南跃科信息工程有限公司</p><h2>{{ page.path === '/contact' ? '从真实业务问题开始沟通' : '需要把这套能力落到学校真实流程里？' }}</h2><p>可直接沟通教务、学工、毕业设计、岗位实习、数字迎新、部署方式与系统集成。我们优先从学校当前的业务流程、角色和数据边界出发。</p><div class="yk-final-actions"><a class="yk-button yk-button-light" :href="contact.phoneHref">拨打 {{ contact.phone }}</a><router-link v-if="page.path !== '/contact'" class="yk-button yk-button-ghost" to="/contact">预约产品演示</router-link></div></div></section>
    </main>

    <footer class="yk-footer"><div class="yk-shell yk-footer-inner"><div><strong>{{ contact.company }}</strong><span>职业院校学生全生命周期数字化平台</span></div><div class="yk-footer-links"><router-link to="/products">产品中心</router-link><router-link to="/about">关于跃科</router-link><a :href="contact.phoneHref">{{ contact.phone }}</a><span>© {{ year }}</span></div></div></footer>
  </div>
</template>

<script>
import { OFFICIAL_SALES_PAGE_MAP, OFFICIAL_SALES_PAGES, OFFICIAL_SITE_CONTACT } from '@/config/officialSalesPages'
import { OFFICIAL_FACT_AUDIT_DATE, SALES_STORIES } from '@/config/officialWebsiteStory'
import { API_BASE_URL, API_PREFIX } from '@/services/http/config'
import '@/styles/official-site.css'
import '@/styles/official-site-story.css'

const DEFAULT_POINTS = Object.freeze([
  { mark: '1', title: '先解决真实工作', desc: '页面只讲现有业务闭环、角色和证据，不用抽象概念替代老师每天真正要处理的事情。' },
  { mark: '2', title: '状态与责任可追踪', desc: '关键业务以状态、责任人、下一动作和过程留痕组织，减少线下口头确认与重复沟通。' },
  { mark: '3', title: '多端共享业务事实', desc: '管理 PC、教师端、学生端与企业协同端共享同一业务状态，不让不同端各自维护一套真值。' },
  { mark: '4', title: '安全边界先于便利', desc: '多租户、权限、数据范围和审计继续作为生产底座，官网展示不改变系统已有安全边界。' }
])
const TYPE_COPY = Object.freeze({ solution: { title: '把分散功能收敛成可持续运行的学校工作方式', lead: '解决方案页面重点说明角色怎么协同、业务怎么连续、异常怎么处理，而不是重新罗列菜单。' }, service: { title: '功能上线之后，还要能稳定交付和持续维护', lead: '从学校开通、初始化、数据到运行支持和升级，交付过程同样需要标准化和可追踪。' }, contact: { title: '把需求说清楚，比先选一堆功能更重要', lead: '可以直接从学校当前最难推进的一条流程开始，先判断角色、状态、数据和部署边界，再讨论产品组合。' } })
const PRODUCT_INTEREST_BY_SLUG = Object.freeze({ 'academic-affairs': '教务系统', 'student-affairs': '学工中心', graduation: '毕业设计', internship: '岗位实习' })

function safeServerLeadMessage(payload, fallback) {
  const detail = typeof payload?.detail === 'string' ? payload.detail.trim() : ''
  if (!detail || detail.length > 100) return fallback
  if (detail.startsWith('在线咨询暂时不可用') || detail.startsWith('提交过于频繁')) return detail
  return fallback
}

export default {
  name: 'OfficialSalesPageView',
  data() { return { leadForm: { schoolName: '', contactName: '', phone: '', interest: '学生全生命周期平台', message: '', website: '' }, leadSubmitting: false, leadSubmitted: false, leadError: '', factAuditDate: OFFICIAL_FACT_AUDIT_DATE, valuePoints: DEFAULT_POINTS } },
  computed: {
    page() { return OFFICIAL_SALES_PAGE_MAP[this.$route.path] || null }, contact() { return OFFICIAL_SITE_CONTACT }, year() { return new Date().getFullYear() },
    story() { return SALES_STORIES[this.page?.path] || null },
    storyHeading() { return this.story?.heading || (TYPE_COPY[this.page?.type] || TYPE_COPY.solution).title },
    storyLead() { return this.story?.lead || (TYPE_COPY[this.page?.type] || TYPE_COPY.solution).lead },
    storyProcess() { return this.story?.process || [] }, storyFacts() { return this.story?.facts || [] }, storyFaqs() { return this.story?.faqs || [] },
    relatedPages() {
      const priority = ['/products/academic-affairs', '/products/student-affairs', '/products/graduation', '/products/internship']
      if (this.page?.path === '/products') return priority.map((path) => OFFICIAL_SALES_PAGE_MAP[path]).filter(Boolean)
      if (this.page?.type === 'product') return OFFICIAL_SALES_PAGES.filter((item) => item.type !== 'product' && item.path !== '/contact').slice(0, 4)
      return priority.map((path) => OFFICIAL_SALES_PAGE_MAP[path]).filter(Boolean)
    }
  },
  watch: {
    '$route.path': { immediate: true, handler() { this.syncHead() } },
    '$route.query.product': { immediate: true, handler(slug) { const interest = PRODUCT_INTEREST_BY_SLUG[String(slug || '').trim()]; if (interest) this.leadForm.interest = interest } }
  },
  methods: {
    evidenceCaption(index) { return index === 0 ? `${this.page.navTitle}核心工作区 · 真实运行界面` : `${this.page.navTitle}真实业务界面 ${index + 1} · 隔离测试数据` },
    async submitLead() {
      this.leadError = ''
      const phone = String(this.leadForm.phone || '').replace(/\D/g, '')
      if (this.leadForm.schoolName.trim().length < 2) { this.leadError = '请填写学校名称'; return }
      if (!/^1[3-9]\d{9}$/.test(phone)) { this.leadError = '请输入有效的 11 位手机号'; return }
      this.leadSubmitting = true
      const fallback = `提交失败，请直接电话联系 ${this.contact.phone}`
      try {
        const response = await fetch(`${API_BASE_URL}${API_PREFIX}/notification/website-lead`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ school_name: this.leadForm.schoolName, contact_name: this.leadForm.contactName, phone, interest: this.leadForm.interest, message: this.leadForm.message, website: this.leadForm.website }) })
        const payload = await response.json().catch(() => null)
        if (!response.ok) throw new Error(safeServerLeadMessage(payload, fallback))
        this.leadSubmitted = true
      } catch (error) { this.leadError = error instanceof Error && error.message ? error.message : fallback }
      finally { this.leadSubmitting = false }
    },
    syncHead() {
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