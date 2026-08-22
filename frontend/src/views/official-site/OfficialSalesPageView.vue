<template>
  <div v-if="page" class="yk-site yk-sales-page">
    <header class="yk-header">
      <div class="yk-shell yk-nav">
        <router-link class="yk-brand" to="/" aria-label="返回跃科官网首页">
          <span class="yk-brand-dot" aria-hidden="true">跃</span>
          <span class="yk-brand-copy"><strong>跃科</strong><small>职业院校学生全生命周期平台</small></span>
        </router-link>
        <nav class="yk-nav-links" aria-label="销售页面导航">
          <router-link to="/products/academic-affairs">教务</router-link>
          <router-link to="/products/student-affairs">学工</router-link>
          <router-link to="/products/graduation">毕设</router-link>
          <router-link to="/products/internship">实习</router-link>
          <router-link to="/contact">联系跃科</router-link>
        </nav>
        <a class="yk-nav-cta" :href="contact.phoneHref">{{ contact.phone }}</a>
      </div>
    </header>

    <main>
      <section class="yk-sales-hero">
        <div class="yk-shell yk-sales-hero-grid">
          <div class="yk-sales-copy">
            <p class="yk-kicker">{{ page.eyebrow }}</p>
            <h1>{{ page.hero }}</h1>
            <p class="yk-sales-lead">{{ page.description }}</p>
            <div class="yk-hero-actions">
              <a class="yk-button yk-button-primary" :href="contact.phoneHref">电话咨询 {{ contact.phone }}</a>
              <router-link v-if="page.path !== '/contact'" class="yk-button yk-button-ghost" to="/contact">预约产品演示</router-link>
              <router-link class="yk-button yk-button-ghost" to="/">返回官网</router-link>
            </div>
            <div class="yk-sales-trust-row">
              <span>真实产品截图</span><span>真实业务代码</span><span>不伪造客户数据</span><span>支持生产部署</span>
            </div>
          </div>
          <figure v-if="page.screenshots?.[0]" class="yk-sales-hero-shot">
            <img :src="page.screenshots[0]" :alt="`${page.navTitle}真实产品界面`" decoding="async" />
            <figcaption>真实运行界面 · 截图中的业务数据来自隔离测试环境</figcaption>
          </figure>
        </div>
      </section>

      <section v-if="page.path === '/contact'" class="yk-section yk-lead-section">
        <div class="yk-shell yk-lead-grid">
          <div class="yk-lead-copy">
            <p class="yk-kicker">预约产品演示</p>
            <h2>留下学校和电话，我会直接收到短信</h2>
            <p>填写后，系统会把学校、联系人、联系电话、意向产品和留言摘要直接短信发送给跃科商务联系人。</p>
            <div class="yk-lead-privacy">
              <strong>不进入业务数据库</strong>
              <span>本次咨询不创建销售线索表，不保存访客手机号或留言到跃科业务数据库。</span>
            </div>
            <a class="yk-lead-phone" :href="contact.phoneHref">也可以直接拨打 {{ contact.phone }}</a>
          </div>

          <form class="yk-lead-form" @submit.prevent="submitLead" novalidate>
            <label>
              <span>学校名称 *</span>
              <input v-model.trim="leadForm.schoolName" maxlength="80" autocomplete="organization" placeholder="例如：湖南某职业学院" required />
            </label>
            <div class="yk-lead-form-row">
              <label>
                <span>联系人</span>
                <input v-model.trim="leadForm.contactName" maxlength="40" autocomplete="name" placeholder="例如：张老师" />
              </label>
              <label>
                <span>联系电话 *</span>
                <input v-model.trim="leadForm.phone" maxlength="11" inputmode="numeric" autocomplete="tel" placeholder="11 位手机号" required />
              </label>
            </div>
            <label>
              <span>意向产品 *</span>
              <select v-model="leadForm.interest" required>
                <option value="教务系统">教务系统</option>
                <option value="学工中心">学工中心</option>
                <option value="毕业设计">毕业设计</option>
                <option value="岗位实习">岗位实习</option>
                <option value="学生全生命周期平台">学生全生命周期平台</option>
                <option value="私有化部署与系统集成">私有化部署与系统集成</option>
              </select>
            </label>
            <label>
              <span>想重点了解什么</span>
              <textarea v-model.trim="leadForm.message" maxlength="200" rows="4" placeholder="例如：想了解岗位实习模块、部署方式和报价"></textarea>
              <small>{{ leadForm.message.length }}/200</small>
            </label>

            <label class="yk-lead-honeypot" aria-hidden="true">
              <span>Website</span>
              <input v-model="leadForm.website" tabindex="-1" autocomplete="off" />
            </label>

            <button class="yk-button yk-button-primary yk-lead-submit" type="submit" :disabled="leadSubmitting || leadSubmitted">
              {{ leadSubmitting ? '正在提交…' : leadSubmitted ? '已提交，我们会尽快联系' : '提交并短信通知跃科' }}
            </button>
            <p v-if="leadError" class="yk-lead-error" role="alert">{{ leadError }}</p>
            <p v-else-if="leadSubmitted" class="yk-lead-success" role="status">提交成功。你的信息已用于本次短信通知，不会写入跃科业务数据库。</p>
          </form>
        </div>
      </section>

      <section class="yk-section yk-sales-value-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">为什么这样设计</p>
            <h2>{{ sectionTitle }}</h2>
            <p>{{ sectionLead }}</p>
          </div>
          <div class="yk-value-grid">
            <article v-for="item in valuePoints" :key="item.title" class="yk-value-card">
              <span class="yk-icon-tile" aria-hidden="true">{{ item.mark }}</span>
              <h3>{{ item.title }}</h3>
              <p>{{ item.desc }}</p>
            </article>
          </div>
        </div>
      </section>

      <section v-if="page.screenshots?.length" class="yk-section yk-products-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">真实产品证据</p>
            <h2>客户看到的是已经运行的系统界面，不是概念效果图</h2>
            <p>以下截图来自仓库真实代码和隔离 Playwright / E2E 环境，仅用于说明产品能力与界面结构，不代表真实学校运营规模或客户案例。</p>
          </div>
          <div class="yk-sales-evidence-grid">
            <figure v-for="(shot, index) in page.screenshots" :key="shot" class="yk-sales-evidence-card">
              <img :src="shot" :alt="`${page.navTitle}真实产品截图 ${index + 1}`" loading="lazy" decoding="async" />
              <figcaption>{{ evidenceCaption(index) }}</figcaption>
            </figure>
          </div>
        </div>
      </section>

      <section class="yk-section yk-sales-related-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">继续了解</p>
            <h2>从当前问题进入对应产品，而不是在官网里迷路</h2>
          </div>
          <div class="yk-sales-related-grid">
            <router-link v-for="item in relatedPages" :key="item.path" :to="item.path" class="yk-sales-related-card">
              <span>{{ item.eyebrow }}</span><strong>{{ item.navTitle }}</strong><p>{{ item.description }}</p><b aria-hidden="true">→</b>
            </router-link>
          </div>
        </div>
      </section>

      <section class="yk-final-cta">
        <div class="yk-shell yk-final-inner">
          <p class="yk-final-kicker">湖南跃科信息工程有限公司</p>
          <h2>{{ page.path === '/contact' ? '从真实业务问题开始沟通' : '需要把这套能力落到学校真实流程里？' }}</h2>
          <p>可直接沟通教务、学工、毕业设计、岗位实习、部署方式与系统集成。我们优先从学校当前的业务流程、角色和数据边界出发。</p>
          <div class="yk-final-actions">
            <a class="yk-button yk-button-light" :href="contact.phoneHref">拨打 {{ contact.phone }}</a>
            <router-link v-if="page.path !== '/contact'" class="yk-button yk-button-ghost" to="/contact">预约产品演示</router-link>
          </div>
        </div>
      </section>
    </main>

    <footer class="yk-footer">
      <div class="yk-shell yk-footer-inner">
        <div><strong>{{ contact.company }}</strong><span>职业院校学生全生命周期数字化平台</span></div>
        <div class="yk-footer-links"><a :href="contact.phoneHref">{{ contact.phone }}</a><span>© {{ year }}</span></div>
      </div>
    </footer>
  </div>
