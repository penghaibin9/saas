<template>
  <div class="yk-site yk-story-site yk-home-site">
    <header class="yk-header">
      <div class="yk-shell yk-nav">
        <a class="yk-brand" href="#top" aria-label="返回首页">
          <span class="yk-brand-dot" aria-hidden="true">跃</span>
          <span class="yk-brand-copy">
            <strong>跃科</strong>
            <small>职业院校学生全生命周期平台</small>
          </span>
        </a>

        <nav class="yk-nav-links" aria-label="官网导航">
          <a href="#lifecycle">学生生命周期</a>
          <a href="#products">核心产品</a>
          <a href="#platform">平台能力</a>
          <a href="#delivery">部署交付</a>
        </nav>

        <div class="yk-nav-actions">
          <a class="yk-nav-login" href="#login">登录系统</a>
          <router-link class="yk-nav-cta" to="/contact">预约产品演示</router-link>
        </div>

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
        <a href="#login" @click="menuOpen = false">登录系统</a>
        <a href="#lifecycle" @click="menuOpen = false">学生生命周期</a>
        <a href="#products" @click="menuOpen = false">核心产品</a>
        <a href="#platform" @click="menuOpen = false">平台能力</a>
        <a href="#delivery" @click="menuOpen = false">部署交付</a>
        <router-link to="/contact" @click="menuOpen = false">预约产品演示</router-link>
      </div>
    </header>

    <main id="top">
      <section class="yk-hero yk-home-hero" aria-labelledby="hero-title">
        <div class="yk-shell yk-home-hero-inner">
          <div class="yk-home-hero-grid">
            <div class="yk-home-hero-copy">
              <p class="yk-kicker">面向职业院校的学生全生命周期数字化平台</p>
              <h1 id="hero-title">把学生从入校到就业，连成一条业务主线</h1>
              <p class="yk-hero-lead">
                统一学生、组织、流程和业务状态，让教务、学工、实习、毕设与学生服务不再各自为战。
              </p>
              <div class="yk-hero-actions">
                <router-link class="yk-button yk-button-primary" to="/contact">预约产品演示</router-link>
                <a class="yk-button yk-button-ghost" href="#products">查看核心产品</a>
              </div>
              <ul class="yk-home-value-points" aria-label="平台价值">
                <li><strong>同一条业务线</strong><span>过程持续推进</span></li>
                <li><strong>同一个工作入口</strong><span>待办风险集中处理</span></li>
                <li><strong>同一套治理底座</strong><span>身份权限统一管理</span></li>
              </ul>
            </div>

            <figure class="yk-home-hero-proof">
              <div class="yk-home-proof-label"><span>跃科统一工作台</span><strong>产品运行界面</strong></div>
              <img src="/official-site/workbench.webp" alt="跃科统一工作台产品界面" decoding="async" />
            </figure>
          </div>

          <section id="login" class="yk-login-panel" aria-labelledby="login-title">
            <div class="yk-login-intro">
              <span>系统入口</span>
              <h2 id="login-title">选择身份，直接进入系统</h2>
              <p>学校用户无需从产品介绍中寻找登录入口。</p>
            </div>
            <div class="yk-login-grid">
              <a v-if="teacherLoginUrl" :href="teacherLoginUrl" class="yk-login-card yk-login-card-primary">
                <span>教师 / 管理人员</span>
                <strong>进入管理工作台</strong>
                <small>教务、学工、实习、毕设与审批工作</small>
                <b aria-hidden="true">→</b>
              </a>
              <a v-if="studentLoginUrl" :href="studentLoginUrl" class="yk-login-card">
                <span>学生</span>
                <strong>进入学生门户</strong>
                <small>查看待办、提交材料与查询进度</small>
                <b aria-hidden="true">→</b>
              </a>
              <a v-if="enterpriseLoginUrl" :href="enterpriseLoginUrl" class="yk-login-card">
                <span>企业协同</span>
                <strong>企业注册 / 登录</strong>
                <small>岗位、实习协同与评价；首次注册由学校邀请激活</small>
                <b aria-hidden="true">→</b>
              </a>
            </div>
          </section>
        </div>
      </section>

      <section id="lifecycle" class="yk-section yk-home-lifecycle-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">一名学生，一条贯穿全程的业务线</p>
            <h2>从迎新到就业，阶段衔接而不是系统堆叠</h2>
            <p>六个阶段共享学生、组织、身份、权限与关键业务事实，每个阶段都知道从哪里来、下一步到哪里去。</p>
          </div>
          <ol class="yk-home-lifecycle-track">
            <li v-for="(item, index) in lifecycleStages" :key="item.key">
              <router-link :to="item.route">
                <span class="yk-home-stage-index">0{{ index + 1 }}</span>
                <small>{{ item.stage }}</small>
                <h3>{{ item.title }}</h3>
                <p>{{ item.desc }}</p>
                <strong>了解这一阶段 →</strong>
              </router-link>
            </li>
          </ol>
        </div>
      </section>

      <section id="products" class="yk-section yk-home-products-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">四大核心产品</p>
            <h2>覆盖学校最重、最连续的业务现场</h2>
            <p>每个产品都可以独立落地，也可以共享工作台、审批、消息、身份与数据治理能力协同运行。</p>
          </div>
          <div class="yk-home-product-grid">
            <article v-for="product in products" :key="product.slug" class="yk-home-product-card">
              <router-link class="yk-home-product-image" :to="`/products/${product.slug}`" :aria-label="`查看${product.name}`">
                <img :src="product.cover" :alt="product.coverAlt" loading="lazy" decoding="async" />
              </router-link>
              <div class="yk-home-product-body">
                <div class="yk-home-product-title">
                  <span :style="{ color: product.accent, background: product.soft }">{{ product.mark }}</span>
                  <div><small>{{ product.eyebrow }}</small><h3>{{ product.name }}</h3></div>
                </div>
                <p>{{ product.summary }}</p>
                <router-link :to="`/products/${product.slug}`">查看产品详情 →</router-link>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section class="yk-section yk-home-trust-section" aria-labelledby="trust-title">
        <div class="yk-shell yk-home-trust-layout">
          <div class="yk-section-heading yk-section-heading-left">
            <p class="yk-kicker">典型交付结构</p>
            <h2 id="trust-title">不从一张功能清单开始，而从一条真实流程开始</h2>
            <p>以下结构不对应特定学校，也不使用未经授权的客户名称；它说明一个项目如何从需求判断走向可验收结果。</p>
          </div>
          <ol class="yk-home-trust-grid">
            <li v-for="item in trustSteps" :key="item.n"><span>{{ item.n }}</span><div><h3>{{ item.title }}</h3><p>{{ item.desc }}</p></div></li>
          </ol>
        </div>
      </section>

      <section id="platform" class="yk-section yk-home-platform-section">
        <div class="yk-shell">
          <div class="yk-section-heading yk-section-heading-left">
            <p class="yk-kicker">一套平台，而不是四套后台</p>
            <h2>统一工作、协同与治理</h2>
            <p>业务中心可以不同，但老师的工作入口、学生的服务体验和学校的治理边界应该保持一致。</p>
          </div>
          <div class="yk-home-pillar-grid">
            <article v-for="pillar in platformPillars" :key="pillar.key" class="yk-home-pillar-card">
              <figure><img :src="pillar.image" :alt="pillar.alt" loading="lazy" decoding="async" /></figure>
              <div>
                <span>{{ pillar.eyebrow }}</span>
                <h3>{{ pillar.title }}</h3>
                <p>{{ pillar.desc }}</p>
                <router-link :to="pillar.route">{{ pillar.link }} →</router-link>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section id="delivery" class="yk-section yk-home-delivery-section">
        <div class="yk-shell yk-home-delivery-layout">
          <div class="yk-section-heading yk-section-heading-left">
            <p class="yk-kicker">从产品能力到学校正式使用</p>
            <h2>四步完成部署与落地</h2>
            <p>把详细实施工作留在交付方案里，首页只呈现学校需要判断的关键路径。</p>
            <div class="yk-home-delivery-actions">
              <router-link class="yk-button yk-button-primary" to="/solutions/deployment">查看部署方案</router-link>
              <router-link class="yk-button yk-button-ghost" to="/services/delivery">了解实施服务</router-link>
            </div>
          </div>
          <ol class="yk-home-delivery-steps">
            <li v-for="step in deliverySteps" :key="step.n">
              <span>{{ step.n }}</span><div><h3>{{ step.title }}</h3><p>{{ step.desc }}</p></div>
            </li>
          </ol>
        </div>
      </section>

      <section id="faq" class="yk-section yk-home-faq-section">
        <div class="yk-shell yk-home-faq-layout">
          <div class="yk-section-heading yk-section-heading-left">
            <p class="yk-kicker">采购前常见问题</p>
            <h2>快速判断是否适合你们学校</h2>
            <p>答案基于当前产品能力和可交付范围，便于学校采购人员检索、比较和引用。</p>
            <small class="yk-home-updated">公开内容更新：<time :datetime="contentUpdatedAt">{{ contentUpdatedAt }}</time></small>
          </div>
          <div class="yk-home-faq-list">
            <details v-for="item in faqs" :key="item.q">
              <summary>{{ item.q }}</summary>
              <p>{{ item.a }}</p>
            </details>
          </div>
        </div>
      </section>

      <section id="contact" class="yk-final-cta">
        <div class="yk-shell yk-final-inner">
          <p class="yk-final-kicker">湖南跃科信息工程有限公司</p>
          <h2>从一条最难推进的业务流程开始</h2>
          <p>告诉我们学校当前最耗时、最容易断点的工作，我们用真实产品流程一起拆解。</p>
          <div class="yk-final-actions">
            <router-link class="yk-button yk-button-light" to="/contact">预约产品演示</router-link>
            <a class="yk-button yk-button-ghost" :href="contact.phoneHref">拨打 {{ contact.phone }}</a>
          </div>
        </div>
      </section>
    </main>

    <footer class="yk-footer">
      <div class="yk-shell yk-footer-inner">
        <div><strong>{{ companyName }}</strong><span>职业院校学生全生命周期数字化平台</span></div>
        <div class="yk-footer-links">
          <a :href="contact.phoneHref">{{ contact.phone }}</a>
          <a v-for="item in footerLinks" :key="item.label" :href="item.url" target="_blank" rel="noopener noreferrer">{{ item.label }}</a>
          <a v-if="icpNumber" :href="icpQueryUrl" target="_blank" rel="noopener noreferrer">{{ icpNumber }}</a>
          <span>© {{ year }}</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script>
