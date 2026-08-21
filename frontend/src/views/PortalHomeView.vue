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
          <a href="#value">平台价值</a>
          <a href="#products">产品中心</a>
          <a href="#mobile">移动协同</a>
          <a href="#access">进入系统</a>
          <a v-if="supportContact" href="#contact">联系跃科</a>
        </nav>

        <a v-if="teacherLoginUrl" class="yk-nav-cta" :href="teacherLoginUrl">进入平台</a>

        <button
          class="yk-menu-button"
          type="button"
          :aria-expanded="menuOpen ? 'true' : 'false'"
          aria-label="打开导航菜单"
          @click="menuOpen = !menuOpen"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M4 7h16M4 12h16M4 17h16" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" />
          </svg>
        </button>
      </div>

      <div v-if="menuOpen" class="yk-mobile-nav yk-shell">
        <a href="#value" @click="menuOpen = false">平台价值</a>
        <a href="#products" @click="menuOpen = false">产品中心</a>
        <a href="#mobile" @click="menuOpen = false">移动协同</a>
        <a href="#access" @click="menuOpen = false">进入系统</a>
        <a v-if="supportContact" href="#contact" @click="menuOpen = false">联系跃科</a>
      </div>
    </header>

    <main id="top">
      <section class="yk-hero" aria-labelledby="hero-title">
        <div class="yk-shell yk-hero-inner">
          <p class="yk-kicker">面向职业院校的数字化业务平台</p>
          <h1 id="hero-title">让学生全生命周期的关键业务，<br class="yk-desktop-break" />在一套平台里协同运行</h1>
          <p class="yk-hero-lead">
            从迎新、在校管理、教学运行，到岗位实习、毕业设计与就业衔接，
            把流程、待办、风险与业务证据汇聚为可执行、可追踪、可审计的闭环。
          </p>
          <div class="yk-hero-actions">
            <a v-if="teacherLoginUrl" class="yk-button yk-button-primary" :href="teacherLoginUrl">
              进入教师 / 管理工作台
              <span aria-hidden="true">→</span>
            </a>
            <a class="yk-button yk-button-ghost" href="#products">了解产品中心</a>
          </div>

          <div class="yk-product-stage" aria-label="跃科真实产品界面">
            <div class="yk-stage-head">
              <div>
                <strong>真实产品界面</strong>
                <span>统一工作台 · 岗位实习 · 教务运行 · 学生门户</span>
              </div>
              <span class="yk-stage-note">流程 · 待办 · 风险 · 多端入口</span>
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

      <section id="value" class="yk-section yk-value-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">不是模块堆砌，而是一条可协同的学生业务主线</p>
            <h2>围绕学生生命周期，连接每一次关键办理</h2>
            <p>
              学生、教师、辅导员、教务与学校管理者在同一业务事实下协作，
              减少多系统切换、重复核对与过程断点。
            </p>
          </div>

          <div class="yk-value-grid">
            <article v-for="item in platformFeatures" :key="item.title" class="yk-value-card">
              <span class="yk-icon-tile" aria-hidden="true">
                <svg viewBox="0 0 24 24">
                  <path d="m12 3 7 4-7 4-7-4 7-4Zm-7 8 7 4 7-4M5 15l7 4 7-4" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </span>
              <h3>{{ item.title }}</h3>
              <p>{{ item.desc }}</p>
            </article>
          </div>
        </div>
      </section>

      <section id="products" class="yk-section yk-products-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">重点业务中心</p>
            <h2>让高频业务从分散办理，走向统一闭环</h2>
            <p>围绕学校真实业务场景组织产品能力，让老师进入页面就知道当前要做什么、风险在哪里、下一步往哪里走。</p>
          </div>

          <div class="yk-product-grid">
            <article v-for="mod in modules" :key="mod.key" class="yk-product-card">
              <div class="yk-product-card-top">
                <span class="yk-product-mark" :style="{ color: mod.color, background: mod.soft }">{{ mod.mark }}</span>
                <span class="yk-product-index">0{{ modules.indexOf(mod) + 1 }}</span>
              </div>
              <h3>{{ mod.name }}</h3>
              <p>{{ mod.desc }}</p>
              <ul>
                <li v-for="stage in mod.stages" :key="stage">{{ stage }}</li>
              </ul>
              <div class="yk-product-links">
                <button type="button" @click="openFlow(mod)">查看业务流程</button>
                <a v-if="mod.relationshipMap" :href="mod.relationshipMap" target="_blank" rel="noopener noreferrer">关系图</a>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section id="mobile" class="yk-section yk-mobile-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">多端协同，而非简单缩小后台</p>
            <h2>让学生与教师在移动端完成高频任务</h2>
            <p>
              学生可查看与办理学业事项；教师可在移动端完成指导、批阅与任务处理，
              关键业务与学校管理端保持同一流程和业务事实。
            </p>
          </div>

          <div class="yk-mobile-proof-grid">
            <article v-for="proof in mobileProofs" :key="proof.src" class="yk-mobile-proof">
              <div class="yk-phone-canvas">
                <img :src="proof.src" :alt="proof.alt" loading="lazy" decoding="async" />
              </div>
              <h3>{{ proof.title }}</h3>
              <p>{{ proof.desc }}</p>
            </article>
          </div>

          <div v-if="hasAnyQr" class="yk-qr-row">
            <template v-for="mp in miniPrograms" :key="mp.key">
              <button v-if="mp.qr" type="button" @click="openQr(mp)">查看{{ mp.name }}码</button>
            </template>
          </div>
        </div>
      </section>

      <section id="access" class="yk-section yk-access-section">
        <div class="yk-shell yk-access-wrap">
          <div class="yk-access-copy">
            <p class="yk-kicker">统一入口，按身份进入</p>
            <h2>一个平台入口，连接学校不同角色的工作</h2>
            <p>入口地址由部署配置统一管理；未配置的入口自动隐藏或禁用，不展示虚假地址。</p>
          </div>

          <div class="yk-access-grid">
            <a v-if="teacherLoginUrl" :href="teacherLoginUrl" class="yk-access-card yk-access-primary">
              <span>教师 / 管理人员</span>
              <strong>进入工作台</strong>
              <small>审批、业务办理、风险处置与管理工作</small>
              <b aria-hidden="true">→</b>
            </a>
            <a v-if="studentLoginUrl" :href="studentLoginUrl" class="yk-access-card">
              <span>学生</span>
              <strong>进入学生门户</strong>
              <small>查看待办、提交材料、查询进度与结果</small>
              <b aria-hidden="true">→</b>
            </a>
            <a v-if="enterpriseLoginUrl" :href="enterpriseLoginUrl" class="yk-access-card">
              <span>企业协同</span>
              <strong>进入企业端</strong>
              <small>岗位、协同、评价与实习业务衔接</small>
              <b aria-hidden="true">→</b>
            </a>
          </div>
        </div>
      </section>

      <section id="contact" class="yk-final-cta">
        <div class="yk-shell yk-final-inner">
          <p class="yk-final-kicker">从一条更清晰的数字化业务主线开始</p>
          <h2>让学校的关键业务真正连起来、跑起来、留得下来</h2>
          <p>
            跃科围绕职业院校学生全生命周期建设可落地、可维护的数字化业务平台，
            支持按学校现有场景逐步接入与协同运行。
          </p>
          <div class="yk-final-actions">
            <a v-if="teacherLoginUrl" class="yk-button yk-button-light" :href="teacherLoginUrl">进入平台</a>
            <span v-if="supportContact" class="yk-contact-text">商务 / 技术联系：{{ supportContact }}</span>
          </div>
        </div>
      </section>
    </main>

    <footer class="yk-footer">
      <div class="yk-shell yk-footer-inner">
        <div>
          <strong>{{ companyName }}</strong>
          <span>职业院校学生全生命周期数字化平台</span>
        </div>
        <div class="yk-footer-links">
          <a v-for="item in footerLinks" :key="item.label" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.label }}</a>
          <a v-if="icpNumber" :href="icpQueryUrl" target="_blank" rel="noopener noreferrer">{{ icpNumber }}</a>
          <span>© {{ year }}</span>
        </div>
      </div>
    </footer>

    <div v-if="modal" class="yk-modal-backdrop" role="presentation" @click.self="closeModal">
      <section class="yk-modal" role="dialog" aria-modal="true" :aria-label="modal.title">
        <button ref="modalClose" class="yk-modal-close" type="button" aria-label="关闭" @click="closeModal">×</button>
        <h2>{{ modal.title }}</h2>

        <ol v-if="modal.type === 'flow'" class="yk-flow-list">
          <li v-for="(step, index) in modal.steps" :key="`${index}-${step}`">
            <span>{{ index + 1 }}</span>
            <p>{{ step }}</p>
          </li>
        </ol>

        <div v-else-if="modal.type === 'qr'" class="yk-qr-modal">
          <img v-if="modal.qr && !qrBroken" :src="modal.qr" :alt="`${modal.title}二维码`" @error="onQrError" />
          <p v-else>二维码暂不可用，请使用学校正式发布入口。</p>
        </div>
      </section>
    </div>
  </div>
