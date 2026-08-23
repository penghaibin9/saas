<template>
  <div class="yk-site yk-story-site yk-platform-highlight-page">
    <header class="yk-header">
      <div class="yk-shell yk-nav">
        <router-link class="yk-brand" to="/" aria-label="返回跃科官网首页">
          <span class="yk-brand-dot" aria-hidden="true">跃</span>
          <span class="yk-brand-copy"><strong>跃科</strong><small>职业院校学生全生命周期平台</small></span>
        </router-link>
        <nav class="yk-nav-links" aria-label="平台能力页面导航">
          <router-link to="/products">产品</router-link>
          <router-link to="/solutions/student-lifecycle">学生生命周期</router-link>
          <router-link class="router-link-active" to="/platform">平台能力</router-link>
          <router-link to="/solutions/deployment">部署与服务</router-link>
          <router-link to="/contact">联系跃科</router-link>
        </nav>
        <router-link class="yk-nav-cta" to="/contact">预约产品演示</router-link>
      </div>
    </header>

    <main>
      <section class="yk-highlight-hero" aria-labelledby="platform-highlight-title">
        <div class="yk-shell yk-highlight-hero-grid">
          <div>
            <div class="yk-highlight-status"><i></i> 平台八大特色 · 已具备能力与持续演进清晰区分</div>
            <p class="yk-kicker">跃科平台能力</p>
            <h1 id="platform-highlight-title">把企业级数字工作平台能力，真正带进职业院校学生管理。</h1>
            <p class="yk-highlight-lead">
              不只管理学生信息，更连接学生成长过程；不只提交业务材料，更管理真实文件版本；
              不只完成线上审批，更让办理依据、责任和下一动作清楚可追踪。
            </p>
            <div class="yk-highlight-pill-row" aria-label="平台关键词">
              <span v-for="tag in heroTags" :key="tag">{{ tag }}</span>
            </div>
            <div class="yk-hero-actions">
              <a class="yk-button yk-button-primary" href="#eight-highlights">看八大特色</a>
              <a class="yk-button yk-button-ghost" href="#current-foundation">看当前能力底座</a>
              <router-link class="yk-button yk-button-ghost" to="/contact">预约产品演示</router-link>
            </div>
            <p class="yk-highlight-truth">
              本页只把已经进入当前产品代码与真实业务入口的能力标记为“当前具备”；尚未完成生产封板的能力统一标记为“持续演进”。
              具体交付范围以项目合同、正式版本与上线验收为准。
            </p>
          </div>

          <div class="yk-highlight-visual" aria-label="跃科统一工作方式真实界面">
            <figure class="yk-highlight-main-shot">
              <img src="/official-site/workbench.webp" alt="跃科统一工作台真实运行界面" decoding="async" />
              <figcaption>真实运行界面 · 隔离测试数据 · 不作为真实客户运营数据</figcaption>
            </figure>
            <div class="yk-highlight-float yk-highlight-float-one"><span>围绕一个学生</span><strong>跨业务看状态与风险</strong><small>学生 360° 工作方式</small></div>
            <div class="yk-highlight-float yk-highlight-float-two"><span>围绕一件事</span><strong>待办 · 审批 · 材料 · 证据</strong><small>统一业务上下文</small></div>
          </div>
        </div>
      </section>

      <section class="yk-highlight-positioning">
        <div class="yk-shell">
          <p class="yk-kicker">跃科的差异化，不是菜单更多</p>
          <h2>从“把流程搬到线上”，继续走向“把学校业务变成可信、连续、可协同的数字工作”。</h2>
          <p>教务、学工、岗位实习、毕业设计继续保有各自的专业规则；平台把学生、文件、审批、Excel、任务、帮助、搜索和证据等共性能力连接起来。</p>
          <div class="yk-highlight-position-lines">
            <span>不只管理学生信息，更连接学生成长过程</span>
            <span>不只上传附件，更管理真实文件版本</span>
            <span>不只完成审批，更保留办理依据与上下文</span>
            <span>不只展示待办数量，更让老师直达那件事</span>
            <span>不只把模块放一起，更形成连续业务主线</span>
          </div>
        </div>
      </section>

      <section id="current-foundation" class="yk-section yk-highlight-foundation-section">
        <div class="yk-shell">
          <div class="yk-section-heading yk-section-heading-left">
            <p class="yk-kicker">已经进入当前产品的能力底座</p>
            <h2>不是等 ABCD 做完以后才有平台能力。</h2>
            <p>当前产品已经存在一批可直接支撑销售、实施和学校日常运行的平台化能力；后续演进是在这个底座上继续加深，而不是从零开始。</p>
          </div>
          <div class="yk-highlight-foundation-grid">
            <article v-for="item in currentFoundation" :key="item.title" class="yk-highlight-foundation-card">
              <div class="yk-highlight-card-top"><span class="yk-highlight-mark">{{ item.mark }}</span><b class="yk-highlight-badge is-live">当前具备</b></div>
              <h3>{{ item.title }}</h3>
              <p>{{ item.desc }}</p>
              <strong>{{ item.value }}</strong>
            </article>
          </div>
        </div>
      </section>

      <section id="eight-highlights" class="yk-section yk-highlight-feature-section">
        <div class="yk-shell">
          <div class="yk-section-heading yk-section-heading-left">
            <p class="yk-kicker">跃科平台八大特色</p>
            <h2>围绕学生、材料、审批、证据与协同，形成真正能被学校感知的平台深度。</h2>
            <p>八项能力统一用学校用户能理解的业务价值表达，不用“功能数量”替代产品深度；当前具备和持续演进明确分开。</p>
          </div>
          <div class="yk-highlight-feature-grid">
            <article v-for="item in highlights" :key="item.no" class="yk-highlight-feature-card" :class="{ 'is-evolving': item.status === '持续演进' }">
              <div class="yk-highlight-feature-top">
                <span class="yk-highlight-mark">{{ item.no }}</span>
                <b class="yk-highlight-badge" :class="item.status === '当前具备' ? 'is-live' : 'is-evolving'">{{ item.status }}</b>
              </div>
              <h3>{{ item.title }}</h3>
              <p>{{ item.summary }}</p>
              <div class="yk-highlight-feature-meta">
                <div><span>学校痛点</span><strong>{{ item.pain }}</strong></div>
                <div><span>平台价值</span><strong>{{ item.value }}</strong></div>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section class="yk-section yk-highlight-proof-section">
        <div class="yk-shell">
          <div class="yk-section-heading yk-section-heading-left">
            <p class="yk-kicker">真实产品证据</p>
            <h2>先展示已经运行的能力，不用概念图冒充生产事实。</h2>
            <p>以下截图来自当前仓库真实代码和隔离浏览器环境，用于证明现有工作台、审批、学生业务和材料评阅界面；持续演进能力不会借这些截图伪装成“已全面上线”。</p>
          </div>
          <div class="yk-highlight-proof-grid">
            <figure v-for="proof in proofs" :key="proof.image" class="yk-highlight-proof-card">
              <img :src="proof.image" :alt="proof.alt" loading="lazy" decoding="async" />
              <figcaption><strong>{{ proof.title }}</strong><span>{{ proof.desc }}</span></figcaption>
            </figure>
          </div>
        </div>
      </section>

      <section class="yk-section yk-highlight-evolution-section">
        <div class="yk-shell">
          <div class="yk-section-heading yk-section-heading-left">
            <p class="yk-kicker">ABCD · 下一阶段平台演进</p>
            <h2>从成熟智慧校园能力，继续向企业级数字工作平台深度推进。</h2>
            <p>ABCD 不是另起炉灶，而是在现有学生、文件、审批、待办和任务底座上继续补强可信、规则、智能与协同四类公共能力。</p>
          </div>
          <div class="yk-highlight-evolution-grid">
            <article v-for="group in evolutionGroups" :key="group.key" class="yk-highlight-evolution-card">
              <span>{{ group.key }}</span><small>{{ group.label }}</small><h3>{{ group.title }}</h3><p>{{ group.desc }}</p><strong>{{ group.points }}</strong>
            </article>
          </div>
        </div>
      </section>

      <section class="yk-section yk-highlight-work-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">老师真正感知到的变化</p>
            <h2>系统越大，不应该让老师越难用。</h2>
            <p>平台能力最终要落到“少找入口、少重复检查、少来回下载、少靠人工记忆”，而不是只增加后台配置项。</p>
          </div>
          <div class="yk-highlight-work-grid">
            <article v-for="item in workWays" :key="item.title" class="yk-highlight-work-card">
              <span>{{ item.label }}</span><h3>{{ item.title }}</h3><p>{{ item.desc }}</p>
            </article>
          </div>
        </div>
      </section>

      <section class="yk-highlight-layer-section">
        <div class="yk-shell yk-highlight-layer-grid">
          <div>
            <p class="yk-kicker">最终形成什么</p>
            <h2>跃科构建的是一套职业院校学生全生命周期数字工作平台。</h2>
            <p>业务模块负责专业规则与正式状态；公共平台负责把文件、规则、审批、证据、查询、任务、异常和学生轨迹连接起来。这样平台越扩展，共性能力越统一，而不是每个模块重新造一套。</p>
            <div class="yk-highlight-layer-tags"><span v-for="item in platformLayers" :key="item">{{ item }}</span></div>
          </div>
          <aside class="yk-highlight-authority">
            <span>公共平台负责</span><strong>学生上下文 · 文件版本 · 审批工作 · Excel 治理 · 任务协作 · 帮助知识 · 证据与查询</strong>
            <hr />
            <span>业务模块继续负责</span><strong>教务规则 · 学工规则 · 岗位实习状态机 · 毕业设计评审 · 正式业务 Authority</strong>
          </aside>
        </div>
      </section>

      <section class="yk-highlight-closing">
        <div class="yk-shell">
          <p>一个学生有连续上下文</p><p>一份材料有真实版本</p><p>一次办理有明确依据</p><p>一个任务有责任与下一步</p>
          <h2>让学校看到的不只是“功能很多”，而是一套能持续承载真实业务的数字工作平台。</h2>
          <div class="yk-hero-actions">
            <router-link class="yk-button yk-button-primary" to="/contact">预约产品演示</router-link>
            <router-link class="yk-button yk-button-ghost" to="/products">查看四大核心产品</router-link>
          </div>
        </div>
      </section>
    </main>

    <footer class="yk-footer">
      <div class="yk-shell yk-footer-inner">
        <div><strong>{{ contact.company }}</strong><span>职业院校学生全生命周期数字化平台</span></div>
        <div class="yk-footer-links"><router-link to="/products">产品中心</router-link><router-link to="/about">关于跃科</router-link><a :href="contact.phoneHref">{{ contact.phone }}</a><span>© {{ year }}</span></div>
      </div>
    </footer>
  </div>