</template>

<script>
import { OFFICIAL_SALES_PAGE_MAP, OFFICIAL_SALES_PAGES, OFFICIAL_SITE_CONTACT, officialCanonicalUrl } from '@/config/officialSalesPages'
import { API_BASE_URL, API_PREFIX } from '@/services/http/config'
import '@/styles/official-site.css'

const DEFAULT_POINTS = Object.freeze([
  { mark: '1', title: '先解决真实工作', desc: '页面只讲现有业务闭环、角色和证据，不用抽象概念替代老师每天真正要处理的事情。' },
  { mark: '2', title: '状态与责任可追踪', desc: '关键业务以状态、责任人、下一动作和过程留痕组织，减少线下口头确认与重复沟通。' },
  { mark: '3', title: '多端共享业务事实', desc: '管理 PC、教师端、学生端与企业协同端共享同一业务状态，不让不同端各自维护一套真值。' },
  { mark: '4', title: '安全边界先于便利', desc: '多租户、权限、数据范围和审计继续作为生产底座，官网展示不改变系统已有的安全边界。' }
])

const TYPE_COPY = Object.freeze({
  solution: { title: '把分散功能收敛成可持续运行的学校工作方式', lead: '解决方案页面重点说明角色怎么协同、业务怎么连续、异常怎么处理，而不是重新罗列菜单。' },
  service: { title: '功能上线之后，还要能稳定交付和持续维护', lead: '从学校开通、初始化、培训到运行支持和升级，交付过程同样需要标准化和可追踪。' },
  contact: { title: '把需求说清楚，比先选一堆功能更重要', lead: '可以直接从学校当前最难推进的一条流程开始，先判断角色、状态、数据和部署边界，再讨论产品组合。' }
})