</template>

<script>
import { API_BASE_URL, API_PREFIX } from '../services/http/config'
import { HELP_FLOWS } from '../config/helpContent'
import {
  COMPANY_NAME,
  DEFAULT_PLATFORM_NAME,
  DEFAULT_PLATFORM_SUBTITLE,
  ENTERPRISE_LOGIN_URL,
  ICP_NUMBER,
  ICP_QUERY_URL,
  PORTAL_MODULES,
  PRIVACY_URL,
  STATUS_PAGE_URL,
  STUDENT_LOGIN_URL,
  STUDENT_MINIPROGRAM_QR,
  SUPPORT_CONTACT,
  SUPPORT_URL,
  TEACHER_LOGIN_URL,
  TEACHER_MINIPROGRAM_QR,
  TERMS_URL
} from '../config/portalConfig'

export default {
  name: 'PortalHomeView',
  data() {
    return {
      menuOpen: false,
      modal: null,
      qrBroken: false,
      lastFocused: null,
      brand: null,
      companyName: COMPANY_NAME,
      icpNumber: ICP_NUMBER,
      icpQueryUrl: ICP_QUERY_URL,
      modules: PORTAL_MODULES,
      statusPageUrl: STATUS_PAGE_URL,
      supportContact: SUPPORT_CONTACT,
      teacherLoginUrl: TEACHER_LOGIN_URL,
      studentLoginUrl: STUDENT_LOGIN_URL,
      enterpriseLoginUrl: ENTERPRISE_LOGIN_URL,
      heroScreens: [
        { src: '/official-site/workbench.webp', label: '统一工作台', alt: '跃科统一工作台真实产品界面' },
        { src: '/official-site/internship.webp', label: '岗位实习', alt: '跃科岗位实习中心真实产品界面' },
        { src: '/official-site/academic.webp', label: '教务运行', alt: '跃科教务运行工作台真实产品界面' },
        { src: '/official-site/student-portal.webp', label: '学生门户', alt: '跃科学生服务门户真实产品界面' }
      ],
      platformFeatures: [
        { title: '统一业务入口', desc: '工作台、审批、消息与业务待办统一组织，减少多系统来回切换。' },
        { title: '流程可追踪', desc: '关键节点有留痕、有责任人、有过程记录，便于持续跟进。' },
        { title: '风险可处置', desc: '把业务异常转化为可执行待办，推进闭环处置与后续跟进。' },
        { title: '多端协同', desc: '管理 PC、教师工作台与学生移动端围绕同一业务流程协同办理。' }
      ],
      mobileProofs: [
        {
          src: '/official-site/student-selection.webp',
          title: '学生端 · 网上选课',
          desc: '学生在移动端查看选课结果与状态，完成高频学业事项。',
          alt: '跃科学生移动端网上选课真实界面'
        },
        {
          src: '/official-site/teacher-graduation.webp',
          title: '教师端 · 毕业设计指导',
          desc: '教师在移动端查看指导任务与过程事项，推进毕设业务。',
          alt: '跃科教师移动端毕业设计指导真实界面'
        },
        {
          src: '/official-site/teacher-taskbook.webp',
          title: '教师端 · 毕设任务书',
          desc: '教师移动处理任务书相关工作，关键状态与业务链保持一致。',
          alt: '跃科教师移动端毕业设计任务书真实界面'
        }
      ]
    }
  },
  computed: {
    year() {
      return new Date().getFullYear()
    },
    platformName() {
      return (this.brand && this.brand.platformName) || DEFAULT_PLATFORM_NAME
    },
    platformSubtitle() {
      return (this.brand && this.brand.platformSubtitle) || DEFAULT_PLATFORM_SUBTITLE
    },
    miniPrograms() {
      return [
        { key: 'teacher', name: '教师微信小程序', qr: TEACHER_MINIPROGRAM_QR },
        { key: 'student', name: '学生微信小程序', qr: STUDENT_MINIPROGRAM_QR }
      ]
    },
    hasAnyQr() {
      return this.miniPrograms.some((item) => !!item.qr)
    },
    footerLinks() {
      return [
        { label: '隐私政策', url: PRIVACY_URL },
        { label: '用户协议', url: TERMS_URL },
        { label: '技术支持', url: SUPPORT_URL }
      ].filter((item) => !!item.url)
    }
  },
  mounted() {
    document.title = `${this.platformName}｜职业院校学生全生命周期数字化平台`
    this.loadBrand()
  },
  beforeUnmount() {
    document.body.style.overflow = ''
  },
  methods: {
    async loadBrand() {
      try {
        const res = await fetch(`${API_BASE_URL}${API_PREFIX}/authz/tenant/brand`, {
          headers: { Accept: 'application/json' }
        })
        if (!res.ok) return
        const payload = await res.json()
        const data = payload && payload.data
        if (data && typeof data === 'object') {
          this.brand = data
          document.title = `${this.platformName}｜职业院校学生全生命周期数字化平台`
        }
      } catch {
        // 公共首页必须可独立渲染；品牌接口异常时使用默认品牌。
      }
    },
    flowOf(flowId) {
      return HELP_FLOWS.find((flow) => flow.id === flowId) || null
    },
    openFlow(mod) {
      const flow = this.flowOf(mod.flowId)
      if (!flow) return
      this.openModal({
        type: 'flow',
        title: `${mod.name} · ${flow.title}`,
        steps: flow.steps || []
      })
    },
    openQr(mp) {
      if (!mp.qr) return
      this.qrBroken = false
      this.openModal({ type: 'qr', title: mp.name, qr: mp.qr })
    },
    openModal(payload) {
      this.lastFocused = document.activeElement
      this.modal = payload
      document.body.style.overflow = 'hidden'
      this.$nextTick(() => {
        const el = this.$refs.modalClose
        if (el && el.focus) el.focus()
      })
    },
    closeModal() {
      this.modal = null
      document.body.style.overflow = ''
      const prev = this.lastFocused
      if (prev && prev.focus) prev.focus()
      this.lastFocused = null
    },
    onQrError() {
      this.qrBroken = true
    }
  }
}
</script>