import { OFFICIAL_PRODUCT_LIST } from '../config/officialProducts'
import { OFFICIAL_SITE_CONTACT } from '../config/officialSalesPages'
import { HOME_FAQS, LIFECYCLE_STAGES, OFFICIAL_CONTENT_UPDATED_AT } from '../config/officialWebsiteStory'
import {
  COMPANY_NAME,
  ENTERPRISE_LOGIN_URL,
  ICP_NUMBER,
  ICP_QUERY_URL,
  PRIVACY_URL,
  STUDENT_LOGIN_URL,
  SUPPORT_URL,
  TEACHER_LOGIN_URL,
  TERMS_URL
} from '../config/portalConfig'
import '../styles/official-site.css'
import '../styles/official-site-story.css'

const COVER_BY_PRODUCT = {
  'academic-affairs': '/official-site/academic.webp',
  'student-affairs': '/official-site/student-affairs-dashboard.png',
  graduation: '/official-site/graduation-dashboard.webp',
  internship: '/official-site/internship.webp'
}

export default {
  name: 'PortalHomeView',
  data() {
    return {
      menuOpen: false,
      companyName: COMPANY_NAME,
      icpNumber: ICP_NUMBER,
      icpQueryUrl: ICP_QUERY_URL,
      contentUpdatedAt: OFFICIAL_CONTENT_UPDATED_AT,
      teacherLoginUrl: TEACHER_LOGIN_URL,
      studentLoginUrl: STUDENT_LOGIN_URL,
      enterpriseLoginUrl: ENTERPRISE_LOGIN_URL,
      lifecycleStages: LIFECYCLE_STAGES,
      faqs: HOME_FAQS,
      trustSteps: [
        { n: '01', title: '选择一条主线', desc: '先选择学校最耗时、最容易断点的一条流程，明确本轮目标。' },
        { n: '02', title: '核对角色与数据', desc: '确认谁发起、谁办理、看什么数据，以及现有系统如何衔接。' },
        { n: '03', title: '按范围联调验收', desc: '用确认过的流程、权限和结果逐项联调，形成清晰验收边界。' }
      ],
      platformPillars: [
        {
          key: 'workbench',
          eyebrow: '统一工作入口',
          title: '老师先看到今天要处理什么',
          desc: '跨教务、学工、实习和毕设汇聚待办、风险、进度与下一动作。',
          image: '/official-site/workbench.webp',
          alt: '跃科统一工作台产品界面',
          route: '/solutions/teacher-workbench',
          link: '了解教师工作台'
        },
        {
          key: 'mobile',
          eyebrow: '多端协同',
          title: '复杂工作留在 PC，高频任务进入移动端',
          desc: '学生和教师围绕查询、提交、审核、核验与风险处置完成高频任务。',
          image: '/official-site/student-portal.webp',
          alt: '跃科学生服务门户产品界面',
          route: '/solutions/student-lifecycle',
          link: '了解学生服务'
        },
        {
          key: 'governance',
          eyebrow: '学校级治理',
          title: '身份、权限、数据范围与审计共享一套底座',
          desc: '不同业务中心共享学校组织、主数据和治理边界，避免重复建设。',
          image: '/official-site/leadership-cockpit.webp',
          alt: '跃科领导数据驾驶舱产品界面',
          route: '/platform',
          link: '查看平台能力'
        }
      ],
      deliverySteps: [
        { n: '01', title: '确认范围', desc: '确认学校组织、角色、启用模块、数据来源与部署边界。' },
        { n: '02', title: '准备底座', desc: '完成组织主数据、用户角色、权限范围与业务配置。' },
        { n: '03', title: '迁移联调', desc: '导入历史数据，围绕关键角色验证真实业务主链。' },
        { n: '04', title: '上线验收', desc: '完成上线检查、生产启用、验收和后续升级安排。' }
      ]
    }
  },
  computed: {
    year() { return new Date().getFullYear() },
    contact() { return OFFICIAL_SITE_CONTACT },
    products() {
      return OFFICIAL_PRODUCT_LIST.map((product) => ({
        ...product,
        cover: COVER_BY_PRODUCT[product.slug],
        coverAlt: `跃科${product.name}产品界面`
      }))
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
    document.title = '跃科｜职业院校学生全生命周期数字化平台'
  }
}
</script>