export default {
  name: 'OfficialSalesPageView',
  data() {
    return {
      leadForm: {
        schoolName: '',
        contactName: '',
        phone: '',
        interest: '岗位实习',
        message: '',
        website: ''
      },
      leadSubmitting: false,
      leadSubmitted: false,
      leadError: ''
    }
  },
  computed: {
    page() { return OFFICIAL_SALES_PAGE_MAP[this.$route.path] || null },
    contact() { return OFFICIAL_SITE_CONTACT },
    year() { return new Date().getFullYear() },
    valuePoints() { return DEFAULT_POINTS },
    sectionTitle() { return (TYPE_COPY[this.page?.type] || TYPE_COPY.solution).title },
    sectionLead() { return (TYPE_COPY[this.page?.type] || TYPE_COPY.solution).lead },
    relatedPages() {
      const priority = ['/products/academic-affairs', '/products/student-affairs', '/products/graduation', '/products/internship']
      const items = priority.map((path) => OFFICIAL_SALES_PAGE_MAP[path]).filter(Boolean)
      if (this.page?.type === 'product') return OFFICIAL_SALES_PAGES.filter((item) => item.type !== 'product' && item.path !== '/contact').slice(0, 4)
      return items
    }
  },
  watch: {
    '$route.path': { immediate: true, handler() { this.syncHead() } }
  },
  methods: {
    evidenceCaption(index) {
      return index === 0 ? `${this.page.navTitle}核心工作区` : `${this.page.navTitle}真实业务界面 ${index + 1}`
    },
    async submitLead() {
      this.leadError = ''
      const phone = String(this.leadForm.phone || '').replace(/\D/g, '')
      if (this.leadForm.schoolName.trim().length < 2) {
        this.leadError = '请填写学校名称'
        return
      }
      if (!/^1[3-9]\d{9}$/.test(phone)) {
        this.leadError = '请输入有效的 11 位手机号'
        return
      }
      this.leadSubmitting = true
      try {
        const response = await fetch(`${API_BASE_URL}${API_PREFIX}/notification/website-lead`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            school_name: this.leadForm.schoolName,
            contact_name: this.leadForm.contactName,
            phone,
            interest: this.leadForm.interest,
            message: this.leadForm.message,
            website: this.leadForm.website,
            source_path: this.$route.path
          })
        })
        const body = await response.json().catch(() => ({}))
        if (!response.ok) {
          throw new Error(body?.detail || '提交失败，请直接电话联系')
        }
        this.leadSubmitted = true
      } catch (error) {
        this.leadError = error?.message || '提交失败，请直接电话联系'
      } finally {
        this.leadSubmitting = false
      }
    },
    upsertMeta(selector, attrs) {
      let node = document.head.querySelector(selector)
      if (!node) {
        node = document.createElement('meta')
        document.head.appendChild(node)
      }
      Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, value))
    },
    syncHead() {
      const page = OFFICIAL_SALES_PAGE_MAP[this.$route.path]
      if (!page) {
        this.$router.replace('/')
        return
      }
      document.title = page.title
      this.upsertMeta('meta[name="description"]', { name: 'description', content: page.description })
      this.upsertMeta('meta[property="og:title"]', { property: 'og:title', content: page.title })
      this.upsertMeta('meta[property="og:description"]', { property: 'og:description', content: page.description })
      this.upsertMeta('meta[property="og:type"]', { property: 'og:type', content: 'website' })
      this.upsertMeta('meta[property="og:url"]', { property: 'og:url', content: officialCanonicalUrl(page.path) })
      let canonical = document.head.querySelector('link[rel="canonical"]')
      if (!canonical) {
        canonical = document.createElement('link')
        canonical.setAttribute('rel', 'canonical')
        document.head.appendChild(canonical)
      }
      canonical.setAttribute('href', officialCanonicalUrl(page.path))
    }
  }
}
</script>

