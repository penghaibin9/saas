<template>
  <div class="yk-site">
    <header class="yk-header">
      <div class="yk-shell yk-nav">
        <a class="yk-brand" href="#top" aria-label="返回首页">
          <span class="yk-brand-dot" aria-hidden="true">跃</span>
          <span class="yk-brand-copy">
            <strong>{{ platformName }}</strong>
            <small>{{ platformSubtitle }}</small>
          </span>
        </a>

        <nav class="yk-nav-links" aria-label="官网导航">
          <a href="#products">四大产品</a>
          <a href="#devices">多端协同</a>
          <a href="#access">进入系统</a>
          <a v-if="supportContact" href="#contact">联系跃科</a>
        </nav>

        <a v-if="teacherLoginUrl" class="yk-nav-cta" href="#access">选择入口</a>

        <button class="yk-menu-button" type="button" :aria-expanded="menuOpen ? 'true' : 'false'" aria-label="打开导航菜单" @click="menuOpen = !menuOpen">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
        </button>
      </div>

      <div v-if="menuOpen" class="yk-mobile-nav yk-shell">
        <a href="#products" @click="menuOpen = false">四大产品</a>
        <a href="#devices" @click="menuOpen = false">多端协同</a>
        <a href="#access" @click="menuOpen = false">进入系统</a>
        <a v-if="supportContact" href="#contact" @click="menuOpen = false">联系跃科</a>
      </div>
    </header>

    <main id="top">
      <section class="yk-hero" aria-labelledby="hero-title">
        <div class="yk-shell yk-hero-inner">
          <p class="yk-kicker">面向职业院校的学生全生命周期数字化平台</p>
          <h1 id="hero-title">让教务、学工、毕业设计与岗位实习，<br class="yk-desktop-break" />在一套平台里协同运行</h1>
          <p class="yk-hero-lead">从学校管理 PC、教师工作台，到学生 PC / 移动端与企业协同端，把流程、待办、风险与业务证据汇聚为可执行、可追踪、可审计的业务闭环。</p>
          <div class="yk-hero-actions">
            <a class="yk-button yk-button-primary" href="#products">查看四大产品 <span aria-hidden="true">→</span></a>
            <a class="yk-button yk-button-ghost" href="#access">进入系统</a>
          </div>

          <div class="yk-product-stage" aria-label="跃科真实产品界面">
            <div class="yk-stage-head">
              <div><strong>真实产品界面</strong><span>统一工作台 · 岗位实习 · 教务运行 · 学生门户</span></div>
              <span class="yk-stage-note">以下均为真实代码运行截图，不是 AI 绘制后台</span>
            </div>
            <div class="yk-shot-grid">
              <figure v-for="shot in heroScreens" :key="shot.src" class="yk-shot">
                <img :src="shot.src" :alt="shot.alt" loading="eager" decoding="async" />
                <figcaption>{{ shot.label }}</figcaption>
              </figure>
            </div>
          </div>
        </div>
      </section>

      <section class="yk-section yk-value-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">一条学生业务主线，连接不同角色</p>
            <h2>不是四套孤立软件，而是四个可协同的核心业务中心</h2>
            <p>老师先看到当前结论、待办与风险，学生围绕本人事项办理，企业只进入被授权的协同范围。</p>
          </div>
          <div class="yk-value-grid">
            <article v-for="item in platformFeatures" :key="item.title" class="yk-value-card">
              <span class="yk-icon-tile" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m12 3 7 4-7 4-7-4 7-4Zm-7 8 7 4 7-4M5 15l7 4 7-4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" /></svg></span>
              <h3>{{ item.title }}</h3><p>{{ item.desc }}</p>
            </article>
          </div>
        </div>
      </section>

      <section id="products" class="yk-section yk-products-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">四大核心产品</p>
            <h2>点进每个模块，看真实界面、业务链和多端协同</h2>
            <p>每个产品都有独立二级页面，不再把所有功能挤在首页。客户可以直接把产品页链接发给学校老师或项目负责人查看。</p>
          </div>

          <div class="yk-product-showcase-grid">
            <article v-for="product in products" :key="product.slug" class="yk-product-showcase-card">
              <router-link class="yk-product-cover" :to="`/products/${product.slug}`" :aria-label="`查看${product.name}详情`">
                <img :src="product.cover" :alt="product.coverAlt" loading="lazy" decoding="async" />
              </router-link>
              <div class="yk-product-showcase-body">
                <div class="yk-product-title-row">
                  <span class="yk-product-mark" :style="{ color: product.accent, background: product.soft }">{{ product.mark }}</span>
                  <div><span>{{ product.eyebrow }}</span><h3>{{ product.name }}</h3></div>
                </div>
                <p>{{ product.summary }}</p>
                <ul><li v-for="stage in product.previewStages" :key="stage">{{ stage }}</li></ul>
                <div class="yk-product-links">
                  <router-link class="yk-detail-link" :to="`/products/${product.slug}`">查看{{ product.name }}详情 <span aria-hidden="true">→</span></router-link>
                  <button type="button" @click="openFlow(product)">流程概览</button>
                  <a v-if="product.relationMap" :href="product.relationMap" target="_blank" rel="noopener noreferrer">关系图</a>
                </div>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section id="devices" class="yk-section yk-mobile-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">PC 与移动端各做擅长的事</p>
            <h2>老师管理、学生办理、企业协同，都有自己的正式入口</h2>
            <p>移动端不是简单缩小后台；管理 PC 承载复杂工作区，学生和教师移动端优先承载高频任务。</p>
          </div>
          <div class="yk-mobile-proof-grid">
            <article v-for="proof in mobileProofs" :key="proof.src" class="yk-mobile-proof">
              <div class="yk-phone-canvas"><img :src="proof.src" :alt="proof.alt" loading="lazy" decoding="async" /></div>
              <h3>{{ proof.title }}</h3><p>{{ proof.desc }}</p>
            </article>
          </div>
          <div v-if="hasAnyQr" class="yk-qr-row"><template v-for="mp in miniPrograms" :key="mp.key"><button v-if="mp.qr" type="button" @click="openQr(mp)">查看{{ mp.name }}码</button></template></div>
        </div>
      </section>

      <section id="access" class="yk-section yk-access-section">
        <div class="yk-shell">
          <div class="yk-section-heading yk-access-heading">
            <p class="yk-kicker">选择你的系统入口</p>
            <h2>原来的教师端、学生端、企业端入口继续保留，并且更清楚</h2>
            <p>入口地址由部署配置统一管理。学校如果以后改成独立子域名，只改配置，不需要重做官网。</p>
          </div>
          <div class="yk-access-grid yk-access-grid-three">
            <a v-if="teacherLoginUrl" :href="teacherLoginUrl" class="yk-access-card yk-access-primary"><span>教师 / 管理人员</span><strong>进入教师与管理工作台</strong><small>教务、学工、毕设、实习、审批、风险与管理工作</small><b aria-hidden="true">→</b></a>
            <a v-if="studentLoginUrl" :href="studentLoginUrl" class="yk-access-card"><span>学生</span><strong>进入学生门户</strong><small>查看待办、提交材料、查询进度与个人结果</small><b aria-hidden="true">→</b></a>
            <a v-if="enterpriseLoginUrl" :href="enterpriseLoginUrl" class="yk-access-card"><span>企业协同</span><strong>企业注册 / 登录</strong><small>岗位、实习协同与评价；首次注册由学校邀请激活</small><b aria-hidden="true">→</b></a>
          </div>
        </div>
      </section>

      <section id="contact" class="yk-final-cta">
        <div class="yk-shell yk-final-inner">
          <p class="yk-final-kicker">职业院校学生全生命周期数字化平台</p>
          <h2>让客户先看懂产品，再进入真实系统体验</h2>
          <p>官网负责讲清楚产品价值、真实界面和业务闭环；教师、学生、企业继续进入各自正式系统，不把宣传页和业务系统混在一起。</p>
          <div class="yk-final-actions"><a class="yk-button yk-button-light" href="#products">查看四大产品</a><span v-if="supportContact" class="yk-contact-text">商务 / 技术联系：{{ supportContact }}</span></div>
        </div>
      </section>
    </main>

    <footer class="yk-footer"><div class="yk-shell yk-footer-inner"><div><strong>{{ companyName }}</strong><span>职业院校学生全生命周期数字化平台</span></div><div class="yk-footer-links"><a v-for="item in footerLinks" :key="item.label" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.label }}</a><a v-if="icpNumber" :href="icpQueryUrl" target="_blank" rel="noopener noreferrer">{{ icpNumber }}</a><span>© {{ year }}</span></div></div></footer>

    <div v-if="modal" class="yk-modal-backdrop" role="presentation" @click.self="closeModal">
      <section class="yk-modal" role="dialog" aria-modal="true" :aria-label="modal.title">
        <button ref="modalClose" class="yk-modal-close" type="button" aria-label="关闭" @click="closeModal">×</button>
        <h2>{{ modal.title }}</h2>
        <ol v-if="modal.type === 'flow'" class="yk-flow-list"><li v-for="(step, index) in modal.steps" :key="`${index}-${step}`"><span>{{ index + 1 }}</span><p>{{ step }}</p></li></ol>
        <div v-else-if="modal.type === 'qr'" class="yk-qr-modal"><img v-if="modal.qr && !qrBroken" :src="modal.qr" :alt="`${modal.title}二维码`" @error="onQrError" /><p v-else>二维码暂不可用，请使用学校正式发布入口。</p></div>
      </section>
    </div>
  </div>