</template>

<script>
import { OFFICIAL_SITE_CONTACT } from '@/config/officialSalesPages'
import { syncOfficialSeo } from '@/services/officialSeoRuntime'
import '@/styles/official-site.css'
import '@/styles/official-site-story.css'
import '@/styles/official-platform-capabilities.css'
import '@/styles/official-platform-highlights.css'

const HERO_TAGS = Object.freeze(['学生 360°', '可信文件版本', '统一审批', '业务待办直达', '可信 Excel', '在线批阅', '电子证据', '协同工作台'])

const CURRENT_FOUNDATION = Object.freeze([
  { mark: '360', title: '学生 360° 成长工作台', desc: '跨越学业、学工、实习、毕业设计与就业，把学生关键状态、风险摘要和下一步动作放到同一授权上下文里。', value: '从“查多个系统”转向“围绕一个学生开展工作”' },
  { mark: 'FILE', title: '统一安全文件与版本中心', desc: '文件对象、逻辑资产、不可覆盖版本、业务绑定、SHA-256、安全等级、扫描状态、保留期限和归档清单统一治理。', value: '附件从“上传文件”升级为可治理的业务资产' },
  { mark: 'APP', title: '跨业务统一审批中心', desc: '批准、退回修改、驳回、转办等办理动作由服务端按真实权限给出，待办携带业务对象、节点、期限和上下文。', value: '不同模块的审批进入统一工作方式' },
  { mark: 'GO', title: '业务待办一键直达', desc: '待办区分真实详情、列表聚焦和安全入口；不能证明存在真实详情页时，不伪造深链。', value: '点击待办直接去真正需要办理的位置' },
  { mark: 'XLSX', title: '可信 Excel 数据交换中心', desc: '标准模板、字段规则、重复检查、错误行回传、预校验与确认写入形成统一导入底座，高风险导入还能锁定确认上下文。', value: '大批量数据也做到先检查、再落库、错误可定位' },
  { mark: 'HELP', title: '内置业务知识与操作帮助中心', desc: '业务说明、流程图和高频任务卡与真实前端入口一起维护，没有真实页面的能力不写帮助、不制造假入口。', value: '降低培训成本，让老师在办理现场就能找到答案' },
  { mark: 'JOB', title: '统一后台任务与批处理中心', desc: '导入、导出、文件和批处理任务统一观察状态、发起人、范围快照、幂等、失败、积压、重试与取消。', value: '把长任务从“黑盒等待”变成可观察、可治理的后台工作' },
  { mark: 'BASE', title: '多租户、权限、数据范围与审计底座', desc: '学校租户、角色权限、数据范围、敏感访问和关键操作审计作为所有业务模块共同的生产边界。', value: '平台能力扩展时，安全边界不被各模块重复实现' }
])

