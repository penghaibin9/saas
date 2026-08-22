<template>
  <div class="yk-site yk-story-site yk-capability-page">
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
      <section class="yk-cap-hero" aria-labelledby="platform-capability-title">
        <div class="yk-shell yk-cap-hero-grid">
          <div class="yk-cap-hero-copy">
            <div class="yk-cap-status"><span></span> 平台能力持续构建</div>
            <p class="yk-kicker">跃科学生全生命周期平台</p>
            <h1 id="platform-capability-title">让学校真正看见每一名学生，<br />也真正管清每一件事。</h1>
            <p class="yk-cap-lead">
              覆盖岗位实习、毕业设计、学工、教务等核心场景，连接材料、审批、证据、待办与学生成长轨迹，
              构建职业院校学生全生命周期数字化工作平台。
            </p>
            <div class="yk-cap-tags" aria-label="平台能力关键词">
              <span v-for="tag in heroTags" :key="tag">{{ tag }}</span>
            </div>
            <div class="yk-hero-actions">
              <a class="yk-button yk-button-primary" href="#capability-matrix">了解产品能力</a>
              <router-link class="yk-button yk-button-ghost" to="/contact">预约产品演示</router-link>
            </div>
            <p class="yk-cap-truth-note">
              本页同时展示现有平台底座与正在建设的平台化能力。未完成生产封板的能力统一标注“持续构建”，
              具体可交付范围以项目合同、正式版本与上线验收为准。
            </p>
          </div>

          <div class="yk-cap-hero-visual" aria-label="跃科统一工作方式示意">
            <figure class="yk-cap-main-shot">
              <img src="/official-site/workbench.webp" alt="跃科统一工作台真实运行界面" decoding="async" />
              <figcaption>真实运行界面 · 隔离测试数据</figcaption>
            </figure>
            <div class="yk-cap-floating yk-cap-floating-one">
              <span>今日工作</span><strong>先看待办与风险</strong><small>工作台统一入口</small>
            </div>
            <div class="yk-cap-floating yk-cap-floating-two">
              <span>学生主线</span><strong>跨业务连续追踪</strong><small>从入校到毕业就业</small>
            </div>
          </div>
        </div>
      </section>

      <section class="yk-cap-connect">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">不是再多一个校园管理系统</p>
            <h2>而是让原本分散的校园业务真正连接起来。</h2>
            <p>公共平台不替代业务模块做专业判断，而是把文件、规则、证据、查询、协作、异常与轨迹连接起来。</p>
          </div>
          <div class="yk-cap-principles">
            <article v-for="item in principles" :key="item.title">
              <span class="yk-cap-principle-mark">{{ item.mark }}</span>
              <h3>{{ item.title }}</h3>
              <p>{{ item.desc }}</p>
            </article>
          </div>
        </div>
      </section>

      <section id="capability-matrix" class="yk-section yk-cap-matrix-section">
        <div class="yk-shell">
          <div class="yk-section-heading yk-section-heading-left">
            <p class="yk-kicker">ABCD · 四组平台级公共能力</p>
            <h2>从“业务模块集合”升级为“校园业务操作平台”</h2>
            <p>四组能力分别解决可信、规则、智能与协同问题。它们服务于教务、学工、实习、毕设等业务，但不建立第二套业务 Authority。</p>
          </div>
          <div class="yk-cap-matrix">
            <article v-for="group in capabilityGroups" :key="group.key" :class="`yk-cap-group yk-cap-group-${group.key.toLowerCase()}`">
              <div class="yk-cap-group-head">
                <span>{{ group.key }}</span>
                <div><small>{{ group.label }}</small><h3>{{ group.title }}</h3></div>
              </div>
              <p>{{ group.problem }}</p>
              <ul><li v-for="point in group.points" :key="point">{{ point }}</li></ul>
              <strong>{{ group.outcome }}</strong>
            </article>
          </div>
        </div>
      </section>

      <section class="yk-section yk-capabilities-section">
        <div class="yk-shell">
          <div class="yk-section-heading yk-section-heading-left">
            <p class="yk-kicker">七项重点能力</p>
            <h2>能查、能比、能验、能追、能证、能协同</h2>
            <p>不是堆技术名词，而是把学校每天真实发生的材料检查、整改重交、归档复核、学生跟踪与多人办理变得更清楚。</p>
          </div>

          <div class="yk-capability-list">
            <article v-for="(item, index) in capabilities" :key="item.no" class="yk-capability-detail" :class="{ 'yk-capability-detail-reverse': index % 2 === 1 }">
              <div class="yk-capability-copy">
                <div class="yk-capability-meta">
                  <span>{{ item.no }}</span>
                  <b>{{ item.status }}</b>
                </div>
                <p class="yk-kicker">{{ item.eyebrow }}</p>
                <h3>{{ item.title }}</h3>
                <p class="yk-capability-summary">{{ item.summary }}</p>
                <div class="yk-capability-question">{{ item.question }}</div>
                <ul><li v-for="point in item.points" :key="point">{{ point }}</li></ul>
                <div class="yk-capability-result"><span>老师最终得到</span><strong>{{ item.result }}</strong></div>
              </div>

              <div class="yk-capability-demo" :aria-label="`${item.title}能力说明示意`">
                <div class="yk-demo-window">
                  <div class="yk-demo-toolbar"><i></i><i></i><i></i><span>{{ item.demoTitle }}</span></div>
                  <div class="yk-demo-body">
                    <template v-if="item.kind === 'evidence'">
                      <div class="yk-demo-record"><span>归档对象</span><strong>毕业设计 · 张三 · 终稿</strong></div>
                      <div class="yk-demo-check" v-for="row in ['业务快照已冻结', '文件版本已锁定', '审核状态已记录', 'SHA-256 已生成']" :key="row"><b>✓</b><span>{{ row }}</span></div>
                      <div class="yk-demo-package">最终证据包 <strong>可核验</strong></div>
                    </template>
                    <template v-else-if="item.kind === 'compliance'">
                      <div class="yk-demo-score"><strong>92%</strong><span>材料完整度</span></div>
                      <div class="yk-demo-alert is-danger"><b>1</b><span>项必须整改</span></div>
                      <div class="yk-demo-alert"><b>2</b><span>项需要关注</span></div>
                      <div class="yk-demo-alert is-ok"><b>5</b><span>项满足当前规则</span></div>
                    </template>
                    <template v-else-if="item.kind === 'form'">
                      <label class="yk-demo-field"><span>是否属于特殊备案情形</span><strong>是</strong></label>
                      <label class="yk-demo-field active"><span>情形类型</span><strong>请选择</strong></label>
                      <label class="yk-demo-field active"><span>情况说明</span><strong>填写说明</strong></label>
                      <label class="yk-demo-field active"><span>证明材料</span><strong>上传文件</strong></label>
                      <small>字段按学校/批次规则出现，提交后仍进入正式业务流程</small>
                    </template>
                    <template v-else-if="item.kind === 'diff'">
                      <div class="yk-demo-version"><span>V3</span><b>对比</b><span>V4</span></div>
                      <div class="yk-demo-diff removed">- 删除：原方案采用线下登记……</div>
                      <div class="yk-demo-diff added">+ 新增：改为线上全过程留痕……</div>
                      <div class="yk-demo-diff changed">~ 修改：指导记录由每周一次调整为……</div>
                      <div class="yk-demo-stat">共发现 <strong>7</strong> 个变化位置</div>
                    </template>
                    <template v-else-if="item.kind === 'timeline'">
                      <div v-for="event in timelineDemo" :key="event.time" class="yk-demo-timeline">
                        <time>{{ event.time }}</time><i></i><span>{{ event.text }}</span>
                      </div>
                    </template>
                    <template v-else-if="item.kind === 'search'">
                      <div class="yk-demo-search">⌕&nbsp;&nbsp;张三</div>
                      <div class="yk-demo-search-result"><small>学生</small><strong>张三 · 软件技术 2301</strong></div>
                      <div class="yk-demo-search-result"><small>我的待办</small><strong>张三 · 毕业设计终稿待评阅</strong></div>
                      <div class="yk-demo-search-result"><small>岗位实习</small><strong>张三 · 风险处置记录</strong></div>
                    </template>
                    <template v-else>
                      <div class="yk-demo-workload">
                        <span><strong>7</strong>今日新增</span><span><strong>3</strong>24h 内到期</span><span><strong>2</strong>已超期</span>
                      </div>
                      <div class="yk-demo-pool"><span>学院公共任务池</span><strong>9 条待认领</strong></div>
                      <div class="yk-demo-task"><span>毕业设计材料复核 · 张三</span><button type="button">认领办理</button></div>
                      <div class="yk-demo-task"><span>实习风险复核 · 李四</span><b>李老师代王老师办理</b></div>
                    </template>
                  </div>
                </div>
                <p>能力说明示意 · 不作为未封板功能的已上线界面证明</p>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section class="yk-section yk-cap-day-section">
        <div class="yk-shell">
          <div class="yk-section-heading">
            <p class="yk-kicker">目标工作方式 · 一位老师的一天</p>
            <h2>系统越大，不应该让老师越难用。</h2>
            <p>以下场景用于说明这些平台能力组合后的目标工作方式，其中包含持续建设能力，不代表全部场景已经生产封板。</p>
          </div>
          <div class="yk-day-track">
            <article v-for="item in teacherDay" :key="item.time">
              <time>{{ item.time }}</time>
              <div class="yk-day-dot"></div>
              <div><small>{{ item.label }}</small><h3>{{ item.title }}</h3><p>{{ item.desc }}</p><strong v-if="item.callout">{{ item.callout }}</strong></div>
            </article>
          </div>
        </div>
      </section>

      <section class="yk-section yk-cap-platform-section">
        <div class="yk-shell yk-cap-platform-grid">
          <div>
            <p class="yk-kicker">最终形成什么</p>
            <h2>从“很多功能做在一起”，跨越到“所有业务在同一套平台能力上协同运行”。</h2>
            <p>
              毕业设计依然决定什么叫“评阅通过”，岗位实习依然决定什么叫“实习完成”，
              学工和教务也继续保有自己的正式业务责任。公共平台负责连接共同能力，而不是抢走业务 Authority。
            </p>
            <div class="yk-cap-platform-tags">
              <span v-for="item in platformLayers" :key="item">{{ item }}</span>
            </div>
          </div>
          <div class="yk-cap-authority-card">
            <span>公共平台负责</span>
            <strong>文件 · 规则 · 证据 · 查询 · 协作 · 异常 · 轨迹</strong>
            <hr />
            <span>业务模块继续负责</span>
            <strong>专业规则 · 正式状态 · 业务审批 · 最终 Authority</strong>
          </div>
        </div>
      </section>

      <section class="yk-cap-closing">
        <div class="yk-shell">
          <p>每一份材料都有版本</p>
          <p>每一次办理都有依据</p>
          <p>每一个任务都有责任人</p>
          <p>每一名学生都有连续轨迹</p>
          <h2>让学生工作更清楚，让教师工作更高效，让学校管理更可信。</h2>
          <div class="yk-hero-actions">
            <router-link class="yk-button yk-button-light" to="/contact">预约产品演示</router-link>
            <router-link class="yk-button yk-button-ghost" to="/products">查看四大核心产品</router-link>
          </div>
        </div>
      </section>
    </main>

    <footer class="yk-footer">
      <div class="yk-shell yk-footer-inner">
        <div><strong>{{ contact.company }}</strong><span>职业院校学生全生命周期数字化平台</span></div>
        <div class="yk-footer-links">
          <router-link to="/products">产品中心</router-link>
          <router-link to="/about">关于跃科</router-link>
          <a :href="contact.phoneHref">{{ contact.phone }}</a>
          <span>© {{ year }}</span>
        </div>
      </div>
    </footer>
  </div>