<style scoped>
.yk-site {
  --yk-ink: #10213d;
  --yk-muted: #5d6d86;
  --yk-blue: #1667e8;
  --yk-blue-dark: #0f56cc;
  --yk-blue-soft: #eef5ff;
  --yk-line: #dbe7f7;
  --yk-dark: #10213d;
  --yk-white: #ffffff;
  min-height: 100vh;
  color: var(--yk-ink);
  background: var(--yk-white);
  font-family: 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
  -webkit-font-smoothing: antialiased;
  overflow-x: hidden;
}

.yk-site *, .yk-site *::before, .yk-site *::after { box-sizing: border-box; }
.yk-site a { color: inherit; text-decoration: none; }
.yk-site button { font: inherit; }
.yk-site :focus-visible { outline: 2px solid var(--yk-blue); outline-offset: 3px; border-radius: 8px; }
.yk-shell { width: min(1200px, calc(100% - 48px)); margin: 0 auto; }

.yk-header {
  position: sticky;
  top: 0;
  z-index: 30;
  background: rgba(255, 255, 255, 0.95);
  border-bottom: 1px solid rgba(219, 231, 247, 0.75);
  backdrop-filter: blur(14px);
}
.yk-nav { height: 68px; display: flex; align-items: center; gap: 28px; }
.yk-brand { min-width: 0; display: flex; align-items: center; gap: 10px; margin-right: auto; }
.yk-brand-dot {
  width: 30px; height: 30px; display: grid; place-items: center; flex: 0 0 auto;
  border-radius: 9px; background: var(--yk-blue); color: #fff; font-size: 14px; font-weight: 800;
}
.yk-brand-copy { min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.yk-brand-copy strong { max-width: 320px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 15px; line-height: 1.2; }
.yk-brand-copy small { color: var(--yk-muted); font-size: 10px; line-height: 1.2; }
.yk-nav-links { display: flex; align-items: center; gap: 28px; }
.yk-nav-links a { color: var(--yk-muted); font-size: 14px; font-weight: 500; transition: color .18s ease; }
.yk-nav-links a:hover { color: var(--yk-ink); }
.yk-nav-cta {
  min-height: 38px; display: inline-flex; align-items: center; justify-content: center;
  padding: 0 17px; border-radius: 10px; background: var(--yk-blue); color: #fff !important;
  font-size: 13px; font-weight: 700; transition: transform .18s ease, background .18s ease;
}
.yk-nav-cta:hover { background: var(--yk-blue-dark); transform: translateY(-1px); }
.yk-menu-button { display: none; width: 40px; height: 40px; border: 0; background: transparent; color: var(--yk-ink); cursor: pointer; }
.yk-menu-button svg { width: 22px; height: 22px; }
.yk-mobile-nav { display: none; }

.yk-hero { background: linear-gradient(180deg, #f6f9ff 0%, #eef5ff 100%); }
.yk-hero-inner { padding: 78px 48px 72px; text-align: center; }
.yk-kicker {
  margin: 0 0 16px; color: var(--yk-blue); font-size: 14px; font-weight: 700;
  line-height: 1.3; letter-spacing: .08em;
}
.yk-hero h1 {
  max-width: 820px; margin: 0 auto; color: var(--yk-ink); font-size: clamp(40px, 5vw, 56px);
  font-weight: 700; line-height: 1.12; letter-spacing: -2px;
}
.yk-hero-lead {
  max-width: 790px; margin: 20px auto 0; color: var(--yk-muted); font-size: 17px;
  line-height: 1.75; letter-spacing: -.02em;
}
.yk-hero-actions { margin-top: 26px; display: flex; justify-content: center; align-items: center; gap: 12px; flex-wrap: wrap; }
.yk-button {
  min-height: 44px; display: inline-flex; align-items: center; justify-content: center; gap: 10px;
  padding: 0 20px; border-radius: 10px; font-size: 14px; font-weight: 700;
  transition: transform .18s ease, box-shadow .18s ease, background .18s ease;
}
.yk-button:hover { transform: translateY(-1px); }
.yk-button-primary { color: #fff !important; background: var(--yk-blue); box-shadow: 0 8px 24px rgba(22, 103, 232, .18); }
.yk-button-primary:hover { background: var(--yk-blue-dark); }
.yk-button-ghost { color: var(--yk-ink); background: #fff; border: 1px solid var(--yk-line); }
.yk-button-light { color: var(--yk-ink) !important; background: #fff; box-shadow: 0 10px 30px rgba(0, 0, 0, .12); }

.yk-product-stage {
  margin: 56px auto 0; padding: 18px; text-align: left; border-radius: 16px;
  background: rgba(255, 255, 255, .92); border: 1px solid rgba(196, 213, 238, .95);
  box-shadow: 0 28px 70px rgba(35, 70, 120, .13);
}
.yk-stage-head { display: flex; align-items: center; justify-content: space-between; gap: 20px; padding: 0 2px 14px; }
.yk-stage-head > div { display: flex; align-items: baseline; gap: 12px; flex-wrap: wrap; }
.yk-stage-head strong { font-size: 13px; }
.yk-stage-head span { color: var(--yk-muted); font-size: 11px; }
.yk-stage-note { white-space: nowrap; }
.yk-shot-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
.yk-shot { margin: 0; overflow: hidden; border-radius: 11px; background: #f5f8fc; border: 1px solid #e4edf8; }
.yk-shot img { width: 100%; aspect-ratio: 3 / 2; display: block; object-fit: cover; object-position: top center; }
.yk-shot figcaption { padding: 8px 11px 9px; color: var(--yk-muted); font-size: 11px; font-weight: 600; }

.yk-section { padding: 92px 0; }
.yk-section-heading { max-width: 820px; margin: 0 auto 42px; text-align: center; }
.yk-section-heading .yk-kicker { margin-bottom: 13px; font-size: 13px; }
.yk-section-heading h2 {
  margin: 0; color: var(--yk-ink); font-size: clamp(30px, 3.4vw, 36px); font-weight: 700;
  line-height: 1.2; letter-spacing: -1px;
}
.yk-section-heading > p:last-child { max-width: 760px; margin: 14px auto 0; color: var(--yk-muted); font-size: 15px; line-height: 1.8; }

.yk-value-section { background: #fff; }
.yk-value-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px; }
.yk-value-card { min-height: 190px; padding: 24px; border: 1px solid var(--yk-line); border-radius: 14px; background: #fff; }
.yk-icon-tile {
  width: 36px; height: 36px; display: grid; place-items: center; border-radius: 10px;
  color: var(--yk-blue); background: #edf5ff;
}
.yk-icon-tile svg { width: 18px; height: 18px; }
.yk-value-card h3 { margin: 18px 0 8px; font-size: 16px; line-height: 1.35; }
.yk-value-card p { margin: 0; color: var(--yk-muted); font-size: 13px; line-height: 1.75; }

.yk-products-section { background: var(--yk-blue-soft); }
.yk-product-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 18px; }
.yk-product-card { padding: 30px; border-radius: 14px; border: 1px solid #dce8f7; background: #fff; }
.yk-product-card-top { display: flex; align-items: center; justify-content: space-between; }
.yk-product-mark { width: 42px; height: 42px; display: grid; place-items: center; border-radius: 12px; font-size: 16px; font-weight: 800; }
.yk-product-index { color: #a7b5c8; font-size: 12px; font-weight: 700; letter-spacing: .12em; }
.yk-product-card h3 { margin: 22px 0 10px; font-size: 20px; line-height: 1.35; }
.yk-product-card > p { min-height: 50px; margin: 0; color: var(--yk-muted); font-size: 14px; line-height: 1.8; }
.yk-product-card ul { display: flex; gap: 7px; flex-wrap: wrap; margin: 20px 0 0; padding: 0; list-style: none; }
.yk-product-card li { padding: 6px 10px; border-radius: 999px; color: #4d607b; background: #f5f8fc; font-size: 11px; font-weight: 600; }
.yk-product-links { margin-top: 24px; display: flex; align-items: center; gap: 16px; }
.yk-product-links button, .yk-product-links a { padding: 0; border: 0; background: transparent; color: var(--yk-blue); font-size: 12px; font-weight: 700; cursor: pointer; }
.yk-product-links a { color: var(--yk-muted); }

.yk-mobile-section { background: #fff; }
.yk-mobile-proof-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 22px; }
.yk-mobile-proof { text-align: center; }
.yk-phone-canvas {
  min-height: 610px; display: flex; align-items: flex-start; justify-content: center; padding: 24px 18px 0;
  overflow: hidden; border-radius: 16px; background: #f3f7fc; border: 1px solid #e1eaf6;
}
.yk-phone-canvas img { width: min(100%, 280px); height: auto; display: block; border-radius: 16px 16px 0 0; box-shadow: 0 14px 34px rgba(21, 51, 92, .11); }
.yk-mobile-proof h3 { margin: 18px 0 7px; font-size: 14px; }
.yk-mobile-proof p { max-width: 300px; margin: 0 auto; color: var(--yk-muted); font-size: 12px; line-height: 1.7; }
.yk-qr-row { margin-top: 28px; display: flex; justify-content: center; gap: 10px; flex-wrap: wrap; }
.yk-qr-row button { padding: 9px 14px; border: 1px solid var(--yk-line); border-radius: 9px; color: var(--yk-ink); background: #fff; cursor: pointer; }

.yk-access-section { padding-top: 72px; background: #f8fbff; border-top: 1px solid #edf2f9; }
.yk-access-wrap { display: grid; grid-template-columns: minmax(260px, .8fr) minmax(0, 1.5fr); gap: 54px; align-items: center; }
.yk-access-copy .yk-kicker { margin-bottom: 12px; }
.yk-access-copy h2 { margin: 0; font-size: clamp(28px, 3vw, 36px); line-height: 1.22; letter-spacing: -1px; }
.yk-access-copy > p:last-child { margin: 14px 0 0; color: var(--yk-muted); font-size: 14px; line-height: 1.8; }
.yk-access-grid { display: grid; gap: 12px; }
.yk-access-card {
  position: relative; display: grid; grid-template-columns: 120px 1fr; gap: 4px 18px; padding: 19px 52px 19px 20px;
  border: 1px solid var(--yk-line); border-radius: 13px; background: #fff; transition: transform .18s ease, box-shadow .18s ease;
}
.yk-access-card:hover { transform: translateY(-1px); box-shadow: 0 12px 28px rgba(41, 73, 116, .08); }
.yk-access-card > span { grid-row: 1 / span 2; align-self: center; color: var(--yk-muted); font-size: 12px; font-weight: 700; }
.yk-access-card strong { font-size: 15px; }
.yk-access-card small { color: var(--yk-muted); font-size: 11px; }
.yk-access-card b { position: absolute; right: 20px; top: 50%; transform: translateY(-50%); color: var(--yk-blue); font-size: 20px; }
.yk-access-primary { border-color: #bad3fa; }

.yk-final-cta { background: var(--yk-dark); color: #fff; }
.yk-final-inner { padding: 88px 48px 84px; text-align: center; }
.yk-final-kicker { margin: 0 0 16px; color: #7eb2ff; font-size: 13px; font-weight: 700; letter-spacing: .08em; }
.yk-final-inner h2 { max-width: 920px; margin: 0 auto; font-size: clamp(32px, 4vw, 42px); line-height: 1.18; letter-spacing: -1px; }
.yk-final-inner > p:not(.yk-final-kicker) { max-width: 760px; margin: 18px auto 0; color: #b9c7d9; font-size: 14px; line-height: 1.8; }
.yk-final-actions { margin-top: 26px; display: flex; align-items: center; justify-content: center; gap: 18px; flex-wrap: wrap; }
.yk-contact-text { color: #dbe6f5; font-size: 13px; }

.yk-footer { color: #dce6f3; background: #0b1930; border-top: 1px solid rgba(255, 255, 255, .08); }
.yk-footer-inner { min-height: 92px; display: flex; align-items: center; justify-content: space-between; gap: 28px; }
.yk-footer-inner > div:first-child { display: flex; flex-direction: column; gap: 5px; }
.yk-footer strong { font-size: 12px; }
.yk-footer span, .yk-footer a { color: #96a7bd; font-size: 10px; }
.yk-footer-links { display: flex; align-items: center; justify-content: flex-end; gap: 16px; flex-wrap: wrap; }
.yk-footer a:hover { color: #fff; }

.yk-modal-backdrop { position: fixed; inset: 0; z-index: 80; display: grid; place-items: center; padding: 22px; background: rgba(8, 20, 39, .58); backdrop-filter: blur(6px); }
.yk-modal { position: relative; width: min(600px, 100%); max-height: min(760px, 88vh); overflow: auto; padding: 30px; border-radius: 18px; background: #fff; box-shadow: 0 30px 80px rgba(0, 0, 0, .25); }
.yk-modal h2 { margin: 0 44px 24px 0; font-size: 22px; }
.yk-modal-close { position: absolute; top: 18px; right: 18px; width: 36px; height: 36px; border: 0; border-radius: 10px; color: var(--yk-muted); background: #f3f6fa; font-size: 22px; cursor: pointer; }
.yk-flow-list { display: grid; gap: 12px; margin: 0; padding: 0; list-style: none; }
.yk-flow-list li { display: grid; grid-template-columns: 32px 1fr; gap: 12px; align-items: start; padding: 14px; border: 1px solid var(--yk-line); border-radius: 12px; }
.yk-flow-list li > span { width: 32px; height: 32px; display: grid; place-items: center; border-radius: 9px; color: var(--yk-blue); background: var(--yk-blue-soft); font-weight: 800; font-size: 12px; }
.yk-flow-list p { margin: 5px 0 0; color: var(--yk-muted); font-size: 13px; line-height: 1.7; }
.yk-qr-modal { text-align: center; }
.yk-qr-modal img { width: min(280px, 76vw); height: auto; }
.yk-qr-modal p { color: var(--yk-muted); }

@media (max-width: 900px) {
  .yk-shell { width: min(100% - 32px, 720px); }
  .yk-nav { height: 60px; }
  .yk-brand-copy small, .yk-nav-links, .yk-nav-cta { display: none; }
  .yk-brand-copy strong { max-width: 250px; font-size: 12px; }
  .yk-brand-dot { width: 26px; height: 26px; border-radius: 8px; font-size: 12px; }
  .yk-menu-button { display: grid; place-items: center; }
  .yk-mobile-nav { display: grid; padding: 0 0 12px; }
  .yk-mobile-nav a { padding: 11px 2px; border-top: 1px solid #edf2f8; color: var(--yk-muted); font-size: 13px; }

  .yk-hero-inner { padding: 54px 8px 46px; }
  .yk-hero h1 { font-size: clamp(34px, 8.7vw, 44px); letter-spacing: -1.4px; }
  .yk-hero-lead { font-size: 14px; line-height: 1.72; }
  .yk-desktop-break { display: none; }
  .yk-product-stage { margin-top: 38px; padding: 9px; border-radius: 13px; }
  .yk-stage-head { padding: 2px 2px 9px; }
  .yk-stage-note { display: none; }
  .yk-shot-grid { gap: 6px; }
  .yk-shot { border-radius: 8px; }
  .yk-shot figcaption { display: none; }

  .yk-section { padding: 66px 0; }
  .yk-section-heading { margin-bottom: 30px; }
  .yk-section-heading h2 { font-size: clamp(27px, 7vw, 34px); }
  .yk-value-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .yk-product-grid { grid-template-columns: 1fr; }
  .yk-mobile-proof-grid { grid-template-columns: 1fr; gap: 26px; }
  .yk-phone-canvas { min-height: auto; padding-top: 20px; }
  .yk-phone-canvas img { width: min(100%, 310px); }
  .yk-access-wrap { grid-template-columns: 1fr; gap: 28px; }
  .yk-access-copy { text-align: center; }
  .yk-final-inner { padding: 68px 14px 64px; }
  .yk-footer-inner { min-height: 120px; flex-direction: column; justify-content: center; text-align: center; }
  .yk-footer-links { justify-content: center; }
}

@media (max-width: 560px) {
  .yk-shell { width: min(100% - 24px, 480px); }
  .yk-hero-inner { padding-top: 44px; }
  .yk-kicker { margin-bottom: 12px; font-size: 11px; letter-spacing: .05em; }
  .yk-hero h1 { font-size: 30px; line-height: 1.16; letter-spacing: -1px; }
  .yk-hero-lead { margin-top: 14px; font-size: 13px; }
  .yk-hero-actions { margin-top: 20px; }
  .yk-button { width: 100%; min-height: 42px; font-size: 13px; }
  .yk-product-stage { margin-top: 30px; }
  .yk-stage-head > div { gap: 6px; }
  .yk-stage-head strong { font-size: 10px; }
  .yk-stage-head span { font-size: 8px; }

  .yk-section { padding: 56px 0; }
  .yk-section-heading { margin-bottom: 25px; }
  .yk-section-heading .yk-kicker { font-size: 10px; }
  .yk-section-heading h2 { font-size: 26px; line-height: 1.22; letter-spacing: -.7px; }
  .yk-section-heading > p:last-child { margin-top: 11px; font-size: 12px; line-height: 1.72; }
  .yk-value-grid { grid-template-columns: 1fr; gap: 10px; }
  .yk-value-card { min-height: 0; padding: 20px; }
  .yk-value-card h3 { margin-top: 14px; }
  .yk-product-card { padding: 22px; }
  .yk-product-card > p { min-height: 0; font-size: 12px; }
  .yk-mobile-proof h3 { margin-top: 14px; }
  .yk-access-card { grid-template-columns: 1fr; padding: 18px 42px 18px 18px; }
  .yk-access-card > span { grid-row: auto; }
  .yk-access-card small { margin-top: 2px; line-height: 1.5; }
  .yk-final-inner h2 { font-size: 28px; }
  .yk-final-inner > p:not(.yk-final-kicker) { font-size: 12px; }
  .yk-contact-text { font-size: 11px; }
  .yk-footer-links { gap: 10px 14px; }
}

@media (prefers-reduced-motion: reduce) {
  .yk-site *, .yk-site *::before, .yk-site *::after { scroll-behavior: auto !important; transition: none !important; animation: none !important; }
}
</style>