const HIGHLIGHTS = Object.freeze([
  { no: '01', status: '当前具备', title: '学生 360° 成长工作台', summary: '一个页面理解学生是谁、现在处于什么状态、有哪些风险、老师下一步该做什么。', pain: '学生信息散落在教务、学工、实习、毕设与就业。', value: '围绕学生统一上下文，不再围绕模块来回找数据。' },
  { no: '02', status: '当前具备', title: '统一安全文件与版本中心', summary: '重要业务材料统一进入文件中心，版本不可覆盖，文件哈希、安全状态、业务绑定与归档清单可追踪。', pain: '附件被覆盖后无法证明当时审核的是哪一版。', value: '把材料变成有版本、有边界、有证据属性的业务资产。' },
  { no: '03', status: '持续演进', title: '四端在线文档预览与批阅', summary: '目标是在管理/教师 PC、学生 PC、教师与学生移动端形成一致的安全预览工作方式，并把预览权限与下载权限分离。', pain: '老师反复下载材料，重交以后容易“看旧稿、批新稿”。', value: '站内查看、锁定真实文件版本，返回业务页后重新核验版本真相。' },
  { no: '04', status: '当前具备', title: '跨业务统一审批中心', summary: '请假、奖助、学籍异动、成绩审核等业务进入统一审批工作区，动作、权限、期限和上下文由服务端统一约束。', pain: '老师在多个模块之间寻找审批入口，办理动作口径不一。', value: '把审批从“每个模块各做一套”收敛成统一工作方式。' },
  { no: '05', status: '持续演进', title: '材料合规智能检查', summary: '把缺材料、格式、版本、安全扫描和业务规则中的机械检查前置，让老师先看必须整改项和关注项。', pain: '老师大量时间花在重复确认“附件有没有齐”。', value: '系统先预检，老师把时间留给真正需要专业判断的内容。' },
  { no: '06', status: '持续演进', title: '可信电子证据链', summary: '目标是把业务快照、真实文件版本、哈希、审核状态和归档清单一起冻结，形成可复核电子业务证据。', pain: '业务显示“已完成”，但事后难说明当时依据和材料版本。', value: '回答“当时发生了什么、依据什么、谁办理”的审计问题。' },
  { no: '07', status: '持续演进', title: '全局业务搜索', summary: '目标是跨学生、我的待办和有权限的业务对象统一搜索，并由服务端返回真实可达目标。', pain: '系统越大，老师越难记住某件事藏在哪个二级菜单。', value: '不先想模块，直接搜索人和事，再去真实业务位置。' },
  { no: '08', status: '持续演进', title: '协同工作台', summary: '在现有统一工作台和待办基础上继续加入任务池、原子认领、安全转办、临时代理、临期与超期管理。', pain: '多人共同办理时容易重复处理、责任不清、积压不可见。', value: '让任务真正流动起来，并清楚知道谁负责、何时到期。' }
])