</template>

<script>
import { OFFICIAL_SALES_PAGE_MAP, OFFICIAL_SITE_CONTACT } from '@/config/officialSalesPages'
import '@/styles/official-site.css'
import '@/styles/official-site-story.css'
import '@/styles/official-platform-capabilities.css'

const HERO_TAGS = Object.freeze(['材料自动检查', '文档版本比对', '可信电子归档', '学生成长轨迹', '全局业务搜索', '协同任务办理'])

const PRINCIPLES = Object.freeze([
  { mark: '信', title: '可信', desc: '业务全过程留痕，重要材料版本冻结，归档结果可核验。' },
  { mark: '效', title: '高效', desc: '材料自动预检、版本智能比对，让老师少做重复检查。' },
  { mark: '续', title: '连续', desc: '跨越学业、学工、实习、毕设与就业，看见完整学生成长轨迹。' },
  { mark: '协', title: '协同', desc: '全局搜索、公共任务池、认领、转办、代理，让跨部门工作真正流动起来。' }
])

const CAPABILITY_GROUPS = Object.freeze([
  { key: 'A', label: 'TRUST', title: '可信证据链', problem: '解决“办完以后无法证明、跨系统异常难发现”。', points: ['冻结业务快照与真实文件版本', '归档清单、哈希与审核状态可复核', '跨系统异常主动巡检'], outcome: '每项重要业务都有可验证证据' },
  { key: 'B', label: 'RULES', title: '规则与表单引擎', problem: '解决“材料靠人工检查、学校差异频繁定制”。', points: ['材料完整性与合规预检', '动态字段与条件显示', '配置最终落回正式业务流程'], outcome: '系统先预检，老师做判断' },
  { key: 'C', label: 'INTELLIGENCE', title: '文档与事实智能', problem: '解决“重交重新通读、学生经历彼此割裂”。', points: ['文件版本差异定位', '跨业务学生事实流', '全过程时间轴与事实来源'], outcome: '看变化、看轨迹、看全过程' },
  { key: 'D', label: 'WORK', title: '搜索与协同工作台', problem: '解决“系统越大越难找、多人协作容易重复”。', points: ['搜人搜事直接到业务', '公共任务池与并发认领', '安全转办、临时代理与紧迫度'], outcome: '直接找到事，真正协同办' }
])