</template>

<script>
import { API_BASE_URL, API_PREFIX } from '../services/http/config'
import { HELP_FLOWS } from '../config/helpContent'
import { OFFICIAL_PRODUCT_LIST } from '../config/officialProducts'
import {
  COMPANY_NAME, DEFAULT_PLATFORM_NAME, DEFAULT_PLATFORM_SUBTITLE, ENTERPRISE_LOGIN_URL,
  ICP_NUMBER, ICP_QUERY_URL, PORTAL_MODULES, PRIVACY_URL, STUDENT_LOGIN_URL,
  STUDENT_MINIPROGRAM_QR, SUPPORT_CONTACT, SUPPORT_URL, TEACHER_LOGIN_URL,
  TEACHER_MINIPROGRAM_QR, TERMS_URL
} from '../config/portalConfig'
import '../styles/official-site.css'

const COVER_BY_PRODUCT = {
  'academic-affairs': '/official-site/academic.webp',
  'student-affairs': '/official-site/student-affairs-master.webp',
  graduation: '/official-site/graduation-overview.webp',
  internship: '/official-site/internship.webp'
}
const PORTAL_BY_KEY = Object.fromEntries(PORTAL_MODULES.map((item) => [item.key, item]))

export default {
  name: 'PortalHomeView',
  data() {
    return {
      menuOpen: false, modal: null, qrBroken: false, lastFocused: null, brand: null,
      companyName: COMPANY_NAME, icpNumber: ICP_NUMBER, icpQueryUrl: ICP_QUERY_URL,
      supportContact: SUPPORT_CONTACT, teacherLoginUrl: TEACHER_LOGIN_URL,
      studentLoginUrl: STUDENT_LOGIN_URL, enterpriseLoginUrl: ENTERPRISE_LOGIN_URL,
      heroScreens: [
        { src: '/official-site/workbench.webp', label: '统一工作台', alt: '跃科统一工作台真实产品界面' },
        { src: '/official-site/internship.webp', label: '岗位实习', alt: '跃科岗位实习中心真实产品界面' },
        { src: '/official-site/academic.webp', label: '教务运行', alt: '跃科教务运行工作台真实产品界面' },
        { src: '/official-site/student-portal.webp', label: '学生门户', alt: '跃科学生服务门户真实产品界面' }
      ],
      platformFeatures: [
        { title: '统一业务入口', desc: '教师、管理人员、学生和企业按身份进入对应工作区，官网只做清晰分流。' },
        { title: '流程可追踪', desc: '关键节点有状态、有责任、有过程记录，让业务从申请一直走到完成和归档。' },
        { title: '风险可处置', desc: '把异常和风险变成可执行待办，保持责任人、处置过程与后续跟进。' },
        { title: '多端协同', desc: '复杂管理工作留在 PC，高频事项进入学生和教师移动端，共享同一业务事实。' }
      ],
      mobileProofs: [
        { src: '/official-site/student-selection.webp', title: '学生移动端 · 网上选课', desc: '学生在移动端查看选课结果与状态，完成高频学业事项。', alt: '跃科学生移动端网上选课真实界面' },
        { src: '/official-site/teacher-graduation.webp', title: '教师移动端 · 毕设指导', desc: '教师查看毕业设计指导任务与过程事项，推进毕设业务。', alt: '跃科教师移动端毕业设计指导真实界面' },
        { src: '/official-site/teacher-taskbook.webp', title: '教师移动端 · 任务书', desc: '教师移动处理任务书相关工作，关键状态与 PC 业务链保持一致。', alt: '跃科教师移动端毕业设计任务书真实界面' }
      ]
    }
  },
  computed: {
    year() { return new Date().getFullYear() },
    platformName() { return (this.brand && this.brand.platformName) || DEFAULT_PLATFORM_NAME },
    platformSubtitle() { return (this.brand && this.brand.platformSubtitle) || DEFAULT_PLATFORM_SUBTITLE },
    products() {
      return OFFICIAL_PRODUCT_LIST.map((product) => {
        const portal = PORTAL_BY_KEY[product.key] || {}
        return { ...product, cover: COVER_BY_PRODUCT[product.slug], coverAlt: `跃科${product.name}真实产品界面`, previewStages: product.workflow.slice(0, 4), flowId: portal.flowId, relationMap: product.relationMap || portal.relationshipMap }
      })
    },
    miniPrograms() { return [{ key: 'teacher', name: '教师微信小程序', qr: TEACHER_MINIPROGRAM_QR }, { key: 'student', name: '学生微信小程序', qr: STUDENT_MINIPROGRAM_QR }] },
    hasAnyQr() { return this.miniPrograms.some((item) => !!item.qr) },
    footerLinks() { return [{ label: '隐私政策', url: PRIVACY_URL }, { label: '用户协议', url: TERMS_URL }, { label: '技术支持', url: SUPPORT_URL }].filter((item) => !!item.url) }
  },
  mounted() { document.title = `${this.platformName}｜职业院校学生全生命周期数字化平台`; this.loadBrand() },
  beforeUnmount() { document.body.style.overflow = '' },
  methods: {
    async loadBrand() {
      try {
        const res = await fetch(`${API_BASE_URL}${API_PREFIX}/authz/tenant/brand`, { headers: { Accept: 'application/json' } })
        if (!res.ok) return
        const payload = await res.json(); const data = payload && payload.data
        if (data && typeof data === 'object') { this.brand = data; document.title = `${this.platformName}｜职业院校学生全生命周期数字化平台` }
      } catch { /* 公共首页品牌接口异常时使用默认品牌 */ }
    },
    openFlow(product) {
      const flow = HELP_FLOWS.find((item) => item.id === product.flowId); if (!flow) return
      this.openModal({ type: 'flow', title: `${product.name} · ${flow.title}`, steps: flow.steps || [] })
    },
    openQr(mp) { if (!mp.qr) return; this.qrBroken = false; this.openModal({ type: 'qr', title: mp.name, qr: mp.qr }) },
    openModal(payload) { this.lastFocused = document.activeElement; this.modal = payload; document.body.style.overflow = 'hidden'; this.$nextTick(() => { const el = this.$refs.modalClose; if (el && el.focus) el.focus() }) },
    closeModal() { this.modal = null; document.body.style.overflow = ''; const prev = this.lastFocused; if (prev && prev.focus) prev.focus(); this.lastFocused = null },
    onQrError() { this.qrBroken = true }
  }
}
</script>