const PROOFS = Object.freeze([
  { image: '/official-site/workbench.webp', title: '统一工作台', alt: '跃科统一工作台真实运行界面', desc: '跨业务待办、风险、进度与下一动作汇到老师日常工作的第一入口。' },
  { image: '/official-site/approval-center.webp', title: '统一审批中心', alt: '跃科审批中心真实运行界面', desc: '审批待办、已办、退回记录等形成统一办理入口。' },
  { image: '/official-site/student-affairs-master.webp', title: '学生主档与学生工作', alt: '跃科学生主档真实运行界面', desc: '围绕学生建立跨事务上下文，为学生 360° 工作方式提供真实业务入口。' },
  { image: '/official-site/graduation-final-review.webp', title: '毕业设计成果评阅', alt: '跃科毕业设计成果评阅真实运行界面', desc: '长周期材料提交、评阅与整改场景为文件版本和在线批阅演进提供真实业务承载点。' }
])

const EVOLUTION_GROUPS = Object.freeze([
  { key: 'A', label: 'TRUST', title: '可信与一致性', desc: '让重要业务完成以后仍然能证明，并主动发现跨系统状态不一致。', points: '可信电子证据链 · 跨业务一致性巡检' },
  { key: 'B', label: 'RULES', title: '规则与材料智能', desc: '把高频机械检查和学校差异配置化，同时保持正式业务 Authority 不被旁路。', points: '材料合规检查 · 动态业务表单' },
  { key: 'C', label: 'INTELLIGENCE', title: '文档与学生事实', desc: '让老师先看版本变化，也沿时间轴理解学生几年里发生过什么。', points: '文档版本比对 · 学生生命周期事实流' },
  { key: 'D', label: 'WORK', title: '搜索与协同工作', desc: '让老师直接找到人和事，并支持多人安全认领、转办、代理和期限管理。', points: '全局业务搜索 · 任务池 / 认领 / 转办 / 代理 / SLA' }
])