const CAPABILITIES = Object.freeze([
  {
    no: '01', status: '持续构建', eyebrow: '可信电子证据链', title: '业务办完之后，不只留下“状态已完成”。',
    summary: '把关键业务事实与真实文件版本冻结下来，形成可复核、可校验、可追溯的正式电子业务证据。',
    question: '它为什么算办完？当时依据哪一版材料？谁提交、谁审核？历史证据后来有没有被污染？',
    points: ['业务快照 + 文件版本 + 文件哈希 + 审核状态', '扫描状态 + 归档清单 + 最终证据包', '归档异常、任务状态与业务状态不一致主动巡检'],
    result: '一份能明确回答“当时发生了什么”的电子业务档案。', demoTitle: '电子证据包', kind: 'evidence'
  },
  {
    no: '02', status: '持续构建', eyebrow: '材料合规智能检查', title: '从“老师人工翻材料”，升级为“系统先检查，老师做判断”。',
    summary: '提交前完成机械性规则检查，把缺材料、版本错误、格式问题和安全扫描状态提前暴露。',
    question: '老师真正需要做的是业务判断，而不是重复确认“附件有没有传齐”。',
    points: ['必交材料、类型、大小、最新版检查', '安全扫描、人工审核要求与状态门禁', '必须整改与提示性风险分级展示'],
    result: '先看到完整度、必须整改项和关注项，再决定是否进入下一环节。', demoTitle: '材料预检', kind: 'compliance'
  },
  {
    no: '03', status: '持续构建', eyebrow: '动态业务表单', title: '学校业务规则变化，不必每一次都重新开发一套页面。',
    summary: '把部分高频、规则明确的业务字段配置化，让学校、专业、批次差异以受控规则进入正式流程。',
    question: '灵活不是再造一套“万能数据”，而是在明确 Authority 边界内减少重复定制。',
    points: ['条件字段按答案动态出现', '字段校验、证明材料与补充信息可配置', '最终提交仍进入实习、毕设、学工、教务正式流程'],
    result: '更低成本适配学校差异，同时不形成第二套影子数据。', demoTitle: '规则驱动表单', kind: 'form'
  },
  {
    no: '04', status: '持续构建', eyebrow: '文档版本智能比对', title: '学生重新提交以后，老师一眼看见“到底改了什么”。',
    summary: '对有权限查看的两个文件版本生成差异结果，让评阅、整改与二次审核先看变化，再看全文。',
    question: '老师想知道的不是“又传了一份 60 页文档”，而是“这次改了哪 7 个位置”。',
    points: ['新增、删除、修改内容定位', '变化段落与差异统计', '比对权限继承原文件访问权限'],
    result: '从重新通读全文，变成优先检查发生变化的位置。', demoTitle: 'V3 ↔ V4 版本比对', kind: 'diff'
  },
  {
    no: '05', status: '持续构建', eyebrow: '学生全生命周期事实流', title: '不只看一张学生档案，而是看见几年里“发生过什么”。',
    summary: '把已经发生的学业、学工、实习、毕设与就业相关事实投影到统一学生主线，为学生 360 与风险研判提供连续上下文。',
    question: '学生主档告诉老师“他是谁”，事实流继续告诉老师“他经历了什么”。',
    points: ['事实保留时间、来源与业务对象', '跨模块只做投影，不反写原业务 Authority', '为学生 360、辅导员工作台和离校审计提供统一主线'],
    result: '打开一个学生，就能沿时间轴理解关键经历和处置结果。', demoTitle: '张三 · 成长轨迹', kind: 'timeline'
  },
  {
    no: '06', status: '持续构建', eyebrow: '全局业务搜索', title: '不再先想“我要去哪个模块”，直接搜索我要处理的人和事。',
    summary: '把学生、我的待办和有权限的业务结果聚合到统一搜索入口，由服务端返回真实目标页面。',
    question: '功能越来越多时，老师不应该先记住“这个功能在第几个二级菜单”。',
    points: ['搜学生、待办与有权限的业务对象', '结果携带服务端确定的真实目标', '搜索继续服从租户、角色、权限与数据范围'],
    result: '搜人或搜事，然后直达真正需要办理的位置。', demoTitle: '全局业务搜索', kind: 'search'
  },
  {
    no: '07', status: '持续构建', eyebrow: '协同待办 2.0', title: '从“给我一张任务列表”，升级为“真正支持多人协作的工作队列”。',
    summary: '面向学院多人共同办理场景，支持公共任务池、原子认领、安全转办、临时代理与负载紧迫度。',
    question: '300 条待审核不等于先平均分给 3 个老师，也不应该让 3 个人同时处理同一条。',
    points: ['公共池任务可认领，同一任务只允许一个人成功', '转办只展示真正有资格接手的人', '代理保留真实操作人与原责任人的历史关系', '工作台突出新增、临期、超期、已认领与公共池'],
    result: '打开工作台第一眼就知道今天先处理什么、谁在负责。', demoTitle: '协同工作队列', kind: 'work'
  }
])