<style scoped>
.yk-sales-hero { padding: 92px 0 72px; background: radial-gradient(circle at 15% 10%, #eef6ff 0, transparent 40%), linear-gradient(180deg, #f8fbff 0%, #fff 100%); }
.yk-sales-hero-grid { display: grid; grid-template-columns: minmax(0, .9fr) minmax(420px, 1.1fr); gap: 54px; align-items: center; }
.yk-sales-copy h1 { margin: 14px 0 18px; max-width: 760px; color: #10213d; font-size: clamp(38px, 5vw, 62px); line-height: 1.08; letter-spacing: -2px; }
.yk-sales-lead { max-width: 720px; color: #5d6d86; font-size: 18px; line-height: 1.8; }
.yk-sales-trust-row { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 24px; }
.yk-sales-trust-row span { padding: 8px 12px; border: 1px solid #dbe7f7; border-radius: 999px; background: #fff; color: #53637c; font-size: 13px; }
.yk-sales-hero-shot { margin: 0; overflow: hidden; border: 1px solid #dbe7f7; border-radius: 24px; background: #fff; box-shadow: 0 24px 70px rgba(16, 33, 61, .12); }
.yk-sales-hero-shot img { display: block; width: 100%; aspect-ratio: 16 / 10; object-fit: cover; object-position: top; }
.yk-sales-hero-shot figcaption { padding: 12px 16px 15px; color: #728098; font-size: 12px; }
.yk-lead-section { background: #f7faff; }
.yk-lead-grid { display: grid; grid-template-columns: minmax(0, .85fr) minmax(420px, 1.15fr); gap: 54px; align-items: start; }
.yk-lead-copy h2 { margin: 12px 0 18px; color: #10213d; font-size: clamp(30px, 4vw, 44px); line-height: 1.18; }
.yk-lead-copy > p { color: #5d6d86; font-size: 17px; line-height: 1.8; }
.yk-lead-privacy { display: grid; gap: 6px; margin: 24px 0 20px; padding: 18px 20px; border: 1px solid #d7e6fa; border-radius: 16px; background: #fff; }
.yk-lead-privacy strong { color: #1667e8; }
.yk-lead-privacy span { color: #66758c; line-height: 1.65; }
.yk-lead-phone { color: #1667e8; font-weight: 700; text-decoration: none; }
.yk-lead-form { position: relative; display: grid; gap: 18px; padding: 28px; border: 1px solid #dbe7f7; border-radius: 24px; background: #fff; box-shadow: 0 22px 54px rgba(16, 33, 61, .09); }
.yk-lead-form label { display: grid; gap: 8px; }
.yk-lead-form label > span { color: #233a5d; font-size: 14px; font-weight: 700; }
.yk-lead-form input, .yk-lead-form select, .yk-lead-form textarea { width: 100%; box-sizing: border-box; border: 1px solid #cedcf0; border-radius: 12px; background: #fff; color: #10213d; font: inherit; outline: none; transition: border-color .18s ease, box-shadow .18s ease; }
.yk-lead-form input, .yk-lead-form select { height: 46px; padding: 0 13px; }
.yk-lead-form textarea { padding: 12px 13px; resize: vertical; min-height: 112px; }
.yk-lead-form input:focus, .yk-lead-form select:focus, .yk-lead-form textarea:focus { border-color: #4d8ee8; box-shadow: 0 0 0 3px rgba(22, 103, 232, .1); }
.yk-lead-form label small { justify-self: end; color: #8a97aa; }
.yk-lead-form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.yk-lead-submit { width: 100%; justify-content: center; border: 0; cursor: pointer; }
.yk-lead-submit:disabled { cursor: default; opacity: .72; }
.yk-lead-error, .yk-lead-success { margin: -4px 0 0; font-size: 14px; line-height: 1.6; }
.yk-lead-error { color: #b42318; }
.yk-lead-success { color: #087443; }
.yk-lead-honeypot { position: absolute !important; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); clip-path: inset(50%); white-space: nowrap; }
.yk-sales-evidence-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 26px; }
.yk-sales-evidence-card { margin: 0; overflow: hidden; border: 1px solid #dbe7f7; border-radius: 22px; background: #fff; box-shadow: 0 18px 46px rgba(16, 33, 61, .08); }
.yk-sales-evidence-card img { display: block; width: 100%; aspect-ratio: 16 / 10; object-fit: cover; object-position: top; background: #eef5ff; }
.yk-sales-evidence-card figcaption { padding: 14px 16px 16px; color: #5d6d86; font-size: 14px; }
.yk-sales-related-section { background: #f7faff; }
.yk-sales-related-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 18px; }
.yk-sales-related-card { position: relative; min-height: 220px; padding: 24px; border: 1px solid #dbe7f7; border-radius: 20px; background: #fff; color: inherit; text-decoration: none; transition: transform .18s ease, box-shadow .18s ease; }
.yk-sales-related-card:hover { transform: translateY(-3px); box-shadow: 0 18px 42px rgba(16, 33, 61, .08); }
.yk-sales-related-card span { color: #1667e8; font-size: 12px; font-weight: 700; }
.yk-sales-related-card strong { display: block; margin: 12px 0 10px; color: #10213d; font-size: 20px; }
.yk-sales-related-card p { margin: 0; color: #66758c; line-height: 1.7; }
.yk-sales-related-card b { position: absolute; right: 22px; bottom: 20px; color: #1667e8; }
@media (max-width: 980px) { .yk-sales-hero-grid, .yk-lead-grid { grid-template-columns: 1fr; } .yk-sales-related-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 680px) { .yk-sales-hero { padding-top: 64px; } .yk-sales-copy h1 { font-size: 38px; letter-spacing: -1px; } .yk-sales-evidence-grid, .yk-sales-related-grid, .yk-lead-form-row { grid-template-columns: 1fr; } .yk-lead-form { padding: 22px 18px; } }
</style>
