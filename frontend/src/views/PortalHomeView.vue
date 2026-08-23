<template>
  <div class="yk-site yk-story-site">
    <header class="yk-header">
      <div class="yk-shell yk-nav">
        <a class="yk-brand" href="#top" aria-label="返回首页">
          <span class="yk-brand-dot" aria-hidden="true">跃</span>
          <span class="yk-brand-copy"><strong>{{ platformName }}</strong><small>{{ platformSubtitle }}</small></span>
        </a>
        <nav class="yk-nav-links" aria-label="官网导航">
          <a href="#products">产品</a>
          <a href="#lifecycle">学生生命周期</a>
          <a href="#platform">平台能力</a>
          <router-link to="/solutions/deployment">部署与服务</router-link>
          <router-link to="/contact">联系跃科</router-link>
        </nav>
        <router-link class="yk-nav-cta" to="/contact">预约产品演示</router-link>
        <button class="yk-menu-button" type="button" :aria-expanded="menuOpen ? 'true' : 'false'" aria-label="打开导航菜单" @click="menuOpen = !menuOpen">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" /></svg>
        </button>
      </div>
      <div v-if="menuOpen" class="yk-mobile-nav yk-shell">
        <a href="#products" @click="menuOpen = false">产品</a>
        <a href="#lifecycle" @click="menuOpen = false">学生生命周期</a>
        <a href="#platform" @click="menuOpen = false">平台能力</a>
        <router-link to="/solutions/deployment" @click="menuOpen = false">部署与服务</router-link>
        <router-link to="/contact" @click="menuOpen = false">联系跃科</router-link>
      </div>
    </header>

    <main id="top">
      <section class="yk-hero" aria-labelledby="hero-title">
        <div class="yk-shell yk-hero-inner">
          <p class="yk-kicker">面向职业院校的学生全生命周期数字化平台</p>
          <h1 id="hero-title">让学生从入校、在校、教学、实践到毕业就业，<br class="yk-desktop-break" />始终在同一条业务主线上</h1>
          <p class="yk-hero-lead">跃科以岗位实习、毕业设计、学工、教务为重点业务中心，连接数字迎新、统一工作台、学生服务和多端协同，让流程可执行、状态可追踪、风险可处置、关键操作可审计。</p>
          <div class="yk-hero-actions">
            <a class="yk-button yk-button-primary" href="#lifecycle">看学生生命周期 <span aria-hidden="true">→</span></a>
            <router-link class="yk-button yk-button-ghost" to="/contact">预约产品演示</router-link>
            <router-link class="yk-button yk-button-ghost" to="/solutions/deployment">了解部署方式</router-link>
          </div>
          <div class="yk-product-stage" aria-label="跃科真实产品界面">
            <div class="yk-stage-head">
              <div><strong>不是概念效果图</strong><span>统一工作台 · 岗位实习 · 教务运行 · 学生门户</span></div>
              <span class="yk-stage-note">真实代码运行界面 · 隔离测试数据</span>
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

      <section id="pain" class="yk-section yk-story-section yk-pain-section">
        <div class="yk-shell">
          <div class="yk-section-heading yk-section-heading-left">
            <p class="yk-kicker">先看学校真实工作，而不是先堆功能</p>
            <h2>系统已经不少，为什么老师还是忙在表格、群聊和临时汇总里？</h2>
            <p>跃科官网先把学校常见的工作断点讲清楚，再告诉客户系统如何把这些事情重新组织成业务闭环。</p>
          </div>
          <div class="yk-pain-grid">
            <article v-for="item in painPoints" :key="item.mark" class="yk-pain-card">
              <span>{{ item.mark }}</span><h3>{{ item.title }}</h3><p>{{ item.answer }}</p>
            </article>
          </div>
        </div>
      </section>

      <section id="lifecycle" class="yk-section yk-story-section yk-lifecycle-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">一张图看懂学生业务怎么连起来</p>
            <h2>迎新 → 在校 → 教学 → 实习 → 毕设 → 就业衔接</h2>
            <p>每个阶段都不是孤岛：共享学生、组织、身份、权限和业务事实，老师、学生与管理部门在不同端协同完成同一件事。</p>
          </div>
          <ol class="yk-lifecycle-track">
            <li v-for="(item, index) in lifecycleStages" :key="item.key" class="yk-lifecycle-card">
              <router-link :to="item.route">
                <div class="yk-lifecycle-top"><span class="yk-lifecycle-index">0{{ index + 1 }}</span><span>{{ item.stage }}</span></div>
                <h3>{{ item.title }}</h3><p>{{ item.desc }}</p>
                <figure><img :src="item.proof" :alt="`${item.title}真实产品界面`" loading="lazy" decoding="async" /></figure>
                <strong>了解这一阶段 <span aria-hidden="true">→</span></strong>
              </router-link>
            </li>
          </ol>
        </div>
      </section>

      <section id="products" class="yk-section yk-products-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">四大核心产品</p>
            <h2>每个产品都能看真实界面、业务链、角色分工和最终证据</h2>
            <p>岗位实习与毕业设计突出全过程闭环，教务与学工体现平台深度；客户不登录系统，也能先完成一轮产品认知。</p>
          </div>
          <div class="yk-product-showcase-grid">
            <article v-for="product in products" :key="product.slug" class="yk-product-showcase-card">
              <router-link class="yk-product-cover" :to="`/products/${product.slug}`" :aria-label="`查看${product.name}详情`"><img :src="product.cover" :alt="product.coverAlt" loading="lazy" decoding="async" /></router-link>
              <div class="yk-product-showcase-body">
                <div class="yk-product-title-row"><span class="yk-product-mark" :style="{ color: product.accent, background: product.soft }">{{ product.mark }}</span><div><span>{{ product.eyebrow }}</span><h3>{{ product.name }}</h3></div></div>
                <p>{{ product.summary }}</p>
                <ul><li v-for="stage in product.previewStages" :key="stage">{{ stage }}</li></ul>
                <div class="yk-product-links">
                  <router-link class="yk-detail-link" :to="`/products/${product.slug}`">完整了解{{ product.name }} <span aria-hidden="true">→</span></router-link>
                  <button type="button" @click="openFlow(product)">流程概览</button>
                  <a v-if="product.relationMap" :href="product.relationMap" target="_blank" rel="noopener noreferrer">完整业务地图</a>
                </div>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section id="work-hub" class="yk-section yk-story-section yk-work-hub-section">
        <div class="yk-shell">
          <div class="yk-section-heading yk-section-heading-left">
            <p class="yk-kicker">老师围绕事情工作，而不是围绕菜单找功能</p>
            <h2>工作台、审批、消息，把不同业务中心重新汇到老师每天的工作入口</h2>
            <p>这是跃科从“四个模块”走向“一套平台”的关键：重要事项先进入待办和工作台，审批有统一入口，结果通过消息持续送达。</p>
          </div>
          <div class="yk-proof-story-list">
            <article v-for="(proof, index) in workHubProofs" :key="proof.key" class="yk-proof-story" :class="{ 'yk-proof-story-reverse': index % 2 === 1 }">
              <figure><img :src="proof.image" :alt="`${proof.title}真实产品界面`" loading="lazy" decoding="async" /></figure>
              <div><span class="yk-proof-tag">真实产品证据</span><h3>{{ proof.title }}</h3><p>{{ proof.desc }}</p><router-link to="/solutions/teacher-workbench">了解统一教师工作方式 →</router-link></div>
            </article>
          </div>
        </div>
      </section>

      <section id="orientation" class="yk-section yk-story-section yk-orientation-section">
        <div class="yk-shell yk-orientation-layout">
          <div class="yk-orientation-copy">
            <p class="yk-kicker">生命周期第一站 · 数字迎新</p>
            <h2>从到校前开始在线报到，让现场不再靠多张表来回确认</h2>
            <p>预报到信息、资格与材料、绿色通道、宿舍、现场核验、异常与未报到、统计归档放在同一迎新批次中持续推进。</p>
            <ol class="yk-inline-flow"><li v-for="step in orientationSteps" :key="step">{{ step }}</li></ol>
            <router-link class="yk-button yk-button-primary" to="/solutions/orientation">完整了解数字迎新 →</router-link>
          </div>
          <div class="yk-orientation-proofs">
            <figure><img src="/official-site/orientation-overview.webp" alt="跃科数字迎新管理看板真实产品界面" loading="lazy" /><figcaption>数字迎新管理看板 · 隔离测试数据</figcaption></figure>
            <figure><img src="/official-site/orientation-progress.webp" alt="跃科数字迎新报到进度真实产品界面" loading="lazy" /><figcaption>迎新报到进度 · 隔离测试数据</figcaption></figure>
          </div>
        </div>
      </section>

      <section id="devices" class="yk-section yk-mobile-section">
        <div class="yk-shell">
          <div class="yk-section-heading"><p class="yk-kicker">PC 与移动端各做擅长的事</p><h2>复杂工作留在 PC，高频任务进入学生门户、微信小程序与 H5</h2><p>移动端不是把 PC 后台简单缩小，而是围绕“查、申、填、报、审核、核验、批阅、风险处理”等高频任务重新组织。</p></div>
          <div class="yk-mobile-proof-grid">
            <article v-for="proof in mobileProofs" :key="proof.src" class="yk-mobile-proof"><div class="yk-phone-canvas"><img :src="proof.src" :alt="proof.alt" loading="lazy" decoding="async" /></div><h3>{{ proof.title }}</h3><p>{{ proof.desc }}</p></article>
          </div>
          <div v-if="hasAnyQr" class="yk-qr-row"><template v-for="mp in miniPrograms" :key="mp.key"><button v-if="mp.qr" type="button" @click="openQr(mp)">查看{{ mp.name }}码</button></template></div>
        </div>
      </section>

      <section id="platform" class="yk-section yk-story-section yk-platform-section">
        <div class="yk-shell">
          <div class="yk-section-heading yk-section-heading-left"><p class="yk-kicker">一套底座托住所有业务</p><h2>客户买到的不只是页面，还有学校级身份、权限、数据和治理边界</h2><p>下面这些能力在教务、学工、实习、毕设等业务中心之间共享，避免每个模块各自维护一套账号、权限和基础数据。</p></div>
          <div class="yk-platform-layout">
            <div class="yk-foundation-grid"><article v-for="item in platformFoundation" :key="item.key"><span>{{ item.title }}</span><p>{{ item.desc }}</p></article></div>
            <figure class="yk-platform-proof"><img src="/official-site/leadership-cockpit.webp" alt="跃科领导数据驾驶舱真实产品界面" loading="lazy" /><figcaption><strong>管理者不只看“有多少数据”</strong><span>更重要的是看进度、异常、风险与趋势。该截图为隔离测试环境界面。</span></figcaption></figure>
          </div>
          <div class="yk-proof-pending-note"><strong>平台治理真实截图持续补齐：</strong><span>角色权限、数据范围、学校品牌、安全审计、数据交换与实施验收将直接由本分支生产 E2E 从隔离管理员环境抓取，不使用概念图替代。</span></div>
          <router-link class="yk-text-link" to="/solutions/security-governance">查看平台安全与数据治理 →</router-link>
        </div>
      </section>

      <section id="delivery" class="yk-section yk-story-section yk-delivery-section">
        <div class="yk-shell">
          <div class="yk-section-heading"><p class="yk-kicker">从功能到真正上线</p><h2>学校初始化、历史数据、角色权限、业务配置、上线检查和后续升级都有落点</h2><p>不承诺未经真实项目验证的固定交付天数；先把一个学校项目真正要经历的实施步骤讲清楚。</p></div>
          <ol class="yk-implementation-grid"><li v-for="step in implementationSteps" :key="step.n"><span>{{ step.n }}</span><h3>{{ step.title }}</h3><p>{{ step.desc }}</p></li></ol>
          <div class="yk-delivery-actions"><router-link class="yk-button yk-button-primary" to="/solutions/deployment">了解部署与上线</router-link><router-link class="yk-button yk-button-ghost" to="/services/delivery">了解实施与服务</router-link></div>
        </div>
      </section>

      <section id="faq" class="yk-section yk-story-section yk-faq-section">
        <div class="yk-shell yk-faq-layout">
          <div class="yk-section-heading yk-section-heading-left"><p class="yk-kicker">客户第一次看官网最常问的问题</p><h2>不用先登录系统，也能先判断这套平台是不是你们学校要找的方向</h2><p>所有答案只使用当前代码、真实界面和产品事实库能支持的口径；没有客户案例就不编客户墙，没有认证就不挂认证徽章。</p></div>
          <div class="yk-faq-list"><details v-for="item in faqs" :key="item.q"><summary>{{ item.q }}</summary><p>{{ item.a }}</p></details></div>
        </div>
      </section>

      <section id="access" class="yk-section yk-access-section yk-access-secondary">
        <div class="yk-shell">
          <div class="yk-section-heading yk-access-heading"><p class="yk-kicker">已经是系统用户？</p><h2>正式业务入口继续保留，但不抢官网产品介绍的主线</h2></div>
          <div class="yk-access-grid yk-access-grid-three">
            <a v-if="teacherLoginUrl" :href="teacherLoginUrl" class="yk-access-card yk-access-primary"><span>教师 / 管理人员</span><strong>进入教师与管理工作台</strong><small>教务、学工、毕设、实习、审批、风险与管理工作</small><b aria-hidden="true">→</b></a>
            <a v-if="studentLoginUrl" :href="studentLoginUrl" class="yk-access-card"><span>学生</span><strong>进入学生门户</strong><small>查看待办、提交材料、查询进度与个人结果</small><b aria-hidden="true">→</b></a>
            <a v-if="enterpriseLoginUrl" :href="enterpriseLoginUrl" class="yk-access-card"><span>企业协同</span><strong>企业注册 / 登录</strong><small>岗位、实习协同与评价；首次注册由学校邀请激活</small><b aria-hidden="true">→</b></a>
          </div>
        </div>
      </section>

      <section id="contact" class="yk-final-cta"><div class="yk-shell yk-final-inner"><p class="yk-final-kicker">湖南跃科信息工程有限公司</p><h2>想看看这些能力怎么落到你们学校？</h2><p>可以从一条最难推进的真实业务流程开始沟通，不需要先把所有模块都选一遍。</p><div class="yk-final-actions"><router-link class="yk-button yk-button-light" to="/contact">预约产品演示</router-link><a class="yk-button yk-button-ghost" :href="contact.phoneHref">拨打 {{ contact.phone }}</a></div></div></section>
    </main>

    <footer class="yk-footer"><div class="yk-shell yk-footer-inner"><div><strong>{{ companyName }}</strong><span>职业院校学生全生命周期数字化平台</span></div><div class="yk-footer-links"><a :href="contact.phoneHref">{{ contact.phone }}</a><a v-for="item in footerLinks" :key="item.label" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.label }}</a><a v-if="icpNumber" :href="icpQueryUrl" target="_blank" rel="noopener noreferrer">{{ icpNumber }}</a><span>© {{ year }}</span></div></div></footer>

    <div v-if="modal" class="yk-modal-backdrop" role="presentation" @click.self="closeModal"><section class="yk-modal" role="dialog" aria-modal="true" :aria-label="modal.title"><button ref="modalClose" class="yk-modal-close" type="button" aria-label="关闭" @click="closeModal">×</button><h2>{{ modal.title }}</h2><ol v-if="modal.type === 'flow'" class="yk-flow-list"><li v-for="(step, index) in modal.steps" :key="`${index}-${step}`"><span>{{ index + 1 }}</span><p>{{ step }}</p></li></ol><div v-else-if="modal.type === 'qr'" class="yk-qr-modal"><img v-if="modal.qr && !qrBroken" :src="modal.qr" :alt="`${modal.title}二维码`" @error="onQrError" /><p v-else>二维码暂不可用，请使用学校正式发布入口。</p></div></section></div>
  </div>