const TIMELINE_DEMO = Object.freeze([
  { time: '03月', text: '进入岗位实习阶段' },
  { time: '04月', text: '企业变更申请完成' },
  { time: '05月', text: '风险预警 → 指导教师完成处置' },
  { time: '06月', text: '毕业设计开题通过' },
  { time: '08月', text: '终稿提交并进入正式评阅' }
])

const TEACHER_DAY = Object.freeze([
  { time: '08:20', label: '打开工作台', title: '先看今天最需要处理什么', desc: '目标工作台聚合新增、即将超期、已超期与公共池事项。', callout: '今天新增待办 7 · 即将超期 3 · 公共池待认领 4' },
  { time: '08:25', label: '搜索学生', title: '直接输入“张三”', desc: '学生、毕业设计待评阅、岗位实习归档和当前待处理事项在同一结果里出现。' },
  { time: '08:27', label: '评阅重交', title: '先看 V4 相比 V3 改了哪里', desc: '系统先给出差异位置，再由老师结合完整文档做专业判断。', callout: '本次为 V4 · 相比 V3 修改 7 个位置' },
  { time: '09:10', label: '材料审核', title: '先看系统预检结果', desc: '机械性材料规则先检查，老师聚焦真正需要判断或退回的内容。', callout: '6 项材料中 5 项符合要求 · 1 项证明材料缺失' },
  { time: '10:30', label: '共同办理', title: '从学院公共池认领任务', desc: '并发认领只允许一个人成功，避免重复办理和责任不清。' },
  { time: '16:00', label: '异常巡检', title: '在问题影响师生之前发现不一致', desc: '目标异常中心发现业务完成但任务未闭环、归档对象缺证据包等跨系统问题。' },
  { time: '17:00', label: '学生 360', title: '沿事实流理解一名学生的连续经历', desc: '从入学、学业、学工、实习到毕业设计，关键事实沿时间轴呈现。' }
])