const WORK_WAYS = Object.freeze([
  { label: '围绕人', title: '打开一个学生，先看完整上下文', desc: '学生主档、关键业务状态、风险摘要和下一动作集中呈现，减少跨模块逐个查询。' },
  { label: '围绕材料', title: '先看版本，再做专业判断', desc: '文件中心保留真实版本；在线预览、批阅与版本差异能力持续在这个版本底座上演进。' },
  { label: '围绕事', title: '待办直接去办理，不先找菜单', desc: '统一待办和审批中心携带真实业务上下文，后续全局搜索与协同队列继续缩短路径。' },
  { label: '围绕治理', title: 'Excel、帮助和后台任务也有统一底座', desc: '数据导入、错误回传、任务状态和操作帮助被平台化管理，实施交付不再依赖零散脚本与口头培训。' }
])

const PLATFORM_LAYERS = Object.freeze(['学生 360°', '统一文件版本', '统一审批', '业务直达待办', '可信 Excel', '业务帮助中心', '后台任务治理', '可信电子证据', '全局搜索', '协同工作台'])

export default {
  name: 'OfficialPlatformCapabilityView',
  data() {
    return {
      heroTags: HERO_TAGS,
      currentFoundation: CURRENT_FOUNDATION,
      highlights: HIGHLIGHTS,
      proofs: PROOFS,
      evolutionGroups: EVOLUTION_GROUPS,
      workWays: WORK_WAYS,
      platformLayers: PLATFORM_LAYERS
    }
  },
  computed: {
    contact() { return OFFICIAL_SITE_CONTACT },
    year() { return new Date().getFullYear() }
  },
  mounted() { syncOfficialSeo('/platform') }
}
</script>