</template>

<script>
import { API_BASE_URL, API_PREFIX } from '../services/http/config'
import { HELP_FLOWS } from '../config/helpContent'
import { OFFICIAL_PRODUCT_LIST } from '../config/officialProducts'
import { OFFICIAL_SITE_CONTACT } from '../config/officialSalesPages'
import { HOME_FAQS, HOME_PAIN_POINTS, IMPLEMENTATION_STEPS, LIFECYCLE_STAGES, PLATFORM_FOUNDATION, WORK_HUB_PROOFS } from '../config/officialWebsiteStory'
import { COMPANY_NAME, DEFAULT_PLATFORM_NAME, DEFAULT_PLATFORM_SUBTITLE, ENTERPRISE_LOGIN_URL, ICP_NUMBER, ICP_QUERY_URL, PORTAL_MODULES, PRIVACY_URL, STUDENT_LOGIN_URL, STUDENT_MINIPROGRAM_QR, SUPPORT_URL, TEACHER_LOGIN_URL, TEACHER_MINIPROGRAM_QR, TERMS_URL } from '../config/portalConfig'
import '../styles/official-site.css'
import '../styles/official-site-story.css'

const COVER_BY_PRODUCT = { 'academic-affairs': '/official-site/academic.webp', 'student-affairs': '/official-site/student-affairs-master.webp', graduation: '/official-site/graduation-overview.webp', internship: '/official-site/internship.webp' }
const PORTAL_BY_KEY = Object.fromEntries(PORTAL_MODULES.map((item) => [item.key, item]))