const PLATFORM_LAYERS = Object.freeze(['统一文件版本', '统一材料规则', '统一电子证据', '统一业务搜索', '统一任务协作', '统一学生事实流', '统一异常巡检', '统一权限与审计'])

export default {
  name: 'OfficialPlatformCapabilityView',
  data() {
    return {
      heroTags: HERO_TAGS,
      principles: PRINCIPLES,
      capabilityGroups: CAPABILITY_GROUPS,
      capabilities: CAPABILITIES,
      timelineDemo: TIMELINE_DEMO,
      teacherDay: TEACHER_DAY,
      platformLayers: PLATFORM_LAYERS
    }
  },
  computed: {
    page() { return OFFICIAL_SALES_PAGE_MAP['/platform'] },
    contact() { return OFFICIAL_SITE_CONTACT },
    year() { return new Date().getFullYear() }
  },
  mounted() {
    this.syncHead()
  },
  methods: {
    syncHead() {
      document.title = '跃科平台能力｜可信证据、材料规则、学生事实与协同工作台'
      const description = '跃科持续构建可信电子证据链、材料合规检查、动态表单、文档版本比对、学生全生命周期事实流、全局业务搜索与协同待办等平台级公共能力。'
      let meta = document.querySelector('meta[name="description"]')
      if (!meta) {
        meta = document.createElement('meta')
        meta.setAttribute('name', 'description')
        document.head.appendChild(meta)
      }
      meta.setAttribute('content', description)
    }
  }
}
</script>