export default {
  name: 'PortalHomeView',
  data() {
    return {
      menuOpen: false, modal: null, qrBroken: false, lastFocused: null, brand: null,
      companyName: COMPANY_NAME, icpNumber: ICP_NUMBER, icpQueryUrl: ICP_QUERY_URL,
      teacherLoginUrl: TEACHER_LOGIN_URL, studentLoginUrl: STUDENT_LOGIN_URL, enterpriseLoginUrl: ENTERPRISE_LOGIN_URL,
      painPoints: HOME_PAIN_POINTS, lifecycleStages: LIFECYCLE_STAGES, workHubProofs: WORK_HUB_PROOFS,
      platformFoundation: PLATFORM_FOUNDATION, implementationSteps: IMPLEMENTATION_STEPS, faqs: HOME_FAQS,
      orientationSteps: ['预报到', '资格 / 材料', '绿色通道', '宿舍', '现场核验', '异常处理', '统计归档'],
      heroScreens: [
        { src: '/official-site/workbench.webp', label: '统一工作台', alt: '跃科统一工作台真实产品界面' },
        { src: '/official-site/internship.webp', label: '岗位实习', alt: '跃科岗位实习中心真实产品界面' },
        { src: '/official-site/academic.webp', label: '教务运行', alt: '跃科教务运行工作台真实产品界面' },
        { src: '/official-site/student-portal.webp', label: '学生门户', alt: '跃科学生服务门户真实产品界面' }
      ],
      mobileProofs: [
        { src: '/official-site/student-selection.webp', title: '学生移动端 · 网上选课', desc: '学生在移动端查看选课结果与状态，完成高频学业事项。', alt: '跃科学生移动端网上选课真实界面' },
        { src: '/official-site/teacher-graduation.webp', title: '教师移动端 · 毕设指导', desc: '教师查看毕业设计指导任务与过程事项，推进毕设业务。', alt: '跃科教师移动端毕业设计指导真实界面' },
        { src: '/official-site/teacher-taskbook.webp', title: '教师移动端 · 任务书', desc: '教师移动处理任务书相关工作，关键状态与 PC 业务链保持一致。', alt: '跃科教师移动端毕业设计任务书真实界面' }
      ]
    }
  },
  computed: {
    year() { return new Date().getFullYear() }, contact() { return OFFICIAL_SITE_CONTACT },
    platformName() { return (this.brand && this.brand.platformName) || DEFAULT_PLATFORM_NAME },
    platformSubtitle() { return (this.brand && this.brand.platformSubtitle) || DEFAULT_PLATFORM_SUBTITLE },
    products() { return OFFICIAL_PRODUCT_LIST.map((product) => { const portal = PORTAL_BY_KEY[product.key] || {}; return { ...product, cover: COVER_BY_PRODUCT[product.slug], coverAlt: `跃科${product.name}真实产品界面`, previewStages: product.workflow.slice(0, 4), flowId: portal.flowId, relationMap: product.relationMap || portal.relationshipMap } }) },
    miniPrograms() { return [{ key: 'teacher', name: '教师微信小程序', qr: TEACHER_MINIPROGRAM_QR }, { key: 'student', name: '学生微信小程序', qr: STUDENT_MINIPROGRAM_QR }] },
    hasAnyQr() { return this.miniPrograms.some((item) => !!item.qr) },
    footerLinks() { return [{ label: '隐私政策', url: PRIVACY_URL }, { label: '用户协议', url: TERMS_URL }, { label: '技术支持', url: SUPPORT_URL }].filter((item) => !!item.url) }
  },
  mounted() { document.title = `${this.platformName}｜职业院校学生全生命周期数字化平台`; this.loadBrand() },
  beforeUnmount() { document.body.style.overflow = '' },
  methods: {
    async loadBrand() { try { const res = await fetch(`${API_BASE_URL}${API_PREFIX}/authz/tenant/brand`, { headers: { Accept: 'application/json' } }); if (!res.ok) return; const payload = await res.json(); const data = payload && payload.data; if (data && typeof data === 'object') { this.brand = data; document.title = `${this.platformName}｜职业院校学生全生命周期数字化平台` } } catch { /* 公共首页品牌接口异常时使用默认品牌 */ } },
    openFlow(product) { const flow = HELP_FLOWS.find((item) => item.id === product.flowId); if (!flow) return; this.openModal({ type: 'flow', title: `${product.name} · ${flow.title}`, steps: flow.steps || [] }) },
    openQr(mp) { if (!mp.qr) return; this.qrBroken = false; this.openModal({ type: 'qr', title: mp.name, qr: mp.qr }) },
    openModal(payload) { this.lastFocused = document.activeElement; this.modal = payload; document.body.style.overflow = 'hidden'; this.$nextTick(() => { const el = this.$refs.modalClose; if (el && el.focus) el.focus() }) },
    closeModal() { this.modal = null; document.body.style.overflow = ''; const prev = this.lastFocused; if (prev && prev.focus) prev.focus(); this.lastFocused = null },
    onQrError() { this.qrBroken = true }
  }
}
</script>